import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Visit
from app.pipeline import FakePipelineEnqueuer
from app.storage import FakeStorageProvider

PASSWORD = "correct-horse-battery-staple"


async def auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/auth/signup", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def create_contact(
    client: AsyncClient, headers: dict[str, str], name: str
) -> dict[str, object]:
    response = await client.post(
        "/contacts",
        headers=headers,
        json={
            "name": name,
            "email": f"{name.lower().replace(' ', '.')}@example.com",
            "phone": "+1-604-555-0100",
            "notes": "Prefers a quiet street",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_property(
    client: AsyncClient,
    headers: dict[str, str],
    display_name: str,
    address: str,
) -> dict[str, object]:
    response = await client.post(
        "/properties",
        headers=headers,
        json={
            "display_name": display_name,
            "address": address,
            "attributes": {
                "beds": 3,
                "baths": 2.5,
                "sqft": 1450,
                "listing_price": 1299000,
                "mls_id": "R1234567",
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_contact_and_property_crud(client: AsyncClient) -> None:
    headers = await auth_headers(client, "workspace-crud@example.com")

    contact = await create_contact(client, headers, "Taylor Buyer")
    contact_id = contact["id"]
    get_contact = await client.get(f"/contacts/{contact_id}", headers=headers)
    assert get_contact.status_code == 200
    update_contact = await client.patch(
        f"/contacts/{contact_id}",
        headers=headers,
        json={"phone": "+1-604-555-0199", "notes": "Updated notes"},
    )
    assert update_contact.status_code == 200
    assert update_contact.json()["phone"] == "+1-604-555-0199"
    assert contact_id in {
        item["id"] for item in (await client.get("/contacts", headers=headers)).json()
    }

    property_data = await create_property(
        client, headers, "Harbour Home", "101 Harbour Street, Vancouver"
    )
    subject_id = property_data["id"]
    assert property_data["attributes"]["baths"] == 2.5
    update_property = await client.patch(
        f"/properties/{subject_id}",
        headers=headers,
        json={"display_name": "Harbour Home Updated", "attributes": {"sqft": 1500}},
    )
    assert update_property.status_code == 200
    assert update_property.json()["display_name"] == "Harbour Home Updated"
    assert update_property.json()["attributes"]["beds"] == 3
    assert update_property.json()["attributes"]["sqft"] == 1500
    assert subject_id in {
        item["id"] for item in (await client.get("/properties", headers=headers)).json()
    }

    assert (
        await client.delete(f"/contacts/{contact_id}", headers=headers)
    ).status_code == 204
    assert (
        await client.delete(f"/properties/{subject_id}", headers=headers)
    ).status_code == 204


async def test_full_capture_happy_path(
    client: AsyncClient,
    storage: FakeStorageProvider,
    pipeline: FakePipelineEnqueuer,
) -> None:
    headers = await auth_headers(client, "capture-happy@example.com")
    contact = await create_contact(client, headers, "Morgan Buyer")
    property_data = await create_property(
        client, headers, "Maple Residence", "88 Maple Avenue, Burnaby"
    )

    create_response = await client.post(
        "/showings",
        headers=headers,
        json={"subject_id": property_data["id"], "contact_id": contact["id"]},
    )
    assert create_response.status_code == 201, create_response.text
    showing = create_response.json()
    visit_id = showing["id"]
    workspace_id = (await client.get("/me", headers=headers)).json()["workspace"]["id"]
    assert showing["status"] == "draft"
    assert showing["processing_status"] == "not_started"

    presign_response = await client.post(
        f"/showings/{visit_id}/media/presign",
        headers=headers,
        json={
            "type": "audio",
            "content_type": "audio/mp4",
            "timestamp_offset_ms": 1250,
        },
    )
    assert presign_response.status_code == 200, presign_response.text
    presign = presign_response.json()
    media_id = presign["media_id"]
    assert presign["method"] == "PUT"
    assert presign["headers"] == {"Content-Type": "audio/mp4"}
    assert presign["max_size_bytes"] == 500 * 1024 * 1024
    object_key = storage.presigned_puts[-1]
    assert object_key == f"{workspace_id}/{visit_id}/{media_id}.m4a"

    storage.put_object(object_key, "audio/mp4", 2 * 1024 * 1024)
    complete_response = await client.post(
        f"/showings/{visit_id}/media/{media_id}/complete", headers=headers
    )
    assert complete_response.status_code == 200, complete_response.text
    assert complete_response.json()["status"] == "uploaded"
    assert complete_response.json()["timestamp_offset_ms"] == 1250

    download_response = await client.get(
        f"/showings/{visit_id}/media/{media_id}/download", headers=headers
    )
    assert download_response.status_code == 200
    assert download_response.json()["download_url"].startswith(
        "https://storage.test/download/"
    )

    finish_response = await client.post(f"/showings/{visit_id}/finish", headers=headers)
    assert finish_response.status_code == 200, finish_response.text
    assert finish_response.json()["processing_status"] == "queued"
    assert finish_response.json()["ended_at"] is not None
    assert len(pipeline.jobs) == 1
    assert str(pipeline.jobs[0][0]) == visit_id
    assert str(pipeline.jobs[0][1]) == workspace_id

    detail_response = await client.get(f"/showings/{visit_id}", headers=headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["contact"]["id"] == contact["id"]
    assert detail["property"]["id"] == property_data["id"]
    assert detail["media"][0]["id"] == media_id
    assert "object_key" not in detail["media"][0]
    assert "storage_url" not in detail["media"][0]
    assert detail["zones"] == []
    assert detail["observations"] == []
    assert detail["transcript"] == []
    assert detail["report"] is None


async def test_subjectless_showing_can_be_created_listed_and_attached(
    client: AsyncClient,
) -> None:
    owner_headers = await auth_headers(client, "subjectless-owner@example.com")
    other_headers = await auth_headers(client, "subjectless-other@example.com")

    created = await client.post("/showings", headers=owner_headers, json={})
    assert created.status_code == 201, created.text
    visit_id = created.json()["id"]
    assert created.json()["property"] is None

    unassigned = await client.get(
        "/showings", headers=owner_headers, params={"unassigned": "true"}
    )
    assert [item["id"] for item in unassigned.json()["items"]] == [visit_id]

    other_property = await create_property(
        client, other_headers, "Other Workspace Home", "10 Private Street"
    )
    cross_tenant_subject = await client.patch(
        f"/showings/{visit_id}",
        headers=owner_headers,
        json={"subject_id": other_property["id"]},
    )
    cross_tenant_visit = await client.patch(
        f"/showings/{visit_id}",
        headers=other_headers,
        json={"address": "11 Leaked Street"},
    )
    assert cross_tenant_subject.status_code == 404
    assert cross_tenant_visit.status_code == 404

    owner_property = await create_property(
        client, owner_headers, "Owner Workspace Home", "54 Attached Avenue"
    )
    attached_existing = await client.patch(
        f"/showings/{visit_id}",
        headers=owner_headers,
        json={"subject_id": owner_property["id"]},
    )
    assert attached_existing.status_code == 200, attached_existing.text
    assert attached_existing.json()["property"]["id"] == owner_property["id"]

    attached_inline = await client.patch(
        f"/showings/{visit_id}",
        headers=owner_headers,
        json={"address": "55 Attached Avenue"},
    )
    assert attached_inline.status_code == 200, attached_inline.text
    assert attached_inline.json()["property"]["address"] == "55 Attached Avenue"

    assigned_only = await client.get(
        "/showings", headers=owner_headers, params={"unassigned": "true"}
    )
    assert assigned_only.json()["items"] == []


@pytest.mark.parametrize("visit_status", ["confirmed", "sent_to_client"])
async def test_capture_guards_non_draft_showings(
    client: AsyncClient,
    session: AsyncSession,
    storage: FakeStorageProvider,
    visit_status: str,
) -> None:
    headers = await auth_headers(client, f"guard-{visit_status}@example.com")
    showing_response = await client.post(
        "/showings",
        headers=headers,
        json={"address": f"1 {visit_status.title()} Way"},
    )
    visit_id = showing_response.json()["id"]
    presign = await client.post(
        f"/showings/{visit_id}/media/presign",
        headers=headers,
        json={"type": "photo", "content_type": "image/jpeg"},
    )
    media_id = presign.json()["media_id"]
    storage.put_object(storage.presigned_puts[-1], "image/jpeg", 1024)

    async with session.begin():
        await session.execute(
            update(Visit)
            .where(Visit.id == uuid.UUID(visit_id))
            .values(status=visit_status)
        )

    attach_response = await client.post(
        f"/showings/{visit_id}/media/presign",
        headers=headers,
        json={"type": "audio", "content_type": "audio/mpeg"},
    )
    complete_response = await client.post(
        f"/showings/{visit_id}/media/{media_id}/complete", headers=headers
    )
    finish_response = await client.post(f"/showings/{visit_id}/finish", headers=headers)
    property_update = await client.patch(
        f"/showings/{visit_id}",
        headers=headers,
        json={"address": f"2 Updated {visit_status.title()} Way"},
    )
    assert attach_response.status_code == 409
    assert complete_response.status_code == 409
    assert finish_response.status_code == 409
    assert property_update.status_code == (
        409 if visit_status == "sent_to_client" else 200
    )


async def test_media_validation_and_size_limit(
    client: AsyncClient, storage: FakeStorageProvider
) -> None:
    headers = await auth_headers(client, "media-validation@example.com")
    showing = await client.post(
        "/showings", headers=headers, json={"address": "25 Photo Lane"}
    )
    visit_id = showing.json()["id"]

    invalid_type = await client.post(
        f"/showings/{visit_id}/media/presign",
        headers=headers,
        json={"type": "photo", "content_type": "application/pdf"},
    )
    assert invalid_type.status_code == 422

    presign = await client.post(
        f"/showings/{visit_id}/media/presign",
        headers=headers,
        json={"type": "photo", "content_type": "image/jpeg"},
    )
    media_id = presign.json()["media_id"]
    storage.put_object(storage.presigned_puts[-1], "image/jpeg", 25 * 1024 * 1024 + 1)
    complete = await client.post(
        f"/showings/{visit_id}/media/{media_id}/complete", headers=headers
    )
    assert complete.status_code == 422


async def test_showing_cursor_pagination_and_filters(client: AsyncClient) -> None:
    headers = await auth_headers(client, "pagination@example.com")
    contact = await create_contact(client, headers, "Pagination Buyer")
    created: list[dict[str, object]] = []
    for index in range(5):
        payload: dict[str, object] = {"address": f"{index} Cursor Street"}
        if index == 2:
            payload["contact_id"] = contact["id"]
        response = await client.post("/showings", headers=headers, json=payload)
        assert response.status_code == 201
        created.append(response.json())

    collected_ids: list[str] = []
    cursor = None
    while True:
        params = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        page_response = await client.get("/showings", headers=headers, params=params)
        assert page_response.status_code == 200, page_response.text
        page = page_response.json()
        collected_ids.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert collected_ids == [item["id"] for item in reversed(created)]
    assert len(set(collected_ids)) == 5

    contact_filter = await client.get(
        "/showings",
        headers=headers,
        params={"contact_id": contact["id"]},
    )
    assert [item["id"] for item in contact_filter.json()["items"]] == [created[2]["id"]]
    subject_filter = await client.get(
        "/showings",
        headers=headers,
        params={"subject_id": created[1]["property"]["id"]},
    )
    assert [item["id"] for item in subject_filter.json()["items"]] == [created[1]["id"]]
    query_filter = await client.get(
        "/showings", headers=headers, params={"q": "Pagination Buyer"}
    )
    assert [item["id"] for item in query_filter.json()["items"]] == [created[2]["id"]]
    assert (
        await client.get("/showings", headers=headers, params={"cursor": "bad"})
    ).status_code == 422


async def test_workspace_isolation_on_capture_routes(
    client: AsyncClient, storage: FakeStorageProvider
) -> None:
    owner_headers = await auth_headers(client, "isolation-owner@example.com")
    other_headers = await auth_headers(client, "isolation-other@example.com")
    contact = await create_contact(client, owner_headers, "Private Buyer")
    property_data = await create_property(
        client, owner_headers, "Private Home", "99 Private Road"
    )
    showing_response = await client.post(
        "/showings",
        headers=owner_headers,
        json={"subject_id": property_data["id"], "contact_id": contact["id"]},
    )
    visit_id = showing_response.json()["id"]
    presign = await client.post(
        f"/showings/{visit_id}/media/presign",
        headers=owner_headers,
        json={"type": "audio", "content_type": "audio/mpeg"},
    )
    media_id = presign.json()["media_id"]

    assert contact["id"] not in {
        item["id"]
        for item in (await client.get("/contacts", headers=other_headers)).json()
    }
    assert property_data["id"] not in {
        item["id"]
        for item in (await client.get("/properties", headers=other_headers)).json()
    }
    assert visit_id not in {
        item["id"]
        for item in (await client.get("/showings", headers=other_headers)).json()[
            "items"
        ]
    }

    isolated_requests = [
        await client.get(f"/contacts/{contact['id']}", headers=other_headers),
        await client.patch(
            f"/contacts/{contact['id']}", headers=other_headers, json={"notes": "x"}
        ),
        await client.delete(f"/contacts/{contact['id']}", headers=other_headers),
        await client.get(f"/properties/{property_data['id']}", headers=other_headers),
        await client.patch(
            f"/properties/{property_data['id']}",
            headers=other_headers,
            json={"display_name": "Leaked"},
        ),
        await client.delete(
            f"/properties/{property_data['id']}", headers=other_headers
        ),
        await client.post(
            "/showings",
            headers=other_headers,
            json={"subject_id": property_data["id"]},
        ),
        await client.get(f"/showings/{visit_id}", headers=other_headers),
        await client.post(
            f"/showings/{visit_id}/media/presign",
            headers=other_headers,
            json={"type": "photo", "content_type": "image/jpeg"},
        ),
        await client.post(
            f"/showings/{visit_id}/media/{media_id}/complete",
            headers=other_headers,
        ),
        await client.get(
            f"/showings/{visit_id}/media/{media_id}/download",
            headers=other_headers,
        ),
        await client.post(f"/showings/{visit_id}/finish", headers=other_headers),
        await client.post(f"/showings/{visit_id}/reprocess", headers=other_headers),
    ]
    assert {response.status_code for response in isolated_requests} == {404}

    owner_detail = await client.get(f"/showings/{visit_id}", headers=owner_headers)
    assert owner_detail.status_code == 200
    assert owner_detail.json()["media"][0]["status"] == "pending"
    assert storage.presigned_gets == []
