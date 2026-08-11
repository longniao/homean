import uuid

from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_context
from app.models import Observation, RawMedia, Report, TranscriptSegment, Zone

PASSWORD = "correct-horse-battery-staple"


def _has_dependency(route: APIRoute, dependency: object) -> bool:
    pending = list(route.dependant.dependencies)
    while pending:
        item = pending.pop()
        if item.call is dependency:
            return True
        pending.extend(item.dependencies)
    return False


def test_every_non_public_route_requires_workspace_context(test_app) -> None:
    """Structural guard only; cross-tenant behavior is tested below with data."""
    from app.main import app

    del test_app
    public_prefixes = ("/auth/", "/r/")
    public_paths = {
        "/health",
        "/ready",
        "/billing/webhook",
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
    }
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    assert routes
    for route in routes:
        if route.path in public_paths or route.path.startswith(public_prefixes):
            continue
        assert _has_dependency(route, get_current_context), route.path


async def test_authenticated_resource_families_are_cross_workspace_isolated(
    client: AsyncClient, session: AsyncSession
) -> None:
    async def signup(email: str) -> dict[str, str]:
        response = await client.post(
            "/auth/signup", json={"email": email, "password": PASSWORD}
        )
        assert response.status_code == 201
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    owner = await signup("scope-owner@example.com")
    foreign = await signup("scope-foreign@example.com")
    owner_me = (await client.get("/me", headers=owner)).json()
    foreign_me = (await client.get("/me", headers=foreign)).json()
    assert owner_me["workspace"]["id"] != foreign_me["workspace"]["id"]

    contact = await client.post(
        "/contacts", headers=owner, json={"name": "Owner Contact"}
    )
    subject = await client.post(
        "/properties",
        headers=owner,
        json={"display_name": "Owner Subject", "address": "1 Owner Lane"},
    )
    showing = await client.post(
        "/showings",
        headers=owner,
        json={"subject_id": subject.json()["id"], "contact_id": contact.json()["id"]},
    )
    assert showing.status_code == 201
    visit_id = uuid.UUID(showing.json()["id"])
    media = RawMedia(
        visit_id=visit_id,
        type="audio",
        object_key=f"scope/{visit_id}.m4a",
        content_type="audio/mp4",
        status="uploaded",
    )
    session.add(media)
    await session.flush()
    segment = TranscriptSegment(
        visit_id=visit_id,
        raw_media_id=media.id,
        text="Owner transcript",
        timestamp_start=0,
        timestamp_end=1,
    )
    session.add(segment)
    await session.flush()
    zone = Zone(
        visit_id=visit_id,
        zone_type="kitchen",
        position=0,
        start_transcript_segment_id=segment.id,
        end_transcript_segment_id=segment.id,
    )
    session.add(zone)
    await session.flush()
    observation = Observation(
        visit_id=visit_id,
        zone_id=zone.id,
        category="general",
        content="Owner observation",
        source_type="professional_edited",
        source_transcript_segment_id=segment.id,
        source_media_id=media.id,
        review_status="pending",
    )
    report = Report(
        visit_id=visit_id,
        template_id="real_estate_v1",
        content={
            "executive_summary": "Owner report",
            "room_by_room": [],
            "highlights": [],
            "concerns": [],
            "follow_ups": [],
        },
        status="pending_review",
    )
    session.add_all([observation, report])
    await session.commit()

    attempts = [
        await client.get(f"/contacts/{contact.json()['id']}", headers=foreign),
        await client.patch(
            f"/contacts/{contact.json()['id']}",
            headers=foreign,
            json={"name": "Leaked"},
        ),
        await client.get(f"/properties/{subject.json()['id']}", headers=foreign),
        await client.delete(f"/properties/{subject.json()['id']}", headers=foreign),
        await client.get(f"/showings/{visit_id}", headers=foreign),
        await client.post(
            f"/showings/{visit_id}/media/presign",
            headers=foreign,
            json={"type": "audio", "content_type": "audio/mp4"},
        ),
        await client.get(
            f"/showings/{visit_id}/media/{media.id}/download", headers=foreign
        ),
        await client.patch(
            f"/observations/{observation.id}",
            headers=foreign,
            json={"content": "Leaked"},
        ),
        await client.patch(
            f"/transcript-segments/{segment.id}",
            headers=foreign,
            json={"text": "Leaked"},
        ),
        await client.patch(
            f"/reports/{report.id}",
            headers=foreign,
            json={"content": report.content},
        ),
        await client.get(f"/showings/{visit_id}/delivery", headers=foreign),
        await client.post(
            f"/showings/{visit_id}/send",
            headers=foreign,
            json={"channel": "link_only"},
        ),
    ]
    assert {response.status_code for response in attempts} == {404}

    owner_billing = await client.get("/billing", headers=owner)
    foreign_billing = await client.get("/billing", headers=foreign)
    assert (
        owner_billing.json()["workspace_id"] != foreign_billing.json()["workspace_id"]
    )

    owner_branding = await client.put(
        "/branding", headers=owner, json={"display_name": "Owner Brand"}
    )
    assert owner_branding.status_code == 200
    foreign_branding = await client.get("/branding", headers=foreign)
    assert foreign_branding.json()["display_name"] != "Owner Brand"
    foreign_profile = await client.patch(
        "/me", headers=foreign, json={"name": "Foreign User"}
    )
    assert foreign_profile.status_code == 200
    assert (await client.get("/me", headers=owner)).json()["user"][
        "name"
    ] != "Foreign User"


# These are intentionally global and are not tenant-owned resource reads:
# auth email lookup, vertical configuration, and Stripe webhook subscription lookup.
