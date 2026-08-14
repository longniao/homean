from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Contact,
    Observation,
    RawMedia,
    Report,
    Subject,
    TranscriptSegment,
    Visit,
    VisitMarker,
    Zone,
)


def visit_toured_at() -> object:
    """When the tour happened, for filtering, ordering and pagination.

    ``created_at`` is when the row reached the server, which for an offline
    capture is whenever it next found signal — a Monday showing synced on
    Wednesday sorts and filters as Wednesday, and disagrees with the date its
    own report prints. ``started_at`` is the capture time the client reports,
    falling back to insertion for rows that never carried one.
    """

    return func.coalesce(Visit.started_at, Visit.created_at)


class ShowingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, *entities: object) -> None:
        self.session.add_all(entities)

    async def flush(self) -> None:
        await self.session.flush()

    async def get_visit(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> Visit | None:
        return await self.session.scalar(
            select(Visit).where(
                Visit.id == visit_id,
                Visit.workspace_id == workspace_id,
            )
        )

    async def get_visit_by_capture_client_id(
        self, workspace_id: uuid.UUID, capture_client_id: uuid.UUID
    ) -> Visit | None:
        """Find a mobile-created visit within one workspace by capture key."""
        return await self.session.scalar(
            select(Visit).where(
                Visit.workspace_id == workspace_id,
                Visit.capture_client_id == capture_client_id,
            )
        )

    async def get_media(
        self,
        workspace_id: uuid.UUID,
        visit_id: uuid.UUID,
        media_id: uuid.UUID,
    ) -> RawMedia | None:
        return await self.session.scalar(
            select(RawMedia)
            .join(Visit, Visit.id == RawMedia.visit_id)
            .where(
                RawMedia.id == media_id,
                RawMedia.visit_id == visit_id,
                Visit.workspace_id == workspace_id,
            )
        )

    async def get_media_for_update(
        self,
        workspace_id: uuid.UUID,
        visit_id: uuid.UUID,
        media_id: uuid.UUID,
    ) -> RawMedia | None:
        """Load one workspace-scoped media row and serialize identity claims."""
        return await self.session.scalar(
            select(RawMedia)
            .join(Visit, Visit.id == RawMedia.visit_id)
            .where(
                RawMedia.id == media_id,
                RawMedia.visit_id == visit_id,
                Visit.workspace_id == workspace_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update(of=RawMedia)
        )

    async def get_media_by_client_id(
        self,
        workspace_id: uuid.UUID,
        visit_id: uuid.UUID,
        client_id: uuid.UUID,
    ) -> RawMedia | None:
        return await self.session.scalar(
            select(RawMedia)
            .join(Visit, Visit.id == RawMedia.visit_id)
            .where(
                RawMedia.visit_id == visit_id,
                RawMedia.client_id == client_id,
                Visit.workspace_id == workspace_id,
            )
        )

    async def has_completed_audio(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> bool:
        media_id = await self.session.scalar(
            select(RawMedia.id)
            .join(Visit, Visit.id == RawMedia.visit_id)
            .where(
                RawMedia.visit_id == visit_id,
                RawMedia.type == "audio",
                RawMedia.status == "uploaded",
                Visit.workspace_id == workspace_id,
            )
            .limit(1)
        )
        return media_id is not None

    async def list(
        self,
        workspace_id: uuid.UUID,
        *,
        contact_id: uuid.UUID | None,
        subject_id: uuid.UUID | None,
        unassigned: bool | None,
        status: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        query: str | None,
        cursor_toured_at: datetime | None,
        cursor_id: uuid.UUID | None,
        limit: int,
    ) -> list[tuple[Visit, Subject | None, Contact | None]]:
        toured_at = visit_toured_at()
        statement = (
            select(Visit, Subject, Contact)
            .outerjoin(
                Subject,
                and_(
                    Subject.id == Visit.subject_id,
                    Subject.workspace_id == workspace_id,
                ),
            )
            .outerjoin(
                Contact,
                and_(
                    Contact.id == Visit.contact_id,
                    Contact.workspace_id == workspace_id,
                ),
            )
            .where(Visit.workspace_id == workspace_id)
        )
        if contact_id is not None:
            statement = statement.where(Visit.contact_id == contact_id)
        if subject_id is not None:
            statement = statement.where(Visit.subject_id == subject_id)
        if unassigned is True:
            statement = statement.where(Visit.subject_id.is_(None))
        if status is not None:
            statement = statement.where(Visit.status == status)
        if date_from is not None:
            statement = statement.where(toured_at >= date_from)
        if date_to is not None:
            statement = statement.where(toured_at <= date_to)
        if query:
            pattern = f"%{query}%"
            statement = statement.where(
                or_(
                    Subject.display_name.ilike(pattern),
                    Subject.location.ilike(pattern),
                    Contact.name.ilike(pattern),
                )
            )
        if cursor_toured_at is not None and cursor_id is not None:
            statement = statement.where(
                or_(
                    toured_at < cursor_toured_at,
                    and_(
                        toured_at == cursor_toured_at,
                        Visit.id < cursor_id,
                    ),
                )
            )
        result = await self.session.execute(
            statement.order_by(toured_at.desc(), Visit.id.desc()).limit(limit)
        )
        return list(result.tuples())

    async def detail_media(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> list[RawMedia]:
        result = await self.session.scalars(
            select(RawMedia)
            .join(Visit, Visit.id == RawMedia.visit_id)
            .where(
                RawMedia.visit_id == visit_id,
                Visit.workspace_id == workspace_id,
            )
            .order_by(RawMedia.created_at, RawMedia.id)
        )
        return list(result)

    async def list_markers(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> list[VisitMarker]:
        result = await self.session.scalars(
            select(VisitMarker)
            .join(Visit, Visit.id == VisitMarker.visit_id)
            .where(
                VisitMarker.visit_id == visit_id,
                Visit.workspace_id == workspace_id,
            )
            .order_by(
                VisitMarker.timestamp_offset_ms,
                VisitMarker.created_at,
                VisitMarker.id,
            )
        )
        return list(result)

    async def get_marker(
        self, visit_id: uuid.UUID, client_id: uuid.UUID
    ) -> VisitMarker | None:
        return await self.session.scalar(
            select(VisitMarker).where(
                VisitMarker.visit_id == visit_id,
                VisitMarker.client_id == client_id,
            )
        )

    async def insert_marker(self, marker: VisitMarker) -> VisitMarker:
        """Insert once and return the existing row when a retry races it.

        The unique visit/client key is the idempotency boundary.  Using
        ``ON CONFLICT DO NOTHING`` keeps concurrent retries from surfacing a
        transient integrity error to the capture client.
        """
        statement = (
            pg_insert(VisitMarker)
            .values(
                visit_id=marker.visit_id,
                client_id=marker.client_id,
                created_by=marker.created_by,
                marker_type=marker.marker_type,
                timestamp_offset_ms=marker.timestamp_offset_ms,
            )
            .on_conflict_do_nothing(
                index_elements=[VisitMarker.visit_id, VisitMarker.client_id]
            )
            .returning(VisitMarker.id)
        )
        marker_id = await self.session.scalar(statement)
        if marker_id is None:
            existing = await self.get_marker(marker.visit_id, marker.client_id)
            if existing is None:  # pragma: no cover - conflict row cannot vanish here
                raise RuntimeError("marker insert conflict could not be resolved")
            return existing
        created = await self.session.scalar(
            select(VisitMarker).where(VisitMarker.id == marker_id)
        )
        if created is None:  # pragma: no cover - returning row was just inserted
            raise RuntimeError("marker insert did not return a row")
        return created

    async def detail_zones(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> list[Zone]:
        result = await self.session.scalars(
            select(Zone)
            .join(Visit, Visit.id == Zone.visit_id)
            .where(Zone.visit_id == visit_id, Visit.workspace_id == workspace_id)
            .order_by(Zone.position, Zone.created_at, Zone.id)
        )
        return list(result)

    async def detail_observations(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> list[Observation]:
        result = await self.session.scalars(
            select(Observation)
            .join(Visit, Visit.id == Observation.visit_id)
            .where(
                Observation.visit_id == visit_id,
                Visit.workspace_id == workspace_id,
            )
            .order_by(Observation.created_at, Observation.id)
        )
        return list(result)

    async def detail_transcript(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> list[TranscriptSegment]:
        result = await self.session.scalars(
            select(TranscriptSegment)
            .join(Visit, Visit.id == TranscriptSegment.visit_id)
            .where(
                TranscriptSegment.visit_id == visit_id,
                Visit.workspace_id == workspace_id,
            )
            .order_by(
                TranscriptSegment.timestamp_start,
                TranscriptSegment.created_at,
                TranscriptSegment.id,
            )
        )
        return list(result)

    async def detail_report(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> Report | None:
        return await self.session.scalar(
            select(Report)
            .join(Visit, Visit.id == Report.visit_id)
            .where(Report.visit_id == visit_id, Visit.workspace_id == workspace_id)
            .order_by(Report.created_at.desc(), Report.id.desc())
            .limit(1)
        )
