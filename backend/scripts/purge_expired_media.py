"""Remove stored capture objects older than the configured retention period.

Retention is a policy decision, so nothing happens until MEDIA_RETENTION_DAYS
is set: the default of 0 disables purging entirely. Runs read-only unless
``--apply`` is passed.

What it removes, and what it deliberately does not:

- Removes the stored object only — the audio, photo or video bytes.
- Keeps the ``raw_media`` row, marked ``purged_at``. Deleting the row would
  break the evidence chain silently, leaving observations pointing at media
  that appears never to have existed rather than media that was retained for a
  stated period and then removed.
- Never touches transcripts, observations or reports. Those are the record;
  the media is its backing.

Run from backend/: ``uv run python scripts/purge_expired_media.py [--apply]``.
"""

import argparse
import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import get_settings
from app.core.database_url import create_async_engine_for_url
from app.models import RawMedia, Visit
from app.storage import S3Client


@dataclass(frozen=True)
class PurgeCandidate:
    media_id: uuid.UUID
    visit_id: uuid.UUID
    object_key: str


def cutoff_for(retention_days: int, now: datetime) -> datetime | None:
    """The instant before which media may be purged, or None when disabled."""

    if retention_days <= 0:
        return None
    return now - timedelta(days=retention_days)


def _create_purge_engine(database_url: str) -> AsyncEngine:
    return create_async_engine_for_url(database_url, pool_pre_ping=True)


async def collect(cutoff: datetime) -> list[PurgeCandidate]:
    settings = get_settings()
    engine = _create_purge_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            rows = await session.execute(
                select(RawMedia.id, RawMedia.visit_id, RawMedia.object_key)
                .join(Visit, Visit.id == RawMedia.visit_id)
                .where(
                    RawMedia.purged_at.is_(None),
                    Visit.created_at < cutoff,
                )
                .order_by(RawMedia.created_at, RawMedia.id)
            )
            return [
                PurgeCandidate(media_id=media, visit_id=visit, object_key=key)
                for media, visit, key in rows.tuples()
            ]
    finally:
        await engine.dispose()


async def purge(candidates: list[PurgeCandidate]) -> tuple[int, int]:
    settings = get_settings()
    storage = S3Client(settings)
    engine = _create_purge_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    purged = 0
    failed = 0
    try:
        async with session_factory() as session:
            for candidate in candidates:
                media = await session.get(RawMedia, candidate.media_id)
                if media is None or media.purged_at is not None:
                    continue
                # Delete first, mark second. Marking first leaves a row
                # claiming the object is gone when the delete failed, and later
                # runs skip marked rows — so the record asserts a deletion that
                # never happened and never retries it. On a retention feature
                # that is the failure that matters, far more than a leaked
                # object. This order self-heals: the delete is idempotent, so
                # an unmarked row is simply purged again next run.
                try:
                    await storage.delete_object(candidate.object_key)
                except Exception:
                    # One unreachable object must not end the run. It stays
                    # unmarked, so the next run retries it.
                    failed += 1
                    continue
                media.purged_at = datetime.now(UTC)
                await session.commit()
                purged += 1
    finally:
        await engine.dispose()
    return purged, failed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually delete; omitted, the run only reports what it would do",
    )
    args = parser.parse_args()
    settings = get_settings()
    cutoff = cutoff_for(settings.media_retention_days, datetime.now(UTC))
    if cutoff is None:
        print(
            json.dumps(
                {
                    "retention_days": settings.media_retention_days,
                    "status": "disabled",
                    "detail": "set MEDIA_RETENTION_DAYS to enable purging",
                },
                indent=2,
            )
        )
        return
    candidates = asyncio.run(collect(cutoff))
    purged, failed = asyncio.run(purge(candidates)) if args.apply else (0, 0)
    print(
        json.dumps(
            {
                "retention_days": settings.media_retention_days,
                "cutoff": cutoff.isoformat(),
                "candidates": len(candidates),
                "purged": purged,
                "failed": failed,
                "status": "applied" if args.apply else "dry-run",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
