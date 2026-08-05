from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Contact,
    Observation,
    RawMedia,
    Report,
    Subject,
    TranscriptSegment,
    Visit,
    Zone,
)


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
        cursor_created_at: datetime | None,
        cursor_id: uuid.UUID | None,
        limit: int,
    ) -> list[tuple[Visit, Subject | None, Contact | None]]:
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
            statement = statement.where(Visit.created_at >= date_from)
        if date_to is not None:
            statement = statement.where(Visit.created_at <= date_to)
        if query:
            pattern = f"%{query}%"
            statement = statement.where(
                or_(
                    Subject.display_name.ilike(pattern),
                    Subject.location.ilike(pattern),
                    Contact.name.ilike(pattern),
                )
            )
        if cursor_created_at is not None and cursor_id is not None:
            statement = statement.where(
                or_(
                    Visit.created_at < cursor_created_at,
                    and_(
                        Visit.created_at == cursor_created_at,
                        Visit.id < cursor_id,
                    ),
                )
            )
        result = await self.session.execute(
            statement.order_by(Visit.created_at.desc(), Visit.id.desc()).limit(limit)
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
