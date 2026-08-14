import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Observation,
    RawMedia,
    Report,
    ReportRevision,
    Subject,
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

    async def get_visit_for_update(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> Visit | None:
        """Load the visit while taking the lifecycle lock.

        Report edits and delivery transitions must always lock the parent
        ``visits`` row before locking the report row.  Keeping this operation
        in the repository makes that ordering explicit at each service call
        site and scopes the lock by workspace.
        """

        return await self.session.scalar(
            select(Visit)
            .where(
                Visit.id == visit_id,
                Visit.workspace_id == workspace_id,
            )
            .with_for_update()
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

    async def get_report_for_update(
        self, workspace_id: uuid.UUID, report_id: uuid.UUID
    ) -> Report | None:
        """Load a report after its visit lock has been acquired.

        ``populate_existing`` is important when a caller first looked up the
        report only to discover its visit id: a concurrent transaction may
        have changed the report before this locking query runs.
        """

        statement = (
            select(Report)
            .join(Visit, Visit.id == Report.visit_id)
            .where(Report.id == report_id, Visit.workspace_id == workspace_id)
            .execution_options(populate_existing=True)
            .with_for_update(of=Report)
        )
        return await self.session.scalar(statement)

    async def report_reference_ids(
        self,
        workspace_id: uuid.UUID,
        visit_id: uuid.UUID,
        observation_ids: set[uuid.UUID],
        zone_ids: set[uuid.UUID],
    ) -> tuple[dict[uuid.UUID, uuid.UUID | None], set[uuid.UUID]]:
        """Return report evidence owned by the workspace and report visit.

        The observation-to-zone mapping is needed by report review validation:
        same-visit evidence is valid for summary sections, but room evidence
        must also belong to the room's exact zone.
        """

        valid_observation_zones: dict[uuid.UUID, uuid.UUID | None] = {}
        if observation_ids:
            result = await self.session.execute(
                select(Observation.id, Observation.zone_id)
                .join(Visit, Visit.id == Observation.visit_id)
                .where(
                    Observation.id.in_(observation_ids),
                    Observation.visit_id == visit_id,
                    Visit.workspace_id == workspace_id,
                )
            )
            valid_observation_zones = {
                observation_id: zone_id for observation_id, zone_id in result.all()
            }

        valid_zone_ids: set[uuid.UUID] = set()
        if zone_ids:
            result = await self.session.scalars(
                select(Zone.id)
                .join(Visit, Visit.id == Zone.visit_id)
                .where(
                    Zone.id.in_(zone_ids),
                    Zone.visit_id == visit_id,
                    Visit.workspace_id == workspace_id,
                )
            )
            valid_zone_ids = set(result)

        return valid_observation_zones, valid_zone_ids

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

    async def list_report_revisions(
        self, workspace_id: uuid.UUID, report_id: uuid.UUID
    ) -> list[ReportRevision]:
        """Return only revisions belonging to the caller's workspace/report."""

        result = await self.session.scalars(
            select(ReportRevision)
            .join(Report, Report.id == ReportRevision.report_id)
            .join(Visit, Visit.id == Report.visit_id)
            .where(
                ReportRevision.report_id == report_id,
                ReportRevision.workspace_id == workspace_id,
                ReportRevision.visit_id == Report.visit_id,
                Visit.workspace_id == workspace_id,
            )
            .order_by(ReportRevision.revision_number.asc())
        )
        return list(result)

    async def next_report_revision_number(
        self, workspace_id: uuid.UUID, report_id: uuid.UUID
    ) -> int:
        """Return the next durable number after the report row is locked.

        Callers must hold the report's row lock before invoking this method.
        Report edits acquire that lock before reaching this point, so two
        concurrent edits observe a serialized maximum.  The database unique
        constraint remains the final guard against an out-of-band insert.
        """

        latest_number = await self.session.scalar(
            select(func.max(ReportRevision.revision_number)).where(
                ReportRevision.report_id == report_id,
                ReportRevision.workspace_id == workspace_id,
            )
        )
        return (latest_number or 0) + 1

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

    async def placed_photos(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> list[RawMedia]:
        """Uploaded photos that were placed in a room, in capture order."""

        result = await self.session.scalars(
            select(RawMedia)
            .join(Visit, Visit.id == RawMedia.visit_id)
            .where(
                RawMedia.visit_id == visit_id,
                RawMedia.type == "photo",
                RawMedia.status == "uploaded",
                RawMedia.zone_id.is_not(None),
                Visit.workspace_id == workspace_id,
            )
            .order_by(RawMedia.timestamp_offset_ms, RawMedia.created_at, RawMedia.id)
        )
        return list(result)

    async def get_subject(
        self, workspace_id: uuid.UUID, subject_id: uuid.UUID | None
    ) -> Subject | None:
        if subject_id is None:
            return None
        return await self.session.scalar(
            select(Subject).where(
                Subject.id == subject_id,
                Subject.workspace_id == workspace_id,
            )
        )
