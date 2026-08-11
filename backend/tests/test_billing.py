import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WorkspaceSubscription
from app.services import FakeBillingProvider

PASSWORD = "correct-horse-battery-staple"


async def _signup(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/auth/signup", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_trial_status_and_subjectless_create(
    client: AsyncClient,
) -> None:
    headers = await _signup(client, "billing-trial@example.com")
    status = await client.get("/billing", headers=headers)
    assert status.status_code == 200
    assert status.json()["plan"] == "trial"
    assert status.json()["active"] is True

    showing = await client.post(
        "/showings", headers=headers, json={"consent_ack": True}
    )
    assert showing.status_code == 201
    assert showing.json()["property"] is None
    assert showing.json()["consent_ack"] is True


async def test_expired_trial_blocks_new_showings(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _signup(client, "billing-expired@example.com")
    token = headers["Authorization"].split(" ", 1)[1]
    from app.core.config import get_settings
    from app.services.auth import TokenService

    claims = TokenService(get_settings()).decode(token, "access")
    await session.execute(
        update(WorkspaceSubscription)
        .where(WorkspaceSubscription.workspace_id == claims.workspace_id)
        .values(trial_ends_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await session.commit()
    response = await client.post("/showings", headers=headers, json={})
    assert response.status_code == 402
    assert response.json()["code"] == "subscription_required"


async def test_checkout_webhook_activates_workspace(
    client: AsyncClient,
    test_app,
) -> None:
    del test_app
    from app.api.dependencies import get_billing_provider
    from app.core.config import get_settings
    from app.main import app

    headers = await _signup(client, "billing-webhook@example.com")
    fake = FakeBillingProvider()

    get_settings().stripe_solo_monthly_price_id = "price_test"
    app.dependency_overrides[get_billing_provider] = lambda: fake
    try:
        token = headers["Authorization"].split(" ", 1)[1]
        from app.core.config import get_settings
        from app.services.auth import TokenService

        claims = TokenService(get_settings()).decode(token, "access")
        fake.subscription_details["sub_test"] = {
            "id": "sub_test",
            "status": "active",
            "customer": "cus_test",
            "metadata": {"workspace_id": str(claims.workspace_id)},
            "current_period_end": int(
                (datetime.now(UTC) + timedelta(days=30)).timestamp()
            ),
            "cancel_at_period_end": False,
            "items": {"data": [{"price": {"id": "price_test"}}]},
        }
        event = {
            "id": "evt_checkout_test",
            "created": int(datetime.now(UTC).timestamp()),
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "mode": "subscription",
                    "metadata": {"workspace_id": str(claims.workspace_id)},
                    "customer": "cus_test",
                    "subscription": "sub_test",
                }
            },
        }
        response = await client.post("/billing/webhook", json=event)
        assert response.status_code == 204
        status = await client.get("/billing", headers=headers)
        assert status.json()["plan"] == "solo_monthly"
        assert status.json()["status"] == "active"
    finally:
        app.dependency_overrides.pop(get_billing_provider, None)


async def test_billing_capabilities_distinguish_trial_paid_and_canceled(
    client: AsyncClient, session: AsyncSession
) -> None:
    headers = await _signup(client, "billing-capabilities@example.com")
    trial = await client.get("/billing", headers=headers)
    assert trial.json()["billing_action"] == "subscribe"
    assert trial.json()["can_checkout"] is True
    assert trial.json()["can_portal"] is False

    token = headers["Authorization"].split(" ", 1)[1]
    from app.core.config import get_settings
    from app.services.auth import TokenService

    claims = TokenService(get_settings()).decode(token, "access")
    await session.execute(
        update(WorkspaceSubscription)
        .where(WorkspaceSubscription.workspace_id == claims.workspace_id)
        .values(
            plan="solo_monthly",
            status="active",
            stripe_customer_id="cus_capabilities",
            stripe_subscription_id="sub_capabilities",
            current_period_end=datetime.now(UTC) + timedelta(days=30),
            trial_ends_at=None,
        )
    )
    await session.commit()
    paid = await client.get("/billing", headers=headers)
    assert paid.json()["billing_action"] == "manage_billing"
    assert paid.json()["can_checkout"] is False
    assert paid.json()["can_portal"] is True

    await session.execute(
        update(WorkspaceSubscription)
        .where(WorkspaceSubscription.workspace_id == claims.workspace_id)
        .values(status="canceled", current_period_end=None)
    )
    await session.commit()
    canceled = await client.get("/billing", headers=headers)
    assert canceled.json()["billing_action"] == "subscribe"
    assert canceled.json()["can_checkout"] is True
    assert canceled.json()["can_portal"] is True


@pytest.mark.parametrize("stripe_status", ["active", "past_due"])
async def test_expired_paid_subscription_still_requires_portal(
    client: AsyncClient,
    session: AsyncSession,
    test_app,
    stripe_status: str,
) -> None:
    from app.api.dependencies import get_billing_provider
    from app.core.config import get_settings
    from app.main import app
    from app.services.auth import TokenService

    fake = FakeBillingProvider()
    get_settings().stripe_solo_monthly_price_id = "price_expired"
    app.dependency_overrides[get_billing_provider] = lambda: fake
    try:
        headers = await _signup(client, f"billing-expired-{stripe_status}@example.com")
        claims = TokenService(get_settings()).decode(
            headers["Authorization"].split(" ", 1)[1], "access"
        )
        await session.execute(
            update(WorkspaceSubscription)
            .where(WorkspaceSubscription.workspace_id == claims.workspace_id)
            .values(
                plan="solo_monthly",
                status=stripe_status,
                stripe_customer_id="cus_expired",
                stripe_subscription_id=f"sub_expired_{stripe_status}",
                current_period_end=datetime.now(UTC) - timedelta(minutes=1),
                trial_ends_at=None,
            )
        )
        await session.commit()

        billing = await client.get("/billing", headers=headers)
        assert billing.status_code == 200
        assert billing.json()["active"] is False
        assert billing.json()["billing_action"] == "manage_billing"
        assert billing.json()["can_checkout"] is False
        assert billing.json()["can_portal"] is True

        checkout = await client.post(
            "/billing/checkout",
            headers=headers,
            json={"plan": "solo_monthly"},
        )
        assert checkout.status_code == 409
        assert checkout.json()["code"] == "billing_portal_required"
        assert fake.checkout_requests == []
    finally:
        app.dependency_overrides.pop(get_billing_provider, None)


async def test_checkout_reuses_customer_and_rejects_active_paid_duplicate(
    client: AsyncClient, session: AsyncSession, test_app
) -> None:
    from app.api.dependencies import get_billing_provider
    from app.core.config import get_settings
    from app.main import app
    from app.services.auth import TokenService

    get_settings().stripe_solo_monthly_price_id = "price_repeat"
    fake = FakeBillingProvider()
    app.dependency_overrides[get_billing_provider] = lambda: fake
    try:
        headers = await _signup(client, "billing-checkout-repeat@example.com")
        first = await client.post(
            "/billing/checkout", headers=headers, json={"plan": "solo_monthly"}
        )
        second = await client.post(
            "/billing/checkout", headers=headers, json={"plan": "solo_monthly"}
        )
        assert first.status_code == second.status_code == 200
        assert len(fake.checkout_requests) == 2
        assert (
            fake.checkout_requests[0]["idempotency_key"]
            == fake.checkout_requests[1]["idempotency_key"]
        )

        token = headers["Authorization"].split(" ", 1)[1]
        claims = TokenService(get_settings()).decode(token, "access")
        await session.execute(
            update(WorkspaceSubscription)
            .where(WorkspaceSubscription.workspace_id == claims.workspace_id)
            .values(
                plan="solo_monthly",
                status="active",
                stripe_customer_id="cus_repeat",
                stripe_subscription_id="sub_repeat",
                current_period_end=datetime.now(UTC) + timedelta(days=30),
            )
        )
        await session.commit()
        duplicate = await client.post(
            "/billing/checkout", headers=headers, json={"plan": "solo_monthly"}
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["code"] == "billing_portal_required"
        assert len(fake.checkout_requests) == 2

        original_key = fake.checkout_requests[0]["idempotency_key"]
        await session.execute(
            update(WorkspaceSubscription)
            .where(WorkspaceSubscription.workspace_id == claims.workspace_id)
            .values(
                status="canceled",
                current_period_end=None,
                stripe_event_id="evt_repeat_cancel",
                stripe_event_type="customer.subscription.deleted",
                stripe_event_created_at=datetime.now(UTC),
            )
        )
        await session.commit()
        replacement = await client.post(
            "/billing/checkout", headers=headers, json={"plan": "solo_monthly"}
        )
        assert replacement.status_code == 200
        assert fake.checkout_requests[-1]["customer_id"] == "cus_repeat"
        assert fake.checkout_requests[-1]["idempotency_key"] != original_key
    finally:
        app.dependency_overrides.pop(get_billing_provider, None)


async def test_canceled_subscription_can_be_replaced_without_old_event_interference(
    client: AsyncClient, session: AsyncSession, test_app
) -> None:
    from app.api.dependencies import get_billing_provider
    from app.core.config import get_settings
    from app.main import app
    from app.services.auth import TokenService

    fake = FakeBillingProvider()
    get_settings().stripe_solo_monthly_price_id = "price_replace"
    app.dependency_overrides[get_billing_provider] = lambda: fake
    try:
        headers = await _signup(client, "billing-replacement@example.com")
        claims = TokenService(get_settings()).decode(
            headers["Authorization"].split(" ", 1)[1], "access"
        )
        same_second = datetime.fromtimestamp(1_700_000_000, UTC)
        await session.execute(
            update(WorkspaceSubscription)
            .where(WorkspaceSubscription.workspace_id == claims.workspace_id)
            .values(
                plan="solo_monthly",
                status="canceled",
                stripe_customer_id="cus_reuse",
                stripe_subscription_id="sub_old",
                stripe_event_id="evt_old_cancel",
                stripe_event_type="customer.subscription.deleted",
                stripe_event_created_at=same_second,
                current_period_end=None,
                cancel_at_period_end=False,
                trial_ends_at=None,
            )
        )
        await session.commit()

        status = await client.get("/billing", headers=headers)
        assert status.json()["billing_action"] == "subscribe"
        assert status.json()["can_checkout"] is True
        assert status.json()["can_portal"] is True

        checkout = await client.post(
            "/billing/checkout", headers=headers, json={"plan": "solo_monthly"}
        )
        assert checkout.status_code == 200
        assert fake.checkout_requests[-1]["customer_id"] == "cus_reuse"

        metadata = {"workspace_id": str(claims.workspace_id)}
        fake.subscription_details["sub_new"] = {
            "id": "sub_new",
            "status": "active",
            "customer": "cus_reuse",
            "metadata": metadata,
            "price_id": "price_replace",
            "current_period_end": int(
                (datetime.now(UTC) + timedelta(days=30)).timestamp()
            ),
            "cancel_at_period_end": False,
        }
        replacement_event = {
            "id": "evt_new_checkout",
            "created": 1_700_000_000,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "mode": "subscription",
                    "metadata": metadata,
                    "customer": "cus_reuse",
                    "subscription": "sub_new",
                    "price_id": "price_replace",
                }
            },
        }
        activated = await client.post(
            "/billing/webhook", headers={}, json=replacement_event
        )
        assert activated.status_code == 204
        duplicate = await client.post(
            "/billing/webhook", headers={}, json=replacement_event
        )
        assert duplicate.status_code == 204

        old_events = [
            {
                "id": "evt_old_update_delayed",
                "created": 1_700_000_001,
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": "sub_old",
                        "status": "active",
                        "customer": "cus_reuse",
                        "metadata": metadata,
                        "price_id": "price_replace",
                    }
                },
            },
            {
                "id": "evt_old_delete_equal",
                "created": 1_700_000_000,
                "type": "customer.subscription.deleted",
                "data": {
                    "object": {
                        "id": "sub_old",
                        "customer": "cus_reuse",
                        "metadata": metadata,
                    }
                },
            },
        ]
        for old_event in old_events:
            response = await client.post("/billing/webhook", json=old_event)
            assert response.status_code == 204
            response = await client.post("/billing/webhook", json=old_event)
            assert response.status_code == 204

        final = await client.get("/billing", headers=headers)
        assert final.json()["status"] == "active"
        stored = await session.scalar(
            select(WorkspaceSubscription.stripe_subscription_id).where(
                WorkspaceSubscription.workspace_id == claims.workspace_id
            )
        )
        assert stored == "sub_new"
    finally:
        app.dependency_overrides.pop(get_billing_provider, None)


async def test_subscription_events_are_order_independent_idempotent_and_versioned(
    client: AsyncClient, session: AsyncSession, test_app
) -> None:
    from app.api.dependencies import get_billing_provider
    from app.core.config import get_settings
    from app.main import app

    fake = FakeBillingProvider()
    get_settings().stripe_solo_monthly_price_id = "price_test"
    app.dependency_overrides[get_billing_provider] = lambda: fake
    try:
        headers = await _signup(client, "billing-event-order@example.com")
        token = headers["Authorization"].split(" ", 1)[1]
        from app.services.auth import TokenService

        claims = TokenService(get_settings()).decode(token, "access")
        metadata = {"workspace_id": str(claims.workspace_id)}
        period_end = int((datetime.now(UTC) + timedelta(days=30)).timestamp())

        async def send(event: dict[str, object]) -> None:
            response = await client.post("/billing/webhook", json=event)
            assert response.status_code == 204, response.text

        await send(
            {
                "id": "evt_update_newer",
                "created": 200,
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": "sub_ordered",
                        "status": "active",
                        "customer": "cus_ordered",
                        "metadata": metadata,
                        "current_period_end": period_end,
                        "price_id": "price_test",
                    }
                },
            }
        )
        await send(
            {
                "id": "evt_checkout_older",
                "created": 100,
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "mode": "subscription",
                        "metadata": metadata,
                        "customer": "cus_ordered",
                        "subscription": "sub_ordered",
                        "status": "active",
                        "price_id": "price_test",
                    }
                },
            }
        )
        current = await client.get("/billing", headers=headers)
        assert current.json()["status"] == "active"

        deletion = {
            "id": "evt_delete_newest",
            "created": 300,
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_ordered",
                    "customer": "cus_ordered",
                    "metadata": metadata,
                }
            },
        }
        await send(deletion)
        await send(deletion)
        await send(
            {
                "id": "evt_update_stale",
                "created": 250,
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": "sub_ordered",
                        "status": "active",
                        "customer": "cus_ordered",
                        "metadata": metadata,
                        "price_id": "price_test",
                    }
                },
            }
        )
        final = await client.get("/billing", headers=headers)
        assert final.json()["status"] == "canceled"
        assert final.json()["current_period_end"] is None
    finally:
        app.dependency_overrides.pop(get_billing_provider, None)


async def test_equal_second_update_and_delete_are_order_independent(
    client: AsyncClient, test_app
) -> None:
    from app.api.dependencies import get_billing_provider
    from app.core.config import get_settings
    from app.main import app

    fake = FakeBillingProvider()
    get_settings().stripe_solo_monthly_price_id = "price_same_second"
    app.dependency_overrides[get_billing_provider] = lambda: fake
    try:

        async def run_order(email: str, events: list[dict[str, object]]) -> None:
            headers = await _signup(client, email)
            token = headers["Authorization"].split(" ", 1)[1]
            from app.services.auth import TokenService

            claims = TokenService(get_settings()).decode(token, "access")
            for event in events:
                event["data"]["object"]["metadata"] = {  # type: ignore[index]
                    "workspace_id": str(claims.workspace_id)
                }
                response = await client.post("/billing/webhook", json=event)
                assert response.status_code == 204, response.text
                duplicate = await client.post("/billing/webhook", json=event)
                assert duplicate.status_code == 204, duplicate.text
            status = await client.get("/billing", headers=headers)
            assert status.json()["status"] == "canceled"
            assert status.json()["current_period_end"] is None

        def event(
            event_id: str, event_type: str, subscription_id: str
        ) -> dict[str, object]:
            obj: dict[str, object] = {
                "id": subscription_id,
                "customer": "cus_same_second",
            }
            if event_type.endswith("updated"):
                obj.update(
                    {
                        "status": "active",
                        "price_id": "price_same_second",
                        "current_period_end": int(
                            (datetime.now(UTC) + timedelta(days=30)).timestamp()
                        ),
                    }
                )
            return {
                "id": event_id,
                "created": 1_700_000_000,
                "type": event_type,
                "data": {"object": obj},
            }

        update = event(
            "evt_same_update_first", "customer.subscription.updated", "sub_same_first"
        )
        deleted = event(
            "evt_same_delete_first", "customer.subscription.deleted", "sub_same_first"
        )
        await run_order("billing-equal-update-first@example.com", [update, deleted])
        update = event(
            "evt_same_update_second", "customer.subscription.updated", "sub_same_second"
        )
        deleted = event(
            "evt_same_delete_second", "customer.subscription.deleted", "sub_same_second"
        )
        await run_order("billing-equal-delete-first@example.com", [deleted, update])
    finally:
        app.dependency_overrides.pop(get_billing_provider, None)


def test_stripe_signature_supports_rotation_and_rejects_invalid_payloads() -> None:
    from app.core.config import get_settings
    from app.services.billing import StripeBillingProvider
    from app.services.exceptions import InvalidBillingEventError

    settings = get_settings()
    previous = settings.stripe_webhook_secret
    settings.stripe_webhook_secret = SecretStr("whsec_test")
    provider = StripeBillingProvider(settings)
    payload = json.dumps({"id": "evt_valid"}).encode()
    timestamp = str(int(time.time()))
    expected = hmac.new(
        b"whsec_test", timestamp.encode() + b"." + payload, hashlib.sha256
    ).hexdigest()
    try:
        assert (
            provider.verify_webhook(
                payload, f"t={timestamp},v1=old-signature,v1={expected}"
            )["id"]
            == "evt_valid"
        )
        for signature in (None, "t=bad,v1=bad", "t=1,v1=bad"):
            try:
                provider.verify_webhook(payload, signature)
            except InvalidBillingEventError:
                pass
            else:
                raise AssertionError("invalid signature was accepted")
        try:
            provider.verify_webhook(b"not-json", f"t={timestamp},v1={expected}")
        except InvalidBillingEventError:
            pass
        else:
            raise AssertionError("invalid payload was accepted")
    finally:
        settings.stripe_webhook_secret = previous


async def test_webhook_route_returns_400_for_missing_signature(
    client: AsyncClient, test_app
) -> None:
    del test_app
    from app.api.dependencies import get_billing_provider
    from app.core.config import get_settings
    from app.main import app
    from app.services.billing import StripeBillingProvider

    settings = get_settings()
    previous = settings.stripe_webhook_secret
    settings.stripe_webhook_secret = SecretStr("whsec_test")
    app.dependency_overrides[get_billing_provider] = lambda: StripeBillingProvider(
        settings
    )
    try:
        response = await client.post("/billing/webhook", json={})
        assert response.status_code == 400
        assert response.json()["code"] == "invalid_billing_event"
    finally:
        app.dependency_overrides.pop(get_billing_provider, None)
        settings.stripe_webhook_secret = previous
