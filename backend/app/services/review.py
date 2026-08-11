import copy
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Observation, Report, ReportRevision, TranscriptSegment, Visit
from app.repositories import ReviewRepository
from app.schemas.review import ObservationCreate, ObservationUpdate
from app.services.context import CurrentContext
from app.services.exceptions import (
    DomainValidationError,
    PropertyRequiredError,
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
        # All report lifecycle mutations use the same lock order: parent
        # visit first, then report.  The initial report lookup only discovers
        # the parent id; reload both rows after locking so this request cannot
        # edit a stale snapshot after a concurrent delivery transition.
        visit = await self._repository.get_visit_for_update(
            context.workspace.id, report.visit_id
        )
        if visit is None:
            raise ResourceNotFoundError
        report = await self._repository.get_report_for_update(
            context.workspace.id, report_id
        )
        if report is None:
            raise ResourceNotFoundError
        if visit.status == "sent_to_client":
            raise ResourceConflictError("sent showings cannot be changed")

        previous_content = copy.deepcopy(report.content)
        normalized_content = copy.deepcopy(content)
        await self._validate_report_references(
            context.workspace.id, visit.id, normalized_content
        )

        # Pydantic has already normalized the request at the API boundary
        # (including default empty sections).  A semantically identical JSON
        # document is therefore a no-op, not an audit revision.
        if previous_content == normalized_content:
            return report

        report.content = normalized_content
        if visit.status == "confirmed":
            branding = await self._repository.get_branding(context.workspace.id)
            report.rendered_html = await self._renderer.render_html(
                normalized_content, branding, consent_ack=visit.consent_ack
            )
            report.status = "confirmed"
        else:
            report.rendered_html = None
            report.status = "pending_review"
        revision_number = await self._repository.next_report_revision_number(
            context.workspace.id, report.id
        )
        self._repository.add(
            ReportRevision(
                workspace_id=context.workspace.id,
                report_id=report.id,
                visit_id=visit.id,
                edited_by=context.user.id,
                revision_number=revision_number,
                previous_content=previous_content,
                new_content=copy.deepcopy(normalized_content),
            )
        )
        await self._repository.flush()
        return report

    async def list_report_revisions(
        self, context: CurrentContext, report_id: uuid.UUID
    ) -> list[ReportRevision]:
        if await self._repository.get_report(context.workspace.id, report_id) is None:
            raise ResourceNotFoundError
        return await self._repository.list_report_revisions(
            context.workspace.id, report_id
        )

    async def confirm_showing(
        self, context: CurrentContext, visit_id: uuid.UUID
    ) -> tuple[Visit, Report]:
        # Keep this transition in the same visit -> report lock order as
        # report edits and delivery.  Otherwise confirmation could race an
        # edit and render content that is no longer the report snapshot.
        visit = await self._repository.get_visit_for_update(
            context.workspace.id, visit_id
        )
        if visit is None:
            raise ResourceNotFoundError
        if visit.status == "sent_to_client":
            raise ResourceConflictError("sent showings cannot be changed")
        report = await self._repository.get_visit_report(context.workspace.id, visit.id)
        if report is None:
            raise ResourceConflictError("showing has no report to confirm")
        report = await self._repository.get_report_for_update(
            context.workspace.id, report.id
        )
        if report is None:
            raise ResourceConflictError("showing has no report to confirm")
        if visit.subject_id is None:
            raise PropertyRequiredError
        await self._validate_report_references(
            context.workspace.id, visit.id, report.content
        )
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
        report.rendered_html = await self._renderer.render_html(
            report.content, branding, consent_ack=visit.consent_ack
        )
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
        if (
            zone_id is not None
            and await self._repository.get_zone(workspace_id, visit_id, zone_id) is None
        ):
            raise ResourceNotFoundError

    async def _validate_report_references(
        self,
        workspace_id: uuid.UUID,
        visit_id: uuid.UUID,
        content: dict[str, object],
    ) -> None:
        observation_ids, zone_ids = self._report_reference_ids(content)
        (
            valid_observation_zones,
            valid_zone_ids,
        ) = await self._repository.report_reference_ids(
            workspace_id,
            visit_id,
            observation_ids,
            zone_ids,
        )
        if (
            set(valid_observation_zones) != observation_ids
            or valid_zone_ids != zone_ids
        ):
            raise ResourceNotFoundError
        self._validate_room_evidence(content, valid_observation_zones, valid_zone_ids)

    @classmethod
    def _validate_room_evidence(
        cls,
        content: dict[str, object],
        observation_zones: dict[uuid.UUID, uuid.UUID | None],
        zone_ids: set[uuid.UUID],
    ) -> None:
        """Keep room evidence bound to one visit zone.

        Visit-level observations intentionally remain valid evidence for the
        non-room summary sections. They cannot be placed in ``room_by_room``:
        a room entry always needs a real Zone owned by the report Visit, and
        every observation cited by that entry must point to that same Zone.
        """

        room_by_room = content.get("room_by_room", [])
        if not isinstance(room_by_room, list):
            raise DomainValidationError("report room_by_room must be a list")
        for room in room_by_room:
            if not isinstance(room, dict):
                raise DomainValidationError("report room entries must be objects")
            raw_zone_id = room.get("zone_id")
            if raw_zone_id is None:
                raise DomainValidationError(
                    "room_by_room entries must reference a visit zone; "
                    "put visit-level observations in highlights, concerns, "
                    "or follow-ups"
                )
            zone_id = cls._parse_reference_id(raw_zone_id)
            if zone_id not in zone_ids:
                # This normally gets caught by the repository set comparison,
                # but keeping the guard here makes the invariant explicit for
                # direct service callers too.
                raise ResourceNotFoundError
            bullets = room.get("bullets", [])
            if not isinstance(bullets, list):
                raise DomainValidationError("report room bullets must be a list")
            for bullet in bullets:
                if not isinstance(bullet, dict):
                    raise DomainValidationError("report bullets must be objects")
                references = bullet.get("observation_ids", [])
                if not isinstance(references, list):
                    raise DomainValidationError("report observation_ids must be a list")
                for reference in references:
                    observation_id = cls._parse_reference_id(reference)
                    if observation_zones.get(observation_id) != zone_id:
                        raise DomainValidationError(
                            "room evidence must reference observations from the "
                            "same zone"
                        )

    @staticmethod
    def _report_reference_ids(
        content: dict[str, object],
    ) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
        observation_ids: set[uuid.UUID] = set()
        zone_ids: set[uuid.UUID] = set()

        def collect_observation_ids(value: object) -> None:
            if isinstance(value, dict):
                references = value.get("observation_ids")
                if references is not None:
                    if not isinstance(references, list):
                        raise DomainValidationError(
                            "report observation_ids must be a list"
                        )
                    observation_ids.update(
                        RealEstateReviewService._parse_reference_id(reference)
                        for reference in references
                    )
                for nested in value.values():
                    collect_observation_ids(nested)
            elif isinstance(value, list):
                for nested in value:
                    collect_observation_ids(nested)

        room_by_room = content.get("room_by_room", [])
        if isinstance(room_by_room, list):
            for room in room_by_room:
                if not isinstance(room, dict):
                    continue
                zone_id = room.get("zone_id")
                if zone_id is not None:
                    zone_ids.add(RealEstateReviewService._parse_reference_id(zone_id))

        collect_observation_ids(content)
        return observation_ids, zone_ids

    @staticmethod
    def _parse_reference_id(value: object) -> uuid.UUID:
        try:
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        except (AttributeError, ValueError, TypeError) as exc:
            raise DomainValidationError(
                "report references must contain valid IDs"
            ) from exc

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
