import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Observation, Report, TranscriptSegment, Visit
from app.repositories import ReviewRepository
from app.schemas.review import ObservationCreate, ObservationUpdate
from app.services.context import CurrentContext
from app.services.exceptions import (
    DomainValidationError,
    ResourceConflictError,
    ResourceNotFoundError,
    SensitiveReviewRequiredError,
)
from app.services.renderer import ReportRenderer
from app.verticals import VerticalConfigService


class RealEstateReviewService:
    def __init__(
        self,
        session: AsyncSession,
        verticals: VerticalConfigService,
        renderer: ReportRenderer,
    ) -> None:
        self._repository = ReviewRepository(session)
        self._verticals = verticals
        self._renderer = renderer

    async def update_observation(
        self,
        context: CurrentContext,
        observation_id: uuid.UUID,
        payload: ObservationUpdate,
    ) -> Observation:
        observation = await self._require_observation(
            context.workspace.id, observation_id
        )
        await self._require_editable_visit(context.workspace.id, observation.visit_id)
        if "category" in payload.model_fields_set:
            self._validate_category(payload.category or "")
            observation.category = payload.category or ""
        if "content" in payload.model_fields_set:
            observation.content = payload.content or ""
        if "zone_id" in payload.model_fields_set:
            await self._validate_zone(
                context.workspace.id, observation.visit_id, payload.zone_id
            )
            observation.zone_id = payload.zone_id
        self._mark_reviewed(observation, context.user.id, "edited")
        observation.source_type = "professional_edited"
        await self._repository.flush()
        return observation

    async def confirm_observation(
        self, context: CurrentContext, observation_id: uuid.UUID
    ) -> Observation:
        observation = await self._require_observation(
            context.workspace.id, observation_id
        )
        await self._require_editable_visit(context.workspace.id, observation.visit_id)
        self._mark_reviewed(observation, context.user.id, "confirmed")
        await self._repository.flush()
        return observation

    async def dismiss_observation(
        self, context: CurrentContext, observation_id: uuid.UUID
    ) -> Observation:
        observation = await self._require_observation(
            context.workspace.id, observation_id
        )
        await self._require_editable_visit(context.workspace.id, observation.visit_id)
        self._mark_reviewed(observation, context.user.id, "dismissed")
        await self._repository.flush()
        return observation

    async def add_observation(
        self, context: CurrentContext, payload: ObservationCreate
    ) -> Observation:
        visit = await self._require_editable_visit(
            context.workspace.id, payload.visit_id
        )
        self._validate_category(payload.category)
        await self._validate_zone(context.workspace.id, visit.id, payload.zone_id)
        segment = None
        if payload.source_transcript_segment_id is not None:
            segment = await self._repository.get_segment(
                context.workspace.id, payload.source_transcript_segment_id
            )
            if segment is None or segment.visit_id != visit.id:
                raise ResourceNotFoundError
        observation = Observation(
            visit_id=visit.id,
            zone_id=payload.zone_id,
            category=payload.category,
            content=payload.content,
            source_type="professional_edited",
            source_transcript_segment_id=segment.id if segment else None,
            source_media_id=segment.raw_media_id if segment else None,
            timestamp_start=segment.timestamp_start if segment else None,
            timestamp_end=segment.timestamp_end if segment else None,
            ai_model=None,
            prompt_version=None,
            confidence=None,
            flags={},
            review_status="edited",
            reviewed_by=context.user.id,
            reviewed_at=datetime.now(UTC),
        )
        self._repository.add(observation)
        await self._repository.flush()
        return observation

    async def update_transcript_segment(
        self,
        context: CurrentContext,
        segment_id: uuid.UUID,
        text: str,
    ) -> TranscriptSegment:
        segment = await self._repository.get_segment(context.workspace.id, segment_id)
        if segment is None:
            raise ResourceNotFoundError
        await self._require_editable_visit(context.workspace.id, segment.visit_id)
        if segment.original_text is None:
            segment.original_text = segment.text
        segment.text = text
        await self._repository.flush()
        return segment

    async def update_report(
        self,
        context: CurrentContext,
        report_id: uuid.UUID,
        content: dict[str, object],
    ) -> Report:
        report = await self._repository.get_report(context.workspace.id, report_id)
        if report is None:
            raise ResourceNotFoundError
        visit = await self._require_editable_visit(
            context.workspace.id, report.visit_id
        )
        report.content = content
        if visit.status == "confirmed":
            branding = await self._repository.get_branding(context.workspace.id)
            report.rendered_html = await self._renderer.render_html(content, branding)
            report.status = "confirmed"
        else:
            report.rendered_html = None
            report.status = "pending_review"
        await self._repository.flush()
        return report

    async def confirm_showing(
        self, context: CurrentContext, visit_id: uuid.UUID
    ) -> tuple[Visit, Report]:
        visit = await self._repository.get_visit(context.workspace.id, visit_id)
        if visit is None:
            raise ResourceNotFoundError
        if visit.status == "sent_to_client":
            raise ResourceConflictError("sent showings cannot be changed")
        report = await self._repository.get_visit_report(context.workspace.id, visit.id)
        if report is None:
            raise ResourceConflictError("showing has no report to confirm")
        reviewed = await self._repository.reviewed_observations(
            context.workspace.id, visit.id
        )
        if not reviewed:
            raise DomainValidationError(
                "at least one observation must be reviewed before confirmation"
            )
        sensitive = await self._repository.pending_sensitive_observations(
            context.workspace.id, visit.id
        )
        if sensitive:
            raise SensitiveReviewRequiredError([str(item.id) for item in sensitive])
        branding = await self._repository.get_branding(context.workspace.id)
        report.rendered_html = await self._renderer.render_html(report.content, branding)
        report.status = "confirmed"
        visit.status = "confirmed"
        await self._repository.flush()
        return visit, report

    async def _require_observation(
        self, workspace_id: uuid.UUID, observation_id: uuid.UUID
    ) -> Observation:
        observation = await self._repository.get_observation(
            workspace_id, observation_id
        )
        if observation is None:
            raise ResourceNotFoundError
        return observation

    async def _require_editable_visit(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> Visit:
        visit = await self._repository.get_visit(workspace_id, visit_id)
        if visit is None:
            raise ResourceNotFoundError
        if visit.status == "sent_to_client":
            raise ResourceConflictError("sent showings cannot be changed")
        return visit

    async def _validate_zone(
        self,
        workspace_id: uuid.UUID,
        visit_id: uuid.UUID,
        zone_id: uuid.UUID | None,
    ) -> None:
        if zone_id is not None and await self._repository.get_zone(
            workspace_id, visit_id, zone_id
        ) is None:
            raise ResourceNotFoundError

    def _validate_category(self, category: str) -> None:
        if category not in self._verticals.get().observation_schema:
            raise DomainValidationError("unsupported observation category")

    @staticmethod
    def _mark_reviewed(
        observation: Observation, user_id: uuid.UUID, status: str
    ) -> None:
        observation.review_status = status
        observation.reviewed_by = user_id
        observation.reviewed_at = datetime.now(UTC)
