import uuid
from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Membership, ProfessionalProfile, User, Vertical, Workspace
from app.services import TokenService


async def signup(client: AsyncClient, email: str) -> dict[str, object]:
    response = await client.post(
        "/auth/signup",
        json={"email": email, "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_signup_creates_default_account_graph(
    client: AsyncClient, session: AsyncSession
) -> None:
    await signup(client, "graph@example.com")

    user = await session.scalar(select(User).where(User.email == "graph@example.com"))
    assert user is not None
    assert user.password_hash.startswith("$argon2")
    membership = await session.scalar(
        select(Membership).where(Membership.user_id == user.id)
    )
    assert membership is not None
    workspace = await session.get(Workspace, membership.workspace_id)
    assert workspace is not None
    assert workspace.language == "en"
    profile = await session.scalar(
        select(ProfessionalProfile).where(
            ProfessionalProfile.membership_id == membership.id
        )
    )
    assert profile is not None
    vertical = await session.get(Vertical, profile.vertical_id)
    assert vertical is not None
    assert vertical.slug == "real_estate"
    assert profile.role == "buyers_agent"


async def test_login_and_refresh_round_trip(client: AsyncClient) -> None:
    await signup(client, "roundtrip@example.com")
    login_response = await client.post(
        "/auth/login",
        json={
            "email": "ROUNDTRIP@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert login_response.status_code == 200
    login_tokens = login_response.json()
    token_service = TokenService(get_settings())
    access_claims = token_service.decode(login_tokens["access_token"], "access")
    refresh_claims = token_service.decode(login_tokens["refresh_token"], "refresh")
    assert access_claims.exp - access_claims.iat == timedelta(minutes=15)
    assert refresh_claims.exp - refresh_claims.iat == timedelta(days=30)

    me_response = await client.get(
        "/me",
        headers={"Authorization": f"Bearer {login_tokens['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["user"]["email"] == "roundtrip@example.com"
    assert me_response.json()["workspace"]["language"] == "en"
    assert me_response.json()["profile"] == {
        "id": me_response.json()["profile"]["id"],
        "role": "buyers_agent",
        "vertical": "real_estate",
    }

    refresh_response = await client.post(
        "/auth/refresh",
        json={"refresh_token": login_tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    refreshed_tokens = refresh_response.json()
    assert refreshed_tokens["access_token"] != login_tokens["access_token"]
    assert refreshed_tokens["refresh_token"] != login_tokens["refresh_token"]

    refreshed_me = await client.get(
        "/me",
        headers={"Authorization": f"Bearer {refreshed_tokens['access_token']}"},
    )
    assert refreshed_me.status_code == 200


async def test_patch_me_updates_name_and_returns_account_graph(
    client: AsyncClient,
) -> None:
    tokens = await signup(client, "profile-update@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    updated = await client.patch("/me", headers=headers, json={"name": "Riley Chen"})

    assert updated.status_code == 200, updated.text
    assert updated.json()["user"]["name"] == "Riley Chen"
    assert updated.json()["user"]["email"] == "profile-update@example.com"
    assert updated.json()["workspace"]["language"] == "en"
    assert updated.json()["profile"]["vertical"] == "real_estate"
    fetched = await client.get("/me", headers=headers)
    assert fetched.json()["user"]["name"] == "Riley Chen"


async def test_cross_workspace_context_returns_not_found(client: AsyncClient) -> None:
    first_tokens = await signup(client, "first@example.com")
    second_tokens = await signup(client, "second@example.com")

    first_me = await client.get(
        "/me",
        headers={"Authorization": f"Bearer {first_tokens['access_token']}"},
    )
    second_me = await client.get(
        "/me",
        headers={"Authorization": f"Bearer {second_tokens['access_token']}"},
    )
    first_user_id = uuid.UUID(first_me.json()["user"]["id"])
    second_workspace_id = uuid.UUID(second_me.json()["workspace"]["id"])

    cross_workspace_token = (
        TokenService(get_settings())
        .create_pair(first_user_id, second_workspace_id)
        .access_token
    )
    response = await client.get(
        "/me",
        headers={"Authorization": f"Bearer {cross_workspace_token}"},
    )

    assert response.status_code == 404
    update_response = await client.patch(
        "/me",
        headers={"Authorization": f"Bearer {cross_workspace_token}"},
        json={"name": "Cross workspace"},
    )
    assert update_response.status_code == 404
