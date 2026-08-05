import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.email import FakeEmailProvider
from app.models import (
    Observation,
    RawMedia,
    Report,
    ReportSend,
    ReportShareLink,
    ReportShareView,
    TranscriptSegment,
    WorkspaceBranding,
    Zone,
)
from app.storage import FakeStorageProvider

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
    client: AsyncClient, session: AsyncSession, email: str
) -> ReviewScenario:
    signup = await client.post(
        "/auth/signup", json={"email": email, "password": PASSWORD}
    )
    assert signup.status_code == 201, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    me = (await client.get("/me", headers=headers)).json()
    workspace_id = uuid.UUID(me["workspace"]["id"])
    showing = await client.post(
        "/showings", headers=headers, json={"address": "88 Review Crescent"}
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
    assert "Showing report" in public_html.text
    public_pdf = await client.get(f"/r/{token}/pdf", headers={"User-Agent": "Buyer/1"})
    assert public_pdf.status_code == 200
    assert public_pdf.content.startswith(b"%PDF")
    assert (
        await session.scalar(
            select(func.count())
            .select_from(ReportShareView)
            .where(ReportShareView.share_link_id == uuid.UUID(share.json()["id"]))
        )
        == 2
    )

    revoked = await client.post(
        f"/showings/{scenario.visit_id}/share-links/{share.json()['id']}/revoke",
        headers=scenario.headers,
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
    assert (await client.get(f"/r/{token}")).status_code == 404

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
    assert (await client.get(f"/r/{expiring.json()['token']}")).status_code == 404


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
    ]
    assert {response.status_code for response in attempts} == {404}
