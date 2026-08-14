import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Observation,
    PipelineRun,
    RawMedia,
    Report,
    TranscriptSegment,
    Visit,
    Zone,
)


class PipelineRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_visit(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> Visit | None:
        return await self.session.scalar(
            select(Visit).where(
                Visit.id == visit_id,
                Visit.workspace_id == workspace_id,
            )
        )

    async def uploaded_audio(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> list[RawMedia]:
        result = await self.session.scalars(
            select(RawMedia)
            .join(Visit, Visit.id == RawMedia.visit_id)
            .where(
                RawMedia.visit_id == visit_id,
                RawMedia.type == "audio",
                RawMedia.status == "uploaded",
                Visit.workspace_id == workspace_id,
            )
            .order_by(RawMedia.created_at, RawMedia.id)
        )
        return list(result)

    async def uploaded_photos(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> list[RawMedia]:
        result = await self.session.scalars(
            select(RawMedia)
            .join(Visit, Visit.id == RawMedia.visit_id)
            .where(
                RawMedia.visit_id == visit_id,
                RawMedia.type == "photo",
                RawMedia.status == "uploaded",
                Visit.workspace_id == workspace_id,
            )
            .order_by(RawMedia.timestamp_offset_ms, RawMedia.created_at, RawMedia.id)
        )
        return list(result)

    async def media_has_transcript(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID, media_id: uuid.UUID
    ) -> bool:
        segment_id = await self.session.scalar(
            select(TranscriptSegment.id)
            .join(Visit, Visit.id == TranscriptSegment.visit_id)
            .where(
                TranscriptSegment.visit_id == visit_id,
                TranscriptSegment.raw_media_id == media_id,
                Visit.workspace_id == workspace_id,
            )
            .limit(1)
        )
        return segment_id is not None

    async def transcripts(
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

    async def zones(self, workspace_id: uuid.UUID, visit_id: uuid.UUID) -> list[Zone]:
        result = await self.session.scalars(
            select(Zone)
            .join(Visit, Visit.id == Zone.visit_id)
            .where(Zone.visit_id == visit_id, Visit.workspace_id == workspace_id)
            .order_by(Zone.position, Zone.created_at, Zone.id)
        )
        return list(result)

    async def observations(
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

    async def pending_report(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> Report | None:
        return await self.session.scalar(
            select(Report)
            .join(Visit, Visit.id == Report.visit_id)
            .where(
                Report.visit_id == visit_id,
                Report.status == "pending_review",
                Visit.workspace_id == workspace_id,
            )
            .order_by(Report.created_at.desc(), Report.id.desc())
            .limit(1)
        )

    async def has_successful_run(
        self,
        workspace_id: uuid.UUID,
        visit_id: uuid.UUID,
        run_id: uuid.UUID,
        step: str,
    ) -> bool:
        run_id = await self.session.scalar(
            select(PipelineRun.id)
            .join(Visit, Visit.id == PipelineRun.visit_id)
            .where(
                PipelineRun.visit_id == visit_id,
                PipelineRun.run_id == run_id,
                PipelineRun.step == step,
                PipelineRun.status == "success",
                Visit.workspace_id == workspace_id,
            )
            .limit(1)
        )
        return run_id is not None

    async def delete_ai_observations(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> None:
        scoped_visit = select(Visit.id).where(
            Visit.id == visit_id, Visit.workspace_id == workspace_id
        )
        await self.session.execute(
            delete(Observation).where(
                Observation.visit_id.in_(scoped_visit),
                Observation.source_type == "ai_generated",
            )
        )

    async def delete_pending_reports(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> None:
        scoped_visit = select(Visit.id).where(
            Visit.id == visit_id, Visit.workspace_id == workspace_id
        )
        await self.session.execute(
            delete(Report).where(
                Report.visit_id.in_(scoped_visit),
                Report.status == "pending_review",
            )
        )

    async def delete_zones(self, workspace_id: uuid.UUID, visit_id: uuid.UUID) -> None:
        scoped_visit = select(Visit.id).where(
            Visit.id == visit_id, Visit.workspace_id == workspace_id
        )
        await self.session.execute(delete(Zone).where(Zone.visit_id.in_(scoped_visit)))

    async def delete_transcripts(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> None:
        scoped_visit = select(Visit.id).where(
            Visit.id == visit_id, Visit.workspace_id == workspace_id
        )
        await self.session.execute(
            delete(TranscriptSegment).where(
                TranscriptSegment.visit_id.in_(scoped_visit)
            )
        )

    def add(self, *entities: object) -> None:
        self.session.add_all(entities)
