import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import AuthSession
from app.services import TokenService
from app.services.auth import refresh_token_hash

PASSWORD = "correct-horse-battery-staple"


async def _signup(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/auth/signup", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _login(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _session_for(session: AsyncSession, tokens: dict[str, str]) -> AuthSession:
    row = await session.scalar(
        select(AuthSession).where(
            AuthSession.refresh_token_hash
            == refresh_token_hash(tokens["refresh_token"])
        )
    )
    assert row is not None
    return row


async def test_only_the_hash_of_a_refresh_token_is_stored(
    client: AsyncClient, session: AsyncSession
) -> None:
    tokens = await _signup(client, "hashed@example.com")

    stored = await _session_for(session, tokens)

    # A database copy must not be replayable as working credentials.
    assert tokens["refresh_token"] not in stored.refresh_token_hash
    assert stored.refresh_token_hash != tokens["refresh_token"]


async def test_logout_revokes_the_session_and_refresh_stops_working(
    client: AsyncClient, session: AsyncSession
) -> None:
    tokens = await _signup(client, "logout@example.com")

    logout = await client.post(
        "/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert logout.status_code == 204

    stored = await _session_for(session, tokens)
    await session.refresh(stored)
    assert stored.revoked_at is not None

    refused = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refused.status_code == 401


async def test_a_stolen_refresh_token_is_worthless_once_the_user_logs_out(
    client: AsyncClient,
) -> None:
    tokens = await _signup(client, "stolen@example.com")
    stolen = tokens["refresh_token"]

    # The thief holds a working token right up until the victim signs out.
    assert (
        await client.post("/auth/refresh", json={"refresh_token": stolen})
    ).status_code == 200
    await client.post("/auth/logout", json={"refresh_token": stolen})

    assert (
        await client.post("/auth/refresh", json={"refresh_token": stolen})
    ).status_code == 401


async def test_a_revoked_session_cannot_use_its_unexpired_access_token(
    client: AsyncClient,
) -> None:
    tokens = await _signup(client, "immediate@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (await client.get("/me", headers=headers)).status_code == 200

    await client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})

    # The access token is still within its 15 minutes, but the session behind
    # it is gone, so revocation takes effect now rather than whenever the token
    # happens to lapse.
    assert (await client.get("/me", headers=headers)).status_code == 401


async def test_refreshing_does_not_extend_the_absolute_expiry(
    client: AsyncClient, session: AsyncSession
) -> None:
    tokens = await _signup(client, "absolute@example.com")
    stored = await _session_for(session, tokens)
    original_expiry = stored.expires_at

    for _ in range(3):
        refreshed = await client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert refreshed.status_code == 200

    await session.refresh(stored)
    # Continuous use must not buy more life, or a stolen token in active use
    # would never expire at all.
    assert stored.expires_at == original_expiry


async def test_a_session_past_its_absolute_expiry_cannot_refresh(
    client: AsyncClient, session: AsyncSession
) -> None:
    tokens = await _signup(client, "expired@example.com")
    stored = await _session_for(session, tokens)

    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()

    refused = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refused.status_code == 401


async def test_signing_out_one_device_leaves_the_other_signed_in(
    client: AsyncClient,
) -> None:
    await _signup(client, "devices@example.com")
    phone = await _login(client, "devices@example.com")
    laptop = await _login(client, "devices@example.com")
    assert phone["refresh_token"] != laptop["refresh_token"]

    await client.post("/auth/logout", json={"refresh_token": phone["refresh_token"]})

    assert (
        await client.post(
            "/auth/refresh", json={"refresh_token": phone["refresh_token"]}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/auth/refresh", json={"refresh_token": laptop["refresh_token"]}
        )
    ).status_code == 200


async def test_one_users_session_cannot_refresh_into_another_workspace(
    client: AsyncClient, session: AsyncSession
) -> None:
    first = await _signup(client, "tenant-one@example.com")
    second = await _signup(client, "tenant-two@example.com")

    first_session = await _session_for(session, first)
    second_session = await _session_for(session, second)
    assert first_session.workspace_id != second_session.workspace_id

    refreshed = await client.post(
        "/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    me = await client.get(
        "/me",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    # A refresh resolves the workspace from its own session row, never from
    # anything the caller supplies.
    assert me.json()["workspace"]["id"] == str(first_session.workspace_id)
    assert me.json()["workspace"]["id"] != str(second_session.workspace_id)


async def test_parallel_refreshes_all_succeed_on_the_same_token(
    client: AsyncClient, session: AsyncSession
) -> None:
    tokens = await _signup(client, "parallel@example.com")
    stored = await _session_for(session, tokens)
    original_expiry = stored.expires_at

    responses = await asyncio.gather(
        *(
            client.post(
                "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
            )
            for _ in range(5)
        )
    )

    # Not rotating is what makes this safe: five dashboard tabs refreshing at
    # once cannot invalidate each other's token.
    assert [response.status_code for response in responses] == [200] * 5
    assert {response.json()["refresh_token"] for response in responses} == {
        tokens["refresh_token"]
    }
    await session.refresh(stored)
    assert stored.expires_at == original_expiry


async def test_logging_out_an_unknown_token_still_succeeds(
    client: AsyncClient,
) -> None:
    # A client must never be blocked from clearing its own credentials, and a
    # rejection here would also reveal which tokens exist.
    response = await client.post(
        "/auth/logout", json={"refresh_token": "not-a-real-token"}
    )

    assert response.status_code == 204


async def test_a_legacy_stateless_refresh_token_is_refused(
    client: AsyncClient,
) -> None:
    # Pre-launch tokens were signed JWTs with no session behind them. They are
    # abandoned rather than adopted, forcing one clean sign-in.
    legacy, _ = TokenService(get_settings()).issue_access_token(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    )

    refused = await client.post("/auth/refresh", json={"refresh_token": legacy})

    assert refused.status_code == 401


@pytest.mark.parametrize("token", ["", " ", "x" * 500])
async def test_malformed_refresh_tokens_are_refused_cleanly(
    client: AsyncClient, token: str
) -> None:
    response = await client.post("/auth/refresh", json={"refresh_token": token})

    assert response.status_code in {401, 422}
