import asyncio
import copy
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.email import (
    EmailDeliveryError,
    EmailDeliveryOutcome,
    FakeEmailProvider,
)
from app.models import (
    Observation,
    RawMedia,
    Report,
    ReportRevision,
    ReportSend,
    ReportShareLink,
    ReportShareView,
    TranscriptSegment,
    Visit,
    WorkspaceBranding,
    Zone,
)
from app.repositories.auth import AuthRepository
from app.repositories.pipeline import PipelineRepository
from app.services.billing import BillingService, FakeBillingProvider
from app.services.context import CurrentContext
from app.services.delivery import (
    EmailDeliveryInProgressError,
    EmailDeliveryOutcomeUnknownError,
    RealEstateDeliveryService,
)
from app.services.exceptions import ResourceConflictError
from app.services.renderer import ReportRenderer
from app.services.review import RealEstateReviewService
from app.storage import FakeStorageProvider
from app.verticals import VerticalConfigService

PASSWORD = "correct-horse-battery-staple"


@dataclass(frozen=True)
class ReviewScenario:
    headers: dict[str, str]
    workspace_id: uuid.UUID
    visit_id: uuid.UUID
    zone_id: uuid.UUID
    segment_id: uuid.UUID
    ordinary_id: uuid.UUID
    sensitive_id: uuid.UUID
    report_id: uuid.UUID


async def _scenario(
    client: AsyncClient,
    session: AsyncSession,
    email: str,
    address: str | None = "88 Review Crescent",
) -> ReviewScenario:
    signup = await client.post(
        "/auth/signup", json={"email": email, "password": PASSWORD}
    )
    assert signup.status_code == 201, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    me = (await client.get("/me", headers=headers)).json()
    workspace_id = uuid.UUID(me["workspace"]["id"])
    showing = await client.post(
        "/showings",
        headers=headers,
        json={"address": address} if address is not None else {},
    )
    assert showing.status_code == 201, showing.text
    visit_id = uuid.UUID(showing.json()["id"])

    media = RawMedia(
        visit_id=visit_id,
        type="audio",
        object_key=f"{workspace_id}/{visit_id}/review.m4a",
        content_type="audio/mp4",
        status="uploaded",
        size_bytes=2048,
    )
    session.add(media)
    await session.flush()
    segment = TranscriptSegment(
        visit_id=visit_id,
        raw_media_id=media.id,
        text="The kitchen is bright but the seller is hiding cabinet damage.",
        timestamp_start=0,
        timestamp_end=5.2,
        confidence=0.91,
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
    ordinary_id = uuid.uuid4()
    sensitive_id = uuid.uuid4()
    observations = [
        Observation(
            id=ordinary_id,
            visit_id=visit_id,
            zone_id=zone.id,
            category="pro",
            content="The kitchen has strong natural light.",
            source_type="ai_generated",
            source_transcript_segment_id=segment.id,
            source_media_id=media.id,
            timestamp_start=0,
            timestamp_end=2.4,
            ai_model="claude-opus-4-8",
            prompt_version="re_v1",
            confidence=0.93,
            flags={},
            review_status="pending",
        ),
        Observation(
            id=sensitive_id,
            visit_id=visit_id,
            zone_id=zone.id,
            category="concern",
            content="The seller is hiding cabinet damage.",
            source_type="ai_generated",
            source_transcript_segment_id=segment.id,
            source_media_id=media.id,
            timestamp_start=2.5,
            timestamp_end=5.2,
            ai_model="claude-opus-4-8",
            prompt_version="re_v1",
            confidence=0.84,
            flags={
                "sensitive": True,
                "reason": "Speculates about intent.",
                "suggested_rewrite": "Cabinet damage is visible beside the sink.",
            },
            review_status="pending",
        ),
    ]
    report = Report(
        visit_id=visit_id,
        template_id="real_estate_v1",
        status="pending_review",
        content={
            "executive_summary": "Bright kitchen with cabinet wear to review.",
            "room_by_room": [
                {
                    "zone_id": str(zone.id),
                    "zone_type": "kitchen",
                    "bullets": [
                        {
                            "text": "Strong natural light.",
                            "observation_ids": [str(ordinary_id)],
                        }
                    ],
                }
            ],
            "highlights": [
                {
                    "text": "Strong natural light.",
                    "observation_ids": [str(ordinary_id)],
                }
            ],
            "concerns": [
                {
                    "text": "Cabinet wear.",
                    "observation_ids": [str(sensitive_id)],
                }
            ],
            "follow_ups": [],
        },
    )
    session.add_all([*observations, report])
    await session.commit()
    return ReviewScenario(
        headers=headers,
        workspace_id=workspace_id,
        visit_id=visit_id,
        zone_id=zone.id,
        segment_id=segment.id,
        ordinary_id=ordinary_id,
        sensitive_id=sensitive_id,
        report_id=report.id,
    )


def _edited_report_content(
    scenario: ReviewScenario,
    *,
    observation_id: uuid.UUID | None = None,
    zone_id: uuid.UUID | None = None,
) -> dict[str, object]:
    primary_observation_id = observation_id or scenario.ordinary_id
    report_zone_id = zone_id or scenario.zone_id
    primary_reference = str(primary_observation_id)
    return {
        "executive_summary": "Agent-updated report summary.",
        "room_by_room": [
            {
                "zone_id": str(report_zone_id),
                "zone_type": "kitchen",
                "bullets": [
                    {
                        "text": "Strong natural light.",
                        "observation_ids": [primary_reference],
                    }
                ],
            }
        ],
        "highlights": [
            {
                "text": "Strong natural light.",
                "observation_ids": [primary_reference],
            }
        ],
        "concerns": [
            {
                "text": "Cabinet wear.",
                "observation_ids": [str(scenario.sensitive_id)],
            }
        ],
        "follow_ups": [
            {
                "text": "Review the cabinet condition.",
                "observation_ids": [primary_reference],
            }
        ],
    }


async def _same_workspace_evidence(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[str, str],
    workspace_id: uuid.UUID,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    showing = await client.post(
        "/showings",
        headers=headers,
        json={"address": "19 Evidence Lane"},
    )
    assert showing.status_code == 201, showing.text
    visit_id = uuid.UUID(showing.json()["id"])
    media = RawMedia(
        visit_id=visit_id,
        type="audio",
        object_key=f"{workspace_id}/{visit_id}/evidence.m4a",
        content_type="audio/mp4",
        status="uploaded",
        size_bytes=2048,
    )
    session.add(media)
    await session.flush()
    segment = TranscriptSegment(
        visit_id=visit_id,
        raw_media_id=media.id,
        text="The second visit has a bright kitchen.",
        timestamp_start=0,
        timestamp_end=3,
        confidence=0.9,
    )
    zone = Zone(visit_id=visit_id, zone_type="kitchen", position=0)
    session.add_all([segment, zone])
    await session.flush()
    observation = Observation(
        visit_id=visit_id,
        zone_id=zone.id,
        category="pro",
        content="The second visit has strong natural light.",
        source_type="ai_generated",
        source_transcript_segment_id=segment.id,
        source_media_id=media.id,
        timestamp_start=0,
        timestamp_end=3,
        ai_model="test-model",
        prompt_version="re_v1",
        confidence=0.9,
        flags={},
        review_status="pending",
    )
    session.add(observation)
    await session.commit()
    return visit_id, zone.id, observation.id


async def _same_visit_other_zone_evidence(
    session: AsyncSession, scenario: ReviewScenario
) -> tuple[uuid.UUID, uuid.UUID]:
    zone = Zone(
        visit_id=scenario.visit_id,
        zone_type="living_room",
        position=1,
    )
    session.add(zone)
    await session.flush()
    observation = Observation(
        visit_id=scenario.visit_id,
        zone_id=zone.id,
        category="pro",
        content="The living room has generous natural light.",
        source_type="ai_generated",
        source_transcript_segment_id=scenario.segment_id,
        timestamp_start=0,
        timestamp_end=2,
        ai_model="test-model",
        prompt_version="re_v1",
        confidence=0.9,
        flags={},
        review_status="pending",
    )
    session.add(observation)
    await session.commit()
    return zone.id, observation.id


async def _visit_level_evidence(
    session: AsyncSession, scenario: ReviewScenario
) -> uuid.UUID:
    observation = Observation(
        visit_id=scenario.visit_id,
        zone_id=None,
        category="noise",
        content="Traffic noise is audible at the front entrance.",
        source_type="ai_generated",
        source_transcript_segment_id=scenario.segment_id,
        timestamp_start=0,
        timestamp_end=2,
        ai_model="test-model",
        prompt_version="re_v1",
        confidence=0.9,
        flags={},
        review_status="pending",
    )
    session.add(observation)
    await session.commit()
    return observation.id


async def _confirm_scenario(client: AsyncClient, scenario: ReviewScenario) -> None:
    ordinary = await client.post(
        f"/observations/{scenario.ordinary_id}/confirm", headers=scenario.headers
    )
    assert ordinary.status_code == 200, ordinary.text
    sensitive = await client.patch(
        f"/observations/{scenario.sensitive_id}",
        headers=scenario.headers,
        json={"content": "Cabinet damage is visible beside the sink."},
    )
    assert sensitive.status_code == 200, sensitive.text
    confirmation = await client.post(
        f"/showings/{scenario.visit_id}/confirm", headers=scenario.headers
    )
    assert confirmation.status_code == 200, confirmation.text


async def test_report_edit_accepts_visit_evidence_and_can_be_confirmed(
    client: AsyncClient, session: AsyncSession
) -> None:
    scenario = await _scenario(client, session, "report-evidence-valid@example.com")
    content = _edited_report_content(scenario)

    edited = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={"content": content},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["content"] == content

    await _confirm_scenario(client, scenario)
    report = await session.get(Report, scenario.report_id)
    assert report is not None
    await session.refresh(report)
    assert report.status == "confirmed"
    assert report.content == content


async def test_report_edit_rejects_dangling_observation_reference(
    client: AsyncClient, session: AsyncSession
) -> None:
    scenario = await _scenario(client, session, "report-evidence-dangling@example.com")
    invalid_content = _edited_report_content(scenario, observation_id=uuid.uuid4())

    rejected = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={"content": invalid_content},
    )
    assert rejected.status_code == 404
    revisions = await client.get(
        f"/reports/{scenario.report_id}/revisions", headers=scenario.headers
    )
    assert revisions.status_code == 200
    assert revisions.json() == []


async def test_report_edit_rejects_cross_visit_evidence_and_zone(
    client: AsyncClient, session: AsyncSession
) -> None:
    scenario = await _scenario(
        client, session, "report-evidence-cross-visit@example.com"
    )
    _, other_zone_id, other_observation_id = await _same_workspace_evidence(
        client, session, scenario.headers, scenario.workspace_id
    )

    cross_visit_observation = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={
            "content": _edited_report_content(
                scenario, observation_id=other_observation_id
            )
        },
    )
    assert cross_visit_observation.status_code == 404

    cross_visit_zone = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={"content": _edited_report_content(scenario, zone_id=other_zone_id)},
    )
    assert cross_visit_zone.status_code == 404


async def test_report_edit_rejects_cross_zone_room_evidence(
    client: AsyncClient, session: AsyncSession
) -> None:
    scenario = await _scenario(
        client, session, "report-evidence-cross-zone@example.com"
    )
    _, other_zone_observation_id = await _same_visit_other_zone_evidence(
        session, scenario
    )

    content = _edited_report_content(scenario, observation_id=other_zone_observation_id)
    rejected = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={"content": content},
    )

    assert rejected.status_code == 422
    assert rejected.json()["detail"] == (
        "room evidence must reference observations from the same zone"
    )
    revisions = await client.get(
        f"/reports/{scenario.report_id}/revisions", headers=scenario.headers
    )
    assert revisions.status_code == 200
    assert revisions.json() == []


async def test_report_edit_keeps_visit_level_evidence_out_of_rooms(
    client: AsyncClient, session: AsyncSession
) -> None:
    scenario = await _scenario(
        client, session, "report-evidence-visit-level@example.com"
    )
    visit_level_id = await _visit_level_evidence(session, scenario)
    content = _edited_report_content(scenario)
    content["highlights"] = [
        {
            "text": "Traffic noise was noted at the entrance.",
            "observation_ids": [str(visit_level_id)],
        }
    ]

    accepted = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={"content": content},
    )
    assert accepted.status_code == 200, accepted.text

    room_content = copy.deepcopy(content)
    room_content["room_by_room"][0]["bullets"][0]["observation_ids"] = [
        str(visit_level_id)
    ]
    rejected = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={"content": room_content},
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == (
        "room evidence must reference observations from the same zone"
    )

    null_room_content = copy.deepcopy(content)
    null_room_content["room_by_room"] = [
        {
            "zone_id": None,
            "zone_type": None,
            "bullets": [
                {
                    "text": "Traffic noise was noted at the entrance.",
                    "observation_ids": [str(visit_level_id)],
                }
            ],
        }
    ]
    null_room = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={"content": null_room_content},
    )
    assert null_room.status_code == 422
    assert null_room.json()["detail"] == (
        "room_by_room entries must reference a visit zone; "
        "put visit-level observations in highlights, concerns, or follow-ups"
    )


async def test_report_edit_rejects_cross_workspace_evidence(
    client: AsyncClient, session: AsyncSession
) -> None:
    scenario = await _scenario(client, session, "report-evidence-owner@example.com")
    other = await _scenario(client, session, "report-evidence-foreign@example.com")

    rejected = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={
            "content": _edited_report_content(
                scenario, observation_id=other.ordinary_id
            )
        },
    )
    assert rejected.status_code == 404


async def test_report_edit_rejects_zone_from_another_workspace(
    client: AsyncClient, session: AsyncSession
) -> None:
    scenario = await _scenario(
        client, session, "report-evidence-zone-owner@example.com"
    )
    other = await _scenario(client, session, "report-evidence-zone-foreign@example.com")

    rejected = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={"content": _edited_report_content(scenario, zone_id=other.zone_id)},
    )
    assert rejected.status_code == 404


async def test_confirmation_requires_property_then_succeeds_after_attachment(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    scenario = await _scenario(
        client,
        session,
        "review-subjectless@example.com",
        address=None,
    )
    ordinary = await client.post(
        f"/observations/{scenario.ordinary_id}/confirm", headers=scenario.headers
    )
    sensitive = await client.patch(
        f"/observations/{scenario.sensitive_id}",
        headers=scenario.headers,
        json={"content": "Cabinet damage is visible beside the sink."},
    )
    assert ordinary.status_code == 200
    assert sensitive.status_code == 200

    blocked = await client.post(
        f"/showings/{scenario.visit_id}/confirm", headers=scenario.headers
    )
    assert blocked.status_code == 422
    assert blocked.json() == {
        "detail": "attach a property before confirming",
        "code": "property_required",
    }

    attached = await client.patch(
        f"/showings/{scenario.visit_id}",
        headers=scenario.headers,
        json={"address": "77 Confirmation Court"},
    )
    assert attached.status_code == 200, attached.text
    assert attached.json()["property"]["address"] == "77 Confirmation Court"

    confirmed = await client.post(
        f"/showings/{scenario.visit_id}/confirm", headers=scenario.headers
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["visit_status"] == "confirmed"


async def test_review_editing_and_confirmation_gates(
    client: AsyncClient, session: AsyncSession
) -> None:
    scenario = await _scenario(client, session, "review-gates@example.com")

    no_review = await client.post(
        f"/showings/{scenario.visit_id}/confirm", headers=scenario.headers
    )
    assert no_review.status_code == 422
    assert "at least one observation" in no_review.json()["detail"]

    confirmed_observation = await client.post(
        f"/observations/{scenario.ordinary_id}/confirm", headers=scenario.headers
    )
    assert confirmed_observation.status_code == 200
    assert confirmed_observation.json()["review_status"] == "confirmed"

    sensitive_gate = await client.post(
        f"/showings/{scenario.visit_id}/confirm", headers=scenario.headers
    )
    assert sensitive_gate.status_code == 422
    assert sensitive_gate.json()["offending_observation_ids"] == [
        str(scenario.sensitive_id)
    ]

    edited = await client.patch(
        f"/observations/{scenario.sensitive_id}",
        headers=scenario.headers,
        json={
            "content": "Cabinet damage is visible beside the sink.",
            "category": "condition",
            "zone_id": None,
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["source_type"] == "professional_edited"
    assert edited.json()["review_status"] == "edited"
    assert edited.json()["zone_id"] is None
    assert edited.json()["reviewed_by"] is not None

    first_correction = await client.patch(
        f"/transcript-segments/{scenario.segment_id}",
        headers=scenario.headers,
        json={"text": "The kitchen is bright and cabinet damage is visible."},
    )
    assert first_correction.status_code == 200, first_correction.text
    original = first_correction.json()["original_text"]
    second_correction = await client.patch(
        f"/transcript-segments/{scenario.segment_id}",
        headers=scenario.headers,
        json={"text": "The kitchen is bright; cabinet wear is visible."},
    )
    assert second_correction.json()["original_text"] == original

    invalid_report = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={
            "content": {
                "executive_summary": "Invalid extra field.",
                "unexpected": True,
            }
        },
    )
    assert invalid_report.status_code == 422

    valid_report = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={
            "content": {
                "executive_summary": "Agent-updated report summary.",
                "room_by_room": [],
                "highlights": [],
                "concerns": [],
                "follow_ups": [],
            }
        },
    )
    assert valid_report.status_code == 200
    assert valid_report.json()["content"]["executive_summary"] == (
        "Agent-updated report summary."
    )

    manual = await client.post(
        "/observations",
        headers=scenario.headers,
        json={
            "visit_id": str(scenario.visit_id),
            "content": "Agent noted a recently replaced faucet.",
            "category": "pro",
            "zone_id": str(scenario.zone_id),
            "source_transcript_segment_id": str(scenario.segment_id),
        },
    )
    assert manual.status_code == 201, manual.text
    assert manual.json()["source_type"] == "professional_edited"
    assert manual.json()["source_media_id"] is not None
    dismissed = await client.post(
        f"/observations/{manual.json()['id']}/dismiss", headers=scenario.headers
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["review_status"] == "dismissed"

    confirmation = await client.post(
        f"/showings/{scenario.visit_id}/confirm", headers=scenario.headers
    )
    assert confirmation.status_code == 200, confirmation.text
    assert confirmation.json()["visit_status"] == "confirmed"
    report = await session.get(Report, scenario.report_id)
    await session.refresh(report)
    assert report is not None
    assert report.status == "confirmed"
    assert "<!doctype html>" in (report.rendered_html or "")
    assert "Showing report" in (report.rendered_html or "")


async def test_branding_and_private_logo_upload(
    client: AsyncClient, session: AsyncSession, storage: FakeStorageProvider
) -> None:
    scenario = await _scenario(client, session, "branding@example.com")
    empty = await client.get("/branding", headers=scenario.headers)
    assert empty.status_code == 200
    assert empty.json()["accent_color"] == "#1F6F5B"

    updated = await client.put(
        "/branding",
        headers=scenario.headers,
        json={
            "display_name": "Riley Chen, PREC",
            "phone": "+1-604-555-0123",
            "email": "riley@example.com",
            "license_no": "BC-12345",
            "accent_color": "#146C5A",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["display_name"] == "Riley Chen, PREC"
    assert updated.json()["accent_color"] == "#146C5A"

    presign = await client.post(
        "/branding/logo/presign",
        headers=scenario.headers,
        json={"content_type": "image/png"},
    )
    assert presign.status_code == 200, presign.text
    assert presign.json()["logo_key"].startswith(f"{scenario.workspace_id}/branding/")
    assert storage.presigned_puts[-1] == presign.json()["logo_key"]
    branding = await session.scalar(
        select(WorkspaceBranding).where(
            WorkspaceBranding.workspace_id == scenario.workspace_id
        )
    )
    assert branding is not None
    await session.refresh(branding)
    assert branding.logo_key == presign.json()["logo_key"]
    preview = await client.get("/branding/preview", headers=scenario.headers)
    assert preview.status_code == 200, preview.text
    assert preview.headers["content-type"].startswith("text/html")
    assert "Riley Chen, PREC" in preview.text
    assert "Large windows provide consistent natural light." in preview.text


async def test_share_links_public_views_revocation_and_expiry(
    client: AsyncClient, session: AsyncSession
) -> None:
    scenario = await _scenario(client, session, "share-links@example.com")
    await _confirm_scenario(client, scenario)
    share = await client.post(
        f"/showings/{scenario.visit_id}/share-links",
        headers=scenario.headers,
        json={"expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
    )
    assert share.status_code == 200, share.text
    token = share.json()["token"]
    assert len(token) >= 22

    public_html = await client.get(f"/r/{token}", headers={"User-Agent": "Buyer/1"})
    assert public_html.status_code == 200
    assert public_html.headers["content-type"].startswith("text/html")
    assert public_html.headers["cache-control"] == "private, no-store, max-age=0"
    assert public_html.headers["pragma"] == "no-cache"
    assert public_html.headers["x-robots-tag"] == "noindex, nofollow, noarchive"
    assert "Showing report" in public_html.text
    public_pdf = await client.get(f"/r/{token}/pdf", headers={"User-Agent": "Buyer/1"})
    assert public_pdf.status_code == 200
    assert public_pdf.content.startswith(b"%PDF")
    assert public_pdf.headers["cache-control"] == "private, no-store, max-age=0"
    assert public_pdf.headers["pragma"] == "no-cache"
    assert public_pdf.headers["x-robots-tag"] == "noindex, nofollow, noarchive"
    assert (
        await session.scalar(
            select(func.count())
            .select_from(ReportShareView)
            .where(ReportShareView.share_link_id == uuid.UUID(share.json()["id"]))
        )
        == 2
    )
    assert (await client.get("/r/not a token")).status_code == 404
    assert (await client.get("/r/é")).status_code == 404
    assert (await client.get(f"/r/{'a' * 129}")).status_code == 404
    assert (await client.get(f"/r/{token}/pdf")).status_code == 200

    revoked = await client.post(
        f"/showings/{scenario.visit_id}/share-links/{share.json()['id']}/revoke",
        headers=scenario.headers,
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
    revoked_response = await client.get(f"/r/{token}")
    assert revoked_response.status_code == 404
    assert revoked_response.headers["cache-control"] == "private, no-store, max-age=0"
    assert revoked_response.headers["x-robots-tag"] == "noindex, nofollow, noarchive"

    expiring = await client.post(
        f"/showings/{scenario.visit_id}/share-links",
        headers=scenario.headers,
        json={},
    )
    await session.execute(
        update(ReportShareLink)
        .where(ReportShareLink.id == uuid.UUID(expiring.json()["id"]))
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await session.commit()
    expired_response = await client.get(f"/r/{expiring.json()['token']}")
    assert expired_response.status_code == 404
    assert expired_response.headers["pragma"] == "no-cache"


async def test_email_and_link_delivery_transitions_and_sent_edit_guards(
    client: AsyncClient,
    session: AsyncSession,
    email_provider: FakeEmailProvider,
) -> None:
    scenario = await _scenario(client, session, "email-send@example.com")
    draft_send = await client.post(
        f"/showings/{scenario.visit_id}/send",
        headers=scenario.headers,
        json={"channel": "link_only"},
    )
    assert draft_send.status_code == 409
    await _confirm_scenario(client, scenario)

    sent = await client.post(
        f"/showings/{scenario.visit_id}/send",
        headers=scenario.headers,
        json={"channel": "email", "to_email": "buyer@example.com"},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["visit_status"] == "sent_to_client"
    assert len(email_provider.messages) == 1
    message = email_provider.messages[0]
    assert sent.json()["share_url"] in message.html_body
    assert message.attachment is not None
    assert message.attachment.content.startswith(b"%PDF")
    report_send = await session.get(ReportSend, uuid.UUID(sent.json()["send_id"]))
    assert report_send is not None
    await session.refresh(report_send)
    assert report_send.status == "sent"
    assert report_send.provider_message_id == "fake-1"

    token = sent.json()["share_url"].rsplit("/", 1)[-1]
    assert (await client.get(f"/r/{token}")).status_code == 200
    assert (await client.get(f"/r/{token}/pdf")).status_code == 200
    delivery = await client.get(
        f"/showings/{scenario.visit_id}/delivery", headers=scenario.headers
    )
    assert delivery.status_code == 200, delivery.text
    delivery_link = delivery.json()["share_links"][0]
    assert delivery.json()["share_links"] == [
        {
            "id": delivery_link["id"],
            "token": token,
            "url": sent.json()["share_url"],
            "created_at": delivery_link["created_at"],
            "expires_at": None,
            "revoked": False,
            "open_count": 2,
        }
    ]
    assert delivery.json()["sends"] == [
        {
            "send_id": sent.json()["send_id"],
            "channel": "email",
            "to_email": "buyer@example.com",
            "status": "sent",
            "attempt_count": 1,
            "last_attempt_at": delivery.json()["sends"][0]["last_attempt_at"],
            "sent_at": delivery.json()["sends"][0]["sent_at"],
            "error": None,
        }
    ]

    sent_guards = [
        await client.patch(
            f"/observations/{scenario.ordinary_id}",
            headers=scenario.headers,
            json={"content": "Cannot edit this."},
        ),
        await client.post(
            f"/observations/{scenario.ordinary_id}/confirm",
            headers=scenario.headers,
        ),
        await client.post(
            f"/observations/{scenario.ordinary_id}/dismiss",
            headers=scenario.headers,
        ),
        await client.post(
            "/observations",
            headers=scenario.headers,
            json={
                "visit_id": str(scenario.visit_id),
                "content": "Cannot add this.",
                "category": "general",
            },
        ),
        await client.patch(
            f"/transcript-segments/{scenario.segment_id}",
            headers=scenario.headers,
            json={"text": "Cannot edit this."},
        ),
        await client.patch(
            f"/reports/{scenario.report_id}",
            headers=scenario.headers,
            json={
                "content": {
                    "executive_summary": "Locked",
                    "room_by_room": [],
                    "highlights": [],
                    "concerns": [],
                    "follow_ups": [],
                }
            },
        ),
    ]
    assert {response.status_code for response in sent_guards} == {409}

    link_scenario = await _scenario(client, session, "link-send@example.com")
    await _confirm_scenario(client, link_scenario)
    link_only = await client.post(
        f"/showings/{link_scenario.visit_id}/send",
        headers=link_scenario.headers,
        json={"channel": "link_only"},
    )
    assert link_only.status_code == 200
    assert link_only.json()["visit_status"] == "sent_to_client"
    assert len(email_provider.messages) == 1


async def test_ambiguous_email_delivery_blocks_retry_and_preserves_one_link(
    client: AsyncClient,
    session: AsyncSession,
    email_provider: FakeEmailProvider,
) -> None:
    scenario = await _scenario(client, session, "email-outcome-unknown@example.com")
    await _confirm_scenario(client, scenario)
    email_provider.error_after_accept = EmailDeliveryError(
        "SMTP timeout after DATA", outcome=EmailDeliveryOutcome.OUTCOME_UNKNOWN
    )

    first = await client.post(
        f"/showings/{scenario.visit_id}/send",
        headers=scenario.headers,
        json={"channel": "email", "to_email": "buyer@example.com"},
    )
    assert first.status_code == 409
    assert first.json()["code"] == "email_delivery_outcome_unknown"
    assert len(email_provider.messages) == 1
    assert len(email_provider.attempts) == 1
    stable_message_id = email_provider.attempts[0].message_id

    delivery = await client.get(
        f"/showings/{scenario.visit_id}/delivery", headers=scenario.headers
    )
    assert delivery.status_code == 200
    assert len(delivery.json()["share_links"]) == 1
    assert delivery.json()["sends"][0]["status"] == "outcome_unknown"
    assert delivery.json()["sends"][0]["attempt_count"] == 1

    email_provider.error_after_accept = None
    retry = await client.post(
        f"/showings/{scenario.visit_id}/send",
        headers=scenario.headers,
        json={"channel": "email", "to_email": "buyer@example.com"},
    )
    assert retry.status_code == 409
    assert retry.json()["code"] == "email_delivery_outcome_unknown"
    assert len(email_provider.messages) == 1
    assert len(email_provider.attempts) == 1
    assert email_provider.attempts[0].message_id == stable_message_id

    unchanged = await client.get(
        f"/showings/{scenario.visit_id}/delivery", headers=scenario.headers
    )
    assert len(unchanged.json()["share_links"]) == 1
    assert unchanged.json()["sends"][0]["status"] == "outcome_unknown"


async def test_definitive_email_failure_retries_same_attempt_and_link(
    client: AsyncClient,
    session: AsyncSession,
    email_provider: FakeEmailProvider,
) -> None:
    scenario = await _scenario(client, session, "email-definitive-failure@example.com")
    await _confirm_scenario(client, scenario)
    email_provider.error = EmailDeliveryError(
        "SMTP rejected recipient", outcome=EmailDeliveryOutcome.DEFINITIVE_FAILURE
    )

    first = await client.post(
        f"/showings/{scenario.visit_id}/send",
        headers=scenario.headers,
        json={"channel": "email", "to_email": "buyer@example.com"},
    )
    assert first.status_code == 503
    assert len(email_provider.messages) == 0
    assert len(email_provider.attempts) == 1
    stable_message_id = email_provider.attempts[0].message_id

    failed_delivery = await client.get(
        f"/showings/{scenario.visit_id}/delivery", headers=scenario.headers
    )
    failed_send = failed_delivery.json()["sends"][0]
    failed_link = failed_delivery.json()["share_links"][0]
    assert failed_send["status"] == "failed"
    assert failed_send["attempt_count"] == 1

    email_provider.error = None
    retry = await client.post(
        f"/showings/{scenario.visit_id}/send",
        headers=scenario.headers,
        json={"channel": "email", "to_email": "buyer@example.com"},
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["send_id"] == failed_send["send_id"]
    assert retry.json()["share_url"] == failed_link["url"]
    assert len(email_provider.messages) == 1
    assert len(email_provider.attempts) == 2
    assert email_provider.attempts[1].message_id == stable_message_id

    sent_delivery = await client.get(
        f"/showings/{scenario.visit_id}/delivery", headers=scenario.headers
    )
    assert len(sent_delivery.json()["share_links"]) == 1
    sent_send = sent_delivery.json()["sends"][0]
    assert sent_send["status"] == "sent"
    assert sent_send["attempt_count"] == 2


async def test_stale_pending_email_is_quarantined_after_clock_controlled_crash(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    scenario = await _scenario(client, session, "email-stale-pending@example.com")
    await _confirm_scenario(client, scenario)

    me = await client.get("/me", headers=scenario.headers)
    assert me.status_code == 200
    context_data = await AuthRepository(session).get_context(
        uuid.UUID(me.json()["user"]["id"]), scenario.workspace_id
    )
    assert context_data is not None
    context = CurrentContext(*context_data)

    class FakePdfRenderer(ReportRenderer):
        async def render_pdf(self, html: str) -> bytes:
            return b"%PDF-1.7\n" + html.encode("utf-8")

    class CrashingEmailProvider(FakeEmailProvider):
        async def send(self, message):  # type: ignore[no-untyped-def]
            self.attempts.append(message)
            raise asyncio.CancelledError

    provider = CrashingEmailProvider()
    current_time = [datetime(2026, 8, 10, 12, 0, tzinfo=UTC)]
    settings = get_settings().model_copy(update={"email_pending_lease_seconds": 60})
    service = RealEstateDeliveryService(
        session,
        settings,
        FakePdfRenderer(FakeStorageProvider(), VerticalConfigService()),
        provider,
        BillingService(session, settings, FakeBillingProvider()),
        clock=lambda: current_time[0],
    )

    # The durable pending row survives the simulated process cancellation.
    with pytest.raises(asyncio.CancelledError):
        await service.send_report(
            context, scenario.visit_id, "email", "buyer@example.com"
        )
    assert len(provider.attempts) == 1

    # A lease that is still active remains concurrency-protected.
    with pytest.raises(EmailDeliveryInProgressError):
        await service.send_report(
            context, scenario.visit_id, "email", "buyer@example.com"
        )
    assert len(provider.attempts) == 1

    current_time[0] += timedelta(seconds=61)
    with pytest.raises(EmailDeliveryOutcomeUnknownError):
        await service.send_report(
            context, scenario.visit_id, "email", "buyer@example.com"
        )
    assert len(provider.attempts) == 1

    delivery = await client.get(
        f"/showings/{scenario.visit_id}/delivery", headers=scenario.headers
    )
    assert delivery.status_code == 200, delivery.text
    stale_send = delivery.json()["sends"][0]
    assert stale_send["status"] == "outcome_unknown"
    assert stale_send["error"] == RealEstateDeliveryService._STALE_PENDING_ERROR
    assert stale_send["attempt_count"] == 1


async def test_report_edit_history_is_append_only_and_workspace_scoped(
    client: AsyncClient, session: AsyncSession
) -> None:
    scenario = await _scenario(client, session, "report-history-owner@example.com")
    me = await client.get("/me", headers=scenario.headers)
    assert me.status_code == 200
    editor_id = uuid.UUID(me.json()["user"]["id"])
    initial = {
        "executive_summary": "First accepted summary.",
        "room_by_room": [],
        "highlights": [],
        "concerns": [],
        "follow_ups": [],
    }
    updated = {
        "executive_summary": "Second accepted summary.",
        "room_by_room": [],
        "highlights": [],
        "concerns": [],
        "follow_ups": [],
    }

    first = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={"content": initial},
    )
    assert first.status_code == 200, first.text
    second = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={"content": updated},
    )
    assert second.status_code == 200, second.text

    response = await client.get(
        f"/reports/{scenario.report_id}/revisions", headers=scenario.headers
    )
    assert response.status_code == 200, response.text
    revisions = response.json()
    assert len(revisions) == 2
    assert revisions[0]["previous_content"]["executive_summary"] == (
        "Bright kitchen with cabinet wear to review."
    )
    assert revisions[0]["new_content"] == initial
    assert revisions[1]["previous_content"] == initial
    assert revisions[1]["new_content"] == updated
    assert revisions[0]["edited_by"] == str(editor_id)
    assert revisions[1]["edited_by"] == str(editor_id)
    assert revisions[0]["created_at"] <= revisions[1]["created_at"]

    revision_id = uuid.UUID(revisions[0]["id"])
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            await session.execute(
                update(ReportRevision)
                .where(ReportRevision.id == revision_id)
                .values(new_content=updated)
            )
    await session.rollback()
    persisted = await session.scalar(
        select(ReportRevision).where(ReportRevision.id == revision_id)
    )
    assert persisted is not None
    assert persisted.new_content == initial

    other = await _scenario(client, session, "report-history-other@example.com")
    foreign_read = await client.get(
        f"/reports/{scenario.report_id}/revisions", headers=other.headers
    )
    assert foreign_read.status_code == 404


async def test_identical_normalized_report_patch_is_a_noop(
    client: AsyncClient, session: AsyncSession
) -> None:
    scenario = await _scenario(client, session, "report-history-noop@example.com")
    edited = {
        "executive_summary": "An edited summary.",
        "room_by_room": [],
        "highlights": [],
        "concerns": [],
        "follow_ups": [],
    }
    first = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={"content": edited},
    )
    assert first.status_code == 200, first.text

    # Reorder the JSON object to prove that semantically identical normalized
    # content does not create an audit row.
    same_content_with_different_key_order = {
        "follow_ups": [],
        "concerns": [],
        "highlights": [],
        "room_by_room": [],
        "executive_summary": "An edited summary.",
    }
    second = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={"content": same_content_with_different_key_order},
    )
    assert second.status_code == 200, second.text
    assert second.json()["content"] == edited

    revisions = await client.get(
        f"/reports/{scenario.report_id}/revisions", headers=scenario.headers
    )
    assert revisions.status_code == 200, revisions.text
    assert len(revisions.json()) == 1


async def test_report_revisions_cascade_with_pending_report_cleanup(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Revision rows are append-only until pipeline/report cleanup removes them."""

    scenario = await _scenario(client, session, "report-history-cleanup@example.com")
    edited = {
        "executive_summary": "This draft will be regenerated.",
        "room_by_room": [],
        "highlights": [],
        "concerns": [],
        "follow_ups": [],
    }
    response = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={"content": edited},
    )
    assert response.status_code == 200, response.text
    revisions = await client.get(
        f"/reports/{scenario.report_id}/revisions", headers=scenario.headers
    )
    assert len(revisions.json()) == 1

    # This is the existing pipeline regeneration cleanup boundary.  The
    # report and its audit snapshots intentionally disappear together; the
    # revision table is not a second source of truth for deleted reports.
    await PipelineRepository(session).delete_pending_reports(
        scenario.workspace_id, scenario.visit_id
    )
    await session.commit()
    assert await session.get(Report, scenario.report_id) is None
    assert (
        await session.scalar(
            select(func.count(ReportRevision.id)).where(
                ReportRevision.report_id == scenario.report_id
            )
        )
        == 0
    )


async def test_concurrent_report_patches_form_linear_revision_chain(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    scenario = await _scenario(client, session, "report-history-concurrent@example.com")
    updates = [
        {
            "executive_summary": "Concurrent edit A.",
            "room_by_room": [],
            "highlights": [],
            "concerns": [],
            "follow_ups": [],
        },
        {
            "executive_summary": "Concurrent edit B.",
            "room_by_room": [],
            "highlights": [],
            "concerns": [],
            "follow_ups": [],
        },
    ]
    me = await client.get("/me", headers=scenario.headers)
    user_id = uuid.UUID(me.json()["user"]["id"])
    a_context_ready = asyncio.Event()
    b_visit_locked = asyncio.Event()
    a_lock_attempted = asyncio.Event()
    a_backend_pid: int | None = None

    async def run_patch_a() -> dict[str, object]:
        nonlocal a_backend_pid
        async with get_session_factory()() as database_session:
            context_data = await AuthRepository(database_session).get_context(
                user_id, scenario.workspace_id
            )
            assert context_data is not None
            context = CurrentContext(*context_data)
            a_backend_pid = await database_session.scalar(
                text("SELECT pg_backend_pid()")
            )
            assert a_backend_pid is not None
            # Keep transaction A's start timestamp measurably earlier than B's
            # without using timing to decide which transaction gets the lock.
            await database_session.execute(text("SELECT pg_sleep(0.02)"))
            a_context_ready.set()
            await asyncio.wait_for(b_visit_locked.wait(), timeout=5)
            service = RealEstateReviewService(
                database_session,
                VerticalConfigService(),
                ReportRenderer(FakeStorageProvider(), VerticalConfigService()),
            )
            a_lock_attempted.set()
            report = await service.update_report(
                context, scenario.report_id, updates[0]
            )
            await database_session.commit()
            return copy.deepcopy(report.content)

    async def run_patch_b() -> dict[str, object]:
        async with get_session_factory()() as database_session:
            await asyncio.wait_for(a_context_ready.wait(), timeout=5)
            context_data = await AuthRepository(database_session).get_context(
                user_id, scenario.workspace_id
            )
            assert context_data is not None
            context = CurrentContext(*context_data)
            await database_session.scalar(
                select(Visit).where(Visit.id == scenario.visit_id).with_for_update()
            )
            b_visit_locked.set()
            await asyncio.wait_for(a_lock_attempted.wait(), timeout=5)

            assert a_backend_pid is not None
            deadline = asyncio.get_running_loop().time() + 5
            while True:
                blocked = await database_session.scalar(
                    text("SELECT cardinality(pg_blocking_pids(:backend_pid)) > 0"),
                    {"backend_pid": a_backend_pid},
                )
                if blocked:
                    break
                if asyncio.get_running_loop().time() >= deadline:
                    raise AssertionError(
                        "transaction A did not wait for transaction B's visit lock"
                    )
                await asyncio.sleep(0.01)

            service = RealEstateReviewService(
                database_session,
                VerticalConfigService(),
                ReportRenderer(FakeStorageProvider(), VerticalConfigService()),
            )
            report = await service.update_report(
                context, scenario.report_id, updates[1]
            )
            await database_session.commit()
            return copy.deepcopy(report.content)

    # Transaction A starts first but waits on B's already-held visit lock.
    # PostgreSQL therefore serializes B before A even though now() reports A's
    # transaction-start timestamp as earlier.  The lock wait is observed from
    # PostgreSQL, so this test does not rely on a sleep winning a race.
    patch_a = asyncio.create_task(run_patch_a())
    await a_context_ready.wait()
    patch_b = asyncio.create_task(run_patch_b())
    results = await asyncio.wait_for(asyncio.gather(patch_a, patch_b), timeout=10)
    assert results == updates

    revisions_response = await client.get(
        f"/reports/{scenario.report_id}/revisions", headers=scenario.headers
    )
    assert revisions_response.status_code == 200, revisions_response.text
    revisions = revisions_response.json()
    assert len(revisions) == 2
    assert revisions[0]["new_content"] == revisions[1]["previous_content"]
    assert [revision["new_content"] for revision in revisions] == updates[::-1]
    assert [revision["revision_number"] for revision in revisions] == [1, 2]
    assert datetime.fromisoformat(revisions[0]["created_at"]) > datetime.fromisoformat(
        revisions[1]["created_at"]
    )


async def test_concurrent_patch_and_send_never_deliver_stale_report(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    scenario = await _scenario(client, session, "report-history-patch-send@example.com")
    await _confirm_scenario(client, scenario)
    updated = {
        "executive_summary": "Fresh content wins the delivery race.",
        "room_by_room": [],
        "highlights": [],
        "concerns": [],
        "follow_ups": [],
    }

    me = await client.get("/me", headers=scenario.headers)
    user_id = uuid.UUID(me.json()["user"]["id"])
    settings = get_settings()

    async def run_patch() -> dict[str, object] | None:
        async with get_session_factory()() as database_session:
            context_data = await AuthRepository(database_session).get_context(
                user_id, scenario.workspace_id
            )
            assert context_data is not None
            context = CurrentContext(*context_data)
            service = RealEstateReviewService(
                database_session,
                VerticalConfigService(),
                ReportRenderer(FakeStorageProvider(), VerticalConfigService()),
            )
            try:
                report = await service.update_report(
                    context, scenario.report_id, updated
                )
            except ResourceConflictError:
                await database_session.rollback()
                return None
            await database_session.commit()
            return copy.deepcopy(report.content)

    async def run_send():  # type: ignore[no-untyped-def]
        async with get_session_factory()() as database_session:
            context_data = await AuthRepository(database_session).get_context(
                user_id, scenario.workspace_id
            )
            assert context_data is not None
            context = CurrentContext(*context_data)
            provider = FakeEmailProvider()
            service = RealEstateDeliveryService(
                database_session,
                settings,
                ReportRenderer(FakeStorageProvider(), VerticalConfigService()),
                provider,
                BillingService(database_session, settings, FakeBillingProvider()),
            )
            result = await service.send_report(
                context, scenario.visit_id, "link_only", None
            )
            await database_session.commit()
            return result.share_url

    patch_task = asyncio.create_task(run_patch())
    send_task = asyncio.create_task(run_send())
    patch_result, share_url = await asyncio.wait_for(
        asyncio.gather(patch_task, send_task), timeout=10
    )

    public = await client.get(f"/r/{share_url.rsplit('/', 1)[-1]}")
    assert public.status_code == 200, public.text
    revisions = await client.get(
        f"/reports/{scenario.report_id}/revisions", headers=scenario.headers
    )
    assert revisions.status_code == 200, revisions.text

    if patch_result is not None:
        # Edit-first: the delivery transaction sees and renders the committed
        # edit after taking the same visit lock.
        assert patch_result == updated
        assert len(revisions.json()) == 1
        assert updated["executive_summary"] in public.text
    else:
        # Send-first: the edit is rejected after observing sent_to_client, so
        # the public snapshot remains the original confirmed report.
        assert revisions.json() == []
        assert updated["executive_summary"] not in public.text
        assert "Bright kitchen with cabinet wear to review." in public.text


async def test_sent_report_patch_does_not_create_revision(
    client: AsyncClient, session: AsyncSession, email_provider: FakeEmailProvider
) -> None:
    scenario = await _scenario(client, session, "report-history-sent@example.com")
    await _confirm_scenario(client, scenario)
    sent = await client.post(
        f"/showings/{scenario.visit_id}/send",
        headers=scenario.headers,
        json={"channel": "link_only"},
    )
    assert sent.status_code == 200, sent.text
    before = await client.get(
        f"/reports/{scenario.report_id}/revisions", headers=scenario.headers
    )
    assert before.status_code == 200
    assert before.json() == []

    blocked = await client.patch(
        f"/reports/{scenario.report_id}",
        headers=scenario.headers,
        json={
            "content": {
                "executive_summary": "Must remain immutable.",
                "room_by_room": [],
                "highlights": [],
                "concerns": [],
                "follow_ups": [],
            }
        },
    )
    assert blocked.status_code == 409
    after = await client.get(
        f"/reports/{scenario.report_id}/revisions", headers=scenario.headers
    )
    assert after.status_code == 200
    assert after.json() == []
    del email_provider


async def test_review_and_delivery_workspace_isolation(
    client: AsyncClient, session: AsyncSession
) -> None:
    owner = await _scenario(client, session, "review-isolation-owner@example.com")
    other = await _scenario(client, session, "review-isolation-other@example.com")
    attempts = [
        await client.patch(
            f"/observations/{owner.ordinary_id}",
            headers=other.headers,
            json={"content": "Cross workspace"},
        ),
        await client.patch(
            f"/transcript-segments/{owner.segment_id}",
            headers=other.headers,
            json={"text": "Cross workspace"},
        ),
        await client.patch(
            f"/reports/{owner.report_id}",
            headers=other.headers,
            json={
                "content": {
                    "executive_summary": "Cross workspace",
                    "room_by_room": [],
                    "highlights": [],
                    "concerns": [],
                    "follow_ups": [],
                }
            },
        ),
        await client.post(f"/showings/{owner.visit_id}/confirm", headers=other.headers),
        await client.post(
            f"/showings/{owner.visit_id}/share-links",
            headers=other.headers,
            json={},
        ),
        await client.post(
            f"/showings/{owner.visit_id}/send",
            headers=other.headers,
            json={"channel": "link_only"},
        ),
        await client.get(f"/showings/{owner.visit_id}/delivery", headers=other.headers),
    ]
    assert {response.status_code for response in attempts} == {404}
