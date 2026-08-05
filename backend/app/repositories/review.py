import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Observation,
    Report,
    TranscriptSegment,
    Visit,
    WorkspaceBranding,
    Zone,
)


class ReviewRepository:
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

    async def get_observation(
        self, workspace_id: uuid.UUID, observation_id: uuid.UUID
    ) -> Observation | None:
        return await self.session.scalar(
            select(Observation)
            .join(Visit, Visit.id == Observation.visit_id)
            .where(
                Observation.id == observation_id,
                Visit.workspace_id == workspace_id,
            )
        )

    async def get_zone(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID, zone_id: uuid.UUID
    ) -> Zone | None:
        return await self.session.scalar(
            select(Zone)
            .join(Visit, Visit.id == Zone.visit_id)
            .where(
                Zone.id == zone_id,
                Zone.visit_id == visit_id,
                Visit.workspace_id == workspace_id,
            )
        )

    async def get_segment(
        self, workspace_id: uuid.UUID, segment_id: uuid.UUID
    ) -> TranscriptSegment | None:
        return await self.session.scalar(
            select(TranscriptSegment)
            .join(Visit, Visit.id == TranscriptSegment.visit_id)
            .where(
                TranscriptSegment.id == segment_id,
                Visit.workspace_id == workspace_id,
            )
        )

    async def get_report(
        self, workspace_id: uuid.UUID, report_id: uuid.UUID
    ) -> Report | None:
        return await self.session.scalar(
            select(Report)
            .join(Visit, Visit.id == Report.visit_id)
            .where(Report.id == report_id, Visit.workspace_id == workspace_id)
        )

    async def get_visit_report(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> Report | None:
        return await self.session.scalar(
            select(Report)
            .join(Visit, Visit.id == Report.visit_id)
            .where(Report.visit_id == visit_id, Visit.workspace_id == workspace_id)
            .order_by(Report.created_at.desc(), Report.id.desc())
            .limit(1)
        )

    async def reviewed_observations(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> list[Observation]:
        result = await self.session.scalars(
            select(Observation)
            .join(Visit, Visit.id == Observation.visit_id)
            .where(
                Observation.visit_id == visit_id,
                Observation.review_status != "pending",
                Visit.workspace_id == workspace_id,
            )
        )
        return list(result)

    async def pending_sensitive_observations(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> list[Observation]:
        result = await self.session.scalars(
            select(Observation)
            .join(Visit, Visit.id == Observation.visit_id)
            .where(
                Observation.visit_id == visit_id,
                Observation.review_status == "pending",
                Observation.flags["sensitive"].astext == "true",
                Visit.workspace_id == workspace_id,
            )
        )
        return list(result)

    async def get_branding(self, workspace_id: uuid.UUID) -> WorkspaceBranding | None:
        return await self.session.scalar(
            select(WorkspaceBranding).where(
                WorkspaceBranding.workspace_id == workspace_id
            )
        )
