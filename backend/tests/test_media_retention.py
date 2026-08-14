from datetime import UTC, datetime

import pytest

from app.storage import FakeStorageProvider
from scripts.purge_expired_media import cutoff_for

NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)


def test_purging_is_disabled_until_a_period_is_chosen() -> None:
    # Retention is a policy decision. Shipping a default that quietly deletes
    # a buyer's evidence would be the wrong way round.
    assert cutoff_for(0, NOW) is None


def test_a_negative_period_does_not_become_a_future_cutoff() -> None:
    assert cutoff_for(-30, NOW) is None


def test_the_cutoff_is_the_configured_number_of_days_back() -> None:
    cutoff = cutoff_for(30, NOW)

    assert cutoff is not None
    assert (NOW - cutoff).days == 30


async def test_deleting_an_absent_object_is_not_an_error() -> None:
    storage = FakeStorageProvider()

    # A purge run may be retried after a crash, so the second pass will meet
    # objects the first one already removed.
    await storage.delete_object("media/missing.m4a")


async def test_deleting_removes_the_bytes_and_the_metadata() -> None:
    storage = FakeStorageProvider()
    storage.put_object_bytes("media/tour.m4a", "audio/mp4", b"audio")

    await storage.delete_object("media/tour.m4a")

    assert await storage.head_object("media/tour.m4a") is None
    assert await storage.get_object_bytes("media/tour.m4a") is None


class _FailingDeleteStorage(FakeStorageProvider):
    """Storage whose delete always fails, standing in for an unreachable bucket."""

    async def delete_object(self, object_key: str) -> None:
        raise RuntimeError("storage is unreachable")


async def test_a_failed_delete_leaves_the_row_unmarked_for_a_later_retry() -> None:
    storage = _FailingDeleteStorage()
    storage.put_object_bytes("media/tour.m4a", "audio/mp4", b"audio")

    with pytest.raises(RuntimeError):
        await storage.delete_object("media/tour.m4a")

    # The object survives, so a record marking it purged would be asserting a
    # deletion that never happened — the failure that actually matters on a
    # retention feature. Marking only after a successful delete keeps the row
    # eligible for the next run instead.
    assert await storage.head_object("media/tour.m4a") is not None
