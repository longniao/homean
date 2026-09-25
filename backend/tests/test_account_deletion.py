"""DELETE /me removes the caller's account, workspace, media and sessions."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Visit, Workspace, WorkspaceSubscription
from app.services import FakeBillingProvider
from app.storage.fake import FakeStorageProvider
from tests.test_capture import auth_headers, create_property

PASSWORD = "correct-horse-battery-staple"


async def _showing_with_media(
    client: AsyncClient, storage: FakeStorageProvider, headers: dict[str, str]
) -> tuple[str, str, str]:
    """Create a showing with one uploaded audio object and a branding logo."""

    property_data = await create_property(client, headers, "Home", "1 Main St")
    showing = await client.post(
        "/showings", headers=headers, json={"subject_id": property_data["id"]}
    )
    assert showing.status_code == 201, showing.text
    visit_id = showing.json()["id"]
    presign = await client.post(
        f"/showings/{visit_id}/media/presign",
        headers=headers,
        json={"type": "audio", "content_type": "audio/mp4", "timestamp_offset_ms": 0},
    )
    assert presign.status_code == 200, presign.text
    media_key = storage.presigned_puts[-1]
    storage.put_object(media_key, "audio/mp4", 1024)
    completed = await client.post(
        f"/showings/{visit_id}/media/{presign.json()['media_id']}/complete",
        headers=headers,
    )
    assert completed.status_code == 200, completed.text

    logo = await client.post(
        "/branding/logo/presign", headers=headers, json={"content_type": "image/png"}
    )
    assert logo.status_code == 200, logo.text
    logo_key = storage.presigned_puts[-1]
    storage.put_object(logo_key, "image/png", 512)
    return visit_id, media_key, logo_key


async def test_delete_account_purges_only_the_callers_data(
    client: AsyncClient,
    storage: FakeStorageProvider,
    session: AsyncSession,
    test_app,  # type: ignore[no-untyped-def]
) -> None:
    del test_app
    from app.api.dependencies import get_billing_provider
    from app.main import app

    leaving = await auth_headers(client, "leaving@example.com")
    staying = await auth_headers(client, "staying@example.com")
    visit_id, media_key, logo_key = await _showing_with_media(client, storage, leaving)
    _, other_media_key, other_logo_key = await _showing_with_media(
        client, storage, staying
    )
    workspace_id = (await client.get("/me", headers=leaving)).json()["workspace"]["id"]

    # Give the leaving workspace a live paid subscription Stripe still owns.
    subscription = await session.scalar(
        select(WorkspaceSubscription).where(
            WorkspaceSubscription.workspace_id == workspace_id
        )
    )
    assert subscription is not None
    subscription.plan = "solo_monthly"
    subscription.status = "active"
    subscription.stripe_subscription_id = "sub_leaving"
    subscription.current_period_end = datetime.now(UTC) + timedelta(days=20)
    await session.commit()

    billing = FakeBillingProvider()
    app.dependency_overrides[get_billing_provider] = lambda: billing
    try:
        wrong = await client.request(
            "DELETE", "/me", headers=leaving, json={"password": "not-the-password"}
        )
        assert wrong.status_code == 403
        assert (await client.get("/me", headers=leaving)).status_code == 200
        assert media_key in storage.objects
        assert billing.cancelled_subscriptions == []

        deleted = await client.request(
            "DELETE", "/me", headers=leaving, json={"password": PASSWORD}
        )
        assert deleted.status_code == 204, deleted.text
    finally:
        app.dependency_overrides.pop(get_billing_provider, None)

    assert billing.cancelled_subscriptions == ["sub_leaving"]

    # Objects: only the leaving workspace's are gone.
    assert media_key not in storage.objects
    assert logo_key not in storage.objects
    assert other_media_key in storage.objects
    assert other_logo_key in storage.objects

    # Rows: user, workspace and visit are gone; the other account is untouched.
    session.expire_all()
    assert (
        await session.scalar(select(User).where(User.email == "leaving@example.com"))
        is None
    )
    assert await session.get(Workspace, workspace_id) is None
    assert await session.get(Visit, visit_id) is None
    assert (
        await session.scalar(select(User).where(User.email == "staying@example.com"))
        is not None
    )

    # Credentials: the old access token and the old password no longer work.
    assert (await client.get("/me", headers=leaving)).status_code == 401
    login = await client.post(
        "/auth/login", json={"email": "leaving@example.com", "password": PASSWORD}
    )
    assert login.status_code == 401
    assert (await client.get("/me", headers=staying)).status_code == 200

    # The address is free again.
    again = await client.post(
        "/auth/signup", json={"email": "leaving@example.com", "password": PASSWORD}
    )
    assert again.status_code == 201


async def test_delete_account_requires_authentication(client: AsyncClient) -> None:
    response = await client.request("DELETE", "/me", json={"password": PASSWORD})
    assert response.status_code == 401
