from uuid import uuid4

import pytest
from httpx import AsyncClient

PASSWORD = "correct-horse-battery-staple"


async def auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/auth/signup", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_markers_create_and_list_in_timestamp_order(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client, "markers-happy@example.com")
    showing = await client.post(
        "/showings", headers=headers, json={"address": "12 Marker Lane"}
    )
    assert showing.status_code == 201, showing.text
    visit_id = showing.json()["id"]

    later = await client.post(
        f"/showings/{visit_id}/markers",
        headers=headers,
        json={"client_id": str(uuid4()), "timestamp_offset_ms": 4200},
    )
    earlier = await client.post(
        f"/showings/{visit_id}/markers",
        headers=headers,
        json={
            "client_id": str(uuid4()),
            "marker_type": "voice_tag",
            "timestamp_offset_ms": 1200,
        },
    )
    assert later.status_code == 201, later.text
    assert earlier.status_code == 201, earlier.text
    assert later.json()["marker_type"] == "voice_tag"
    assert later.json()["timestamp_offset_ms"] == 4200

    listed = await client.get(f"/showings/{visit_id}/markers", headers=headers)
    assert listed.status_code == 200, listed.text
    assert [marker["timestamp_offset_ms"] for marker in listed.json()] == [1200, 4200]
    assert [marker["id"] for marker in listed.json()] == [
        earlier.json()["id"],
        later.json()["id"],
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"timestamp_offset_ms": -1},
        {"timestamp_offset_ms": "not-a-number"},
        {"timestamp_offset_ms": "NaN"},
        {"timestamp_offset_ms": "Infinity"},
        {"timestamp_offset_ms": 0, "marker_type": "other"},
    ],
)
async def test_marker_input_validation(
    client: AsyncClient, payload: dict[str, object]
) -> None:
    headers = await auth_headers(client, f"marker-validation-{id(payload)}@example.com")
    showing = await client.post(
        "/showings", headers=headers, json={"address": "13 Marker Lane"}
    )
    visit_id = showing.json()["id"]
    response = await client.post(
        f"/showings/{visit_id}/markers", headers=headers, json=payload
    )
    assert response.status_code == 422, response.text


async def test_marker_create_requires_draft_state(client: AsyncClient, session) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import update

    from app.models import Visit

    headers = await auth_headers(client, "marker-state@example.com")
    showing = await client.post(
        "/showings", headers=headers, json={"address": "14 Marker Lane"}
    )
    visit_id = showing.json()["id"]
    from uuid import UUID

    async with session.begin():
        await session.execute(
            update(Visit).where(Visit.id == UUID(visit_id)).values(status="confirmed")
        )

    create_response = await client.post(
        f"/showings/{visit_id}/markers",
        headers=headers,
        json={"client_id": str(uuid4()), "timestamp_offset_ms": 100},
    )
    assert create_response.status_code == 409, create_response.text


async def test_marker_workspace_isolation(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "marker-owner@example.com")
    other_headers = await auth_headers(client, "marker-other@example.com")
    showing = await client.post(
        "/showings", headers=owner_headers, json={"address": "15 Marker Lane"}
    )
    visit_id = showing.json()["id"]
    created = await client.post(
        f"/showings/{visit_id}/markers",
        headers=owner_headers,
        json={"client_id": str(uuid4()), "timestamp_offset_ms": 800},
    )
    assert created.status_code == 201

    foreign_list = await client.get(
        f"/showings/{visit_id}/markers", headers=other_headers
    )
    foreign_create = await client.post(
        f"/showings/{visit_id}/markers",
        headers=other_headers,
        json={"client_id": str(uuid4()), "timestamp_offset_ms": 900},
    )
    assert foreign_list.status_code == 404
    assert foreign_create.status_code == 404

    owner_list = await client.get(
        f"/showings/{visit_id}/markers", headers=owner_headers
    )
    assert [marker["id"] for marker in owner_list.json()] == [created.json()["id"]]


async def test_marker_retry_with_same_client_id_is_idempotent(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client, "marker-idempotency@example.com")
    showing = await client.post(
        "/showings", headers=headers, json={"address": "16 Marker Lane"}
    )
    visit_id = showing.json()["id"]
    client_id = str(uuid4())
    payload = {"client_id": client_id, "timestamp_offset_ms": 2300}

    first = await client.post(
        f"/showings/{visit_id}/markers", headers=headers, json=payload
    )
    retry = await client.post(
        f"/showings/{visit_id}/markers", headers=headers, json=payload
    )

    assert first.status_code == 201, first.text
    assert retry.status_code == 201, retry.text
    assert retry.json() == first.json()
    listed = await client.get(f"/showings/{visit_id}/markers", headers=headers)
    assert len(listed.json()) == 1

    conflicting = await client.post(
        f"/showings/{visit_id}/markers",
        headers=headers,
        json={"client_id": client_id, "timestamp_offset_ms": 2400},
    )
    assert conflicting.status_code == 409, conflicting.text
