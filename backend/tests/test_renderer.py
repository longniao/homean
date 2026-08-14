import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.models import RawMedia, Subject, WorkspaceBranding
from app.services.renderer import PHOTOS_PER_ZONE, ReportRenderer
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
        "0e97c55808d406f8fe2dc94732dbd0986bf62304e2d996ba1c3672e88d3b6ff9"
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


def _jpeg(width: int = 1600, height: int = 1200) -> bytes:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (width, height), (120, 150, 130)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _photo(
    storage: FakeStorageProvider, key: str, zone_id: uuid.UUID | None
) -> RawMedia:
    storage.put_object_bytes(key, "image/jpeg", _jpeg())
    return RawMedia(
        id=uuid.uuid4(),
        visit_id=uuid.uuid4(),
        type="photo",
        object_key=key,
        content_type="image/jpeg",
        status="uploaded",
        zone_id=zone_id,
    )


async def test_placed_photos_render_inside_their_own_room() -> None:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    zone_id = uuid.UUID(content["room_by_room"][0]["zone_id"])
    storage = FakeStorageProvider()
    renderer = ReportRenderer(storage, VerticalConfigService())

    rendered = await renderer.render_html(
        content, _branding(), photos=[_photo(storage, "photos/kitchen.jpg", zone_id)]
    )

    assert rendered.count("data:image/jpeg;base64,") == 1
    # The strip belongs to the room card, after that room's bullets.
    assert rendered.index("Kitchen") < rendered.index('<div class="shots">')


async def test_unplaced_photos_are_not_rendered_at_all() -> None:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    storage = FakeStorageProvider()
    renderer = ReportRenderer(storage, VerticalConfigService())

    rendered = await renderer.render_html(
        content, _branding(), photos=[_photo(storage, "photos/loose.jpg", None)]
    )

    assert "data:image/jpeg;base64," not in rendered


async def test_photos_are_downscaled_rather_than_inlined_at_capture_size() -> None:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    zone_id = uuid.UUID(content["room_by_room"][0]["zone_id"])
    storage = FakeStorageProvider()
    renderer = ReportRenderer(storage, VerticalConfigService())
    original = _jpeg()

    rendered = await renderer.render_html(
        content, _branding(), photos=[_photo(storage, "photos/kitchen.jpg", zone_id)]
    )

    # The stored HTML is replayed for the life of a share link, so an inlined
    # capture-sized photo would bloat every delivery of it.
    encoded = rendered.split("data:image/jpeg;base64,")[1].split('"')[0]
    assert len(encoded) < len(original)


async def test_a_room_never_inlines_more_than_its_photo_cap() -> None:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    zone_id = uuid.UUID(content["room_by_room"][0]["zone_id"])
    storage = FakeStorageProvider()
    renderer = ReportRenderer(storage, VerticalConfigService())
    photos = [
        _photo(storage, f"photos/kitchen-{index}.jpg", zone_id) for index in range(5)
    ]

    rendered = await renderer.render_html(content, _branding(), photos=photos)

    assert rendered.count("data:image/jpeg;base64,") == PHOTOS_PER_ZONE


async def test_an_unreadable_photo_does_not_fail_the_report() -> None:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    zone_id = uuid.UUID(content["room_by_room"][0]["zone_id"])
    storage = FakeStorageProvider()
    renderer = ReportRenderer(storage, VerticalConfigService())
    storage.put_object_bytes("photos/corrupt.jpg", "image/jpeg", b"not an image")
    corrupt = RawMedia(
        id=uuid.uuid4(),
        visit_id=uuid.uuid4(),
        type="photo",
        object_key="photos/corrupt.jpg",
        content_type="image/jpeg",
        status="uploaded",
        zone_id=zone_id,
    )

    rendered = await renderer.render_html(content, _branding(), photos=[corrupt])

    assert rendered.startswith("<!doctype html>")
    assert "data:image/jpeg;base64," not in rendered


async def test_footer_runs_in_the_page_margin_so_it_cannot_orphan_a_page() -> None:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    renderer = ReportRenderer(FakeStorageProvider(), VerticalConfigService())

    rendered = await renderer.render_html(content, _branding(), consent_ack=True)

    assert "position: running(docfooter)" in rendered
    assert "content: element(docfooter)" in rendered
    # A running element applies from where it occurs onward, so the print twin
    # is declared before the body content or it is missing from every page but
    # the last.
    assert rendered.index('class="pagefoot"') < rendered.index('class="report"')
