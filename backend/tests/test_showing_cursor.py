import base64
import json
import uuid
from datetime import UTC, datetime

import pytest

from app.services.exceptions import DomainValidationError
from app.services.showings import RealEstateShowingService


def _cursor_for_payload(payload: bytes | dict[str, object]) -> str:
    if isinstance(payload, dict):
        payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


@pytest.mark.parametrize(
    "cursor",
    [
        "a",
        _cursor_for_payload(b"\xff"),
        _cursor_for_payload(b'{"created_at":'),
        _cursor_for_payload(
            {
                "created_at": "not-a-date",
                "id": str(uuid.uuid4()),
            }
        ),
        _cursor_for_payload(
            {
                "created_at": "2026-01-01T00:00:00+00:00",
                "id": "not-a-uuid",
            }
        ),
    ],
)
def test_decode_cursor_rejects_malformed_values(cursor: str) -> None:
    with pytest.raises(DomainValidationError, match="^invalid cursor$"):
        RealEstateShowingService._decode_cursor(cursor)


def test_decode_cursor_preserves_valid_cursor_behavior() -> None:
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    visit_id = uuid.uuid4()
    cursor = RealEstateShowingService._encode_cursor(created_at, visit_id)

    assert RealEstateShowingService._decode_cursor(cursor) == (created_at, visit_id)
