import hashlib
import json
import uuid
from pathlib import Path

from app.models import WorkspaceBranding
from app.services.renderer import ReportRenderer
from app.storage import FakeStorageProvider
from app.verticals import VerticalConfigService

FIXTURE = Path(__file__).with_name("fixtures") / "real_estate_report.json"


async def test_real_estate_renderer_snapshot() -> None:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    branding = WorkspaceBranding(
        workspace_id=uuid.UUID("44444444-4444-4444-8444-444444444444"),
        display_name="Riley & Chen Realty",
        phone="+1-604-555-0123",
        email="reports@example.com",
        license_no="BC-12345",
        accent_color="#146C5A",
    )
    renderer = ReportRenderer(FakeStorageProvider(), VerticalConfigService())

    rendered = await renderer.render_html(content, branding)

    assert rendered.startswith("<!doctype html>")
    assert "Riley &amp; Chen Realty" in rendered
    assert "Kitchen" in rendered
    assert "@media print" in rendered
    assert "@media (max-width: 640px)" in rendered
    assert hashlib.sha256(rendered.encode("utf-8")).hexdigest() == (
        "d8ebdf1044ef4c414abaf0228ef4672ce1d66621c28fe7f85513818f60fd6a42"
    )
