import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.models import Visit
from app.repositories.showings import visit_toured_at
from app.services.showings import RealEstateShowingService

MONDAY = datetime(2026, 8, 10, 17, 0, tzinfo=UTC)


def _compiled(statement: object) -> str:
    return str(statement).lower()


def test_listing_orders_by_the_tour_date_not_the_insert_time() -> None:
    statement = select(Visit).order_by(visit_toured_at().desc())

    compiled = _compiled(statement)

    # created_at is when the row reached the server, which for an offline
    # capture is whenever it next found signal.
    assert "coalesce" in compiled
    assert "started_at" in compiled


def test_the_tour_date_falls_back_for_rows_that_never_carried_one() -> None:
    statement = select(visit_toured_at())

    compiled = _compiled(statement)

    # started_at is nullable, and a null must not sort a visit off the end of
    # the list; insertion time is the honest stand-in.
    assert "coalesce" in compiled
    assert "created_at" in compiled


def test_a_cursor_is_built_from_the_same_date_the_query_sorts_by() -> None:
    # Toured Monday, synced Wednesday.
    visit = Visit(
        id=uuid.uuid4(),
        started_at=MONDAY,
        created_at=datetime(2026, 8, 12, tzinfo=UTC),
    )

    encoded = RealEstateShowingService._encode_cursor(
        visit.started_at or visit.created_at, visit.id
    )
    decoded_at, _ = RealEstateShowingService._decode_cursor(encoded)

    # A cursor built from a different column than the ORDER BY silently drops
    # or repeats rows at every page boundary.
    assert decoded_at == MONDAY
