import json
import uuid
from pathlib import Path

from app.models import WorkspaceBranding
from app.services.renderer import ReportRenderer
from app.storage import FakeStorageProvider
from app.verticals import VerticalConfigService

FIXTURE = Path(__file__).with_name("fixtures") / "real_estate_report.json"


def _branding() -> WorkspaceBranding:
    return WorkspaceBranding(
        workspace_id=uuid.UUID("44444444-4444-4444-8444-444444444444"),
        display_name="Riley & Chen Realty",
        accent_color="#146C5A",
    )


def test_consent_wording_is_versioned_for_later_resolution() -> None:
    consent = VerticalConfigService().get().consent

    # A visit stores this version, so the exact wording an agent agreed to
    # stays resolvable after the text changes.
    assert consent.version
    assert consent.text.strip()


def test_placeholder_legal_text_cannot_ship_unnoticed() -> None:
    pack = VerticalConfigService().get()

    # This asserts the *current* state deliberately. When counsel approves the
    # consent text and both disclosures, flip the config to "reviewed" — this
    # test then fails and forces a conscious update rather than letting
    # unreviewed wording reach real buyers unnoticed.
    assert pack.consent.counsel_review_status == "pending", (
        "counsel_review_status changed: confirm counsel approved consent.text, "
        "scope_disclosure and recording_disclosure, then update this test."
    )


async def test_scope_limit_is_stated_whether_or_not_a_recording_exists() -> None:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    renderer = ReportRenderer(FakeStorageProvider(), VerticalConfigService())
    labels = VerticalConfigService().get().report_template.labels

    acknowledged = await renderer.render_html(content, _branding(), consent_ack=True)
    unacknowledged = await renderer.render_html(content, _branding(), consent_ack=False)

    # The risk of a report being read as an inspection finding does not depend
    # on whether audio was captured, so this limit is unconditional.
    assert labels["scope_disclosure"] in acknowledged
    assert labels["scope_disclosure"] in unacknowledged


async def test_recording_notice_appears_only_for_recorded_visits() -> None:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    renderer = ReportRenderer(FakeStorageProvider(), VerticalConfigService())
    labels = VerticalConfigService().get().report_template.labels

    acknowledged = await renderer.render_html(content, _branding(), consent_ack=True)
    unacknowledged = await renderer.render_html(content, _branding(), consent_ack=False)

    assert labels["recording_disclosure"] in acknowledged
    assert labels["recording_disclosure"] not in unacknowledged


def test_a_pack_without_a_scope_limit_is_rejected() -> None:
    import pytest
    from pydantic import ValidationError

    from app.verticals.config import VerticalPack

    raw = VerticalConfigService().get().model_dump()
    raw["report_template"]["labels"].pop("scope_disclosure")

    with pytest.raises(ValidationError, match="scope_disclosure"):
        VerticalPack.model_validate(raw)
