import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.models import Subject, WorkspaceBranding
from app.services.renderer import ReportRenderer
from app.storage import FakeStorageProvider
from app.verticals import VerticalConfigService

FIXTURE = Path(__file__).with_name("fixtures") / "real_estate_report.json"

EMPTY_REPORT = {
    "executive_summary": "A short tour with little to note.",
    "room_by_room": [],
    "highlights": [],
    "concerns": [],
    "follow_ups": [],
}


def _branding() -> WorkspaceBranding:
    return WorkspaceBranding(
        workspace_id=uuid.UUID("44444444-4444-4444-8444-444444444444"),
        display_name="Riley & Chen Realty",
        phone="+1-604-555-0123",
        email="reports@example.com",
        license_no="BC-12345",
        accent_color="#146C5A",
    )


async def test_real_estate_renderer_snapshot() -> None:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    renderer = ReportRenderer(FakeStorageProvider(), VerticalConfigService())

    rendered = await renderer.render_html(content, _branding())

    assert rendered.startswith("<!doctype html>")
    assert "Riley &amp; Chen Realty" in rendered
    assert "Kitchen" in rendered
    assert "@media print" in rendered
    assert "@media (max-width: 640px)" in rendered
    assert hashlib.sha256(rendered.encode("utf-8")).hexdigest() == (
        "08401f154e49348de15916c97ec355f6d67273e652f8365719e08f83fd593ede"
    )


async def test_report_leads_with_the_property_and_tour_date() -> None:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    renderer = ReportRenderer(FakeStorageProvider(), VerticalConfigService())

    rendered = await renderer.render_html(
        content,
        _branding(),
        subject=Subject(
            subject_type="property",
            display_name="1428 Maple Grove Lane",
            location="Vancouver, BC",
        ),
        toured_on=datetime(2026, 5, 16, tzinfo=UTC),
    )

    # The recipient may be holding several of these, so the property heads the
    # document rather than the brokerage.
    assert "<h1>1428 Maple Grove Lane</h1>" in rendered
    assert "Vancouver, BC · Toured 16 May 2026" in rendered
    assert rendered.index("1428 Maple Grove Lane") < rendered.index(
        "Riley &amp; Chen Realty"
    )


async def test_tour_date_uses_the_capture_zone_not_utc() -> None:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    renderer = ReportRenderer(FakeStorageProvider(), VerticalConfigService())
    subject = Subject(
        subject_type="property", display_name="1428 Maple Grove Lane", location=None
    )
    # 16 May 19:00 in Vancouver is already 17 May in UTC.
    evening_tour = datetime(2026, 5, 17, 2, 0, tzinfo=UTC)

    local = await renderer.render_html(
        content,
        _branding(),
        subject=subject,
        toured_on=evening_tour,
        timezone="America/Vancouver",
    )
    without_zone = await renderer.render_html(
        content, _branding(), subject=subject, toured_on=evening_tour
    )

    assert "Toured 16 May 2026" in local
    assert "Toured 17 May 2026" in without_zone


async def test_unresolvable_zone_falls_back_instead_of_failing_delivery() -> None:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    renderer = ReportRenderer(FakeStorageProvider(), VerticalConfigService())

    rendered = await renderer.render_html(
        content,
        _branding(),
        subject=Subject(
            subject_type="property", display_name="1428 Maple Grove Lane", location=None
        ),
        toured_on=datetime(2026, 5, 17, 2, 0, tzinfo=UTC),
        timezone="Mars/Olympus_Mons",
    )

    assert "Toured 17 May 2026" in rendered


async def test_report_without_a_subject_omits_the_property_line() -> None:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    renderer = ReportRenderer(FakeStorageProvider(), VerticalConfigService())

    rendered = await renderer.render_html(content, _branding())

    assert '<p class="meta">' not in rendered
    assert "<h1>Showing report</h1>" in rendered


async def test_empty_sections_state_absence_instead_of_rendering_a_dash() -> None:
    renderer = ReportRenderer(FakeStorageProvider(), VerticalConfigService())

    rendered = await renderer.render_html(EMPTY_REPORT, _branding())

    # Highlights, concerns and follow-ups say so explicitly; a heading with
    # nothing under it reads as an unfinished document.
    assert rendered.count("None recorded") == 3
    # An empty room list is degenerate rather than informative, so it is omitted.
    assert "Room-by-room observations" not in rendered


async def test_footer_runs_in_the_page_margin_so_it_cannot_orphan_a_page() -> None:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    renderer = ReportRenderer(FakeStorageProvider(), VerticalConfigService())

    rendered = await renderer.render_html(content, _branding(), consent_ack=True)

    assert "position: running(docfooter)" in rendered
    assert "content: element(docfooter)" in rendered
