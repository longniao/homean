import time
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pipeline_config import PipelineConfig, PipelineStep
from app.models import (
    Observation,
    PipelineRun,
    Report,
    TranscriptSegment,
    Visit,
    Zone,
)
from app.pipeline.llm import LLMClient, LLMResponse, SchemaT
from app.pipeline.prompts import PromptRenderer
from app.pipeline.schemas import (
    ObservationExtractionResult,
    RealEstateReportSchema,
    ReportBullet,
    RoomByRoomSection,
    ZoneDetectionResult,
)
from app.pipeline.transcription import TranscriptionProvider
from app.repositories import PipelineRepository
from app.repositories.billing import BillingRepository
from app.services.exceptions import ResourceConflictError, ResourceNotFoundError
from app.storage import StorageProvider
from app.verticals import VerticalConfigService

PIPELINE_STEPS = (
    PipelineStep.TRANSCRIBE,
    PipelineStep.ZONE_DETECTION,
    PipelineStep.OBSERVATION_EXTRACTION,
    PipelineStep.REPORT_GENERATION,
)


@dataclass(frozen=True)
class TimedLLMResponse:
    response: LLMResponse[SchemaT]
    duration_ms: int


@dataclass(frozen=True)
class SanitizedReport:
    content: RealEstateReportSchema
    dropped_bullets: int
    dropped_references: int


class RealEstatePipelineService:
    def __init__(
        self,
        session: AsyncSession,
        storage: StorageProvider,
        transcription: TranscriptionProvider,
        llm: LLMClient,
        config: PipelineConfig,
        verticals: VerticalConfigService,
    ) -> None:
        self._session = session
        self._repository = PipelineRepository(session)
        self._billing_repository = BillingRepository(session)
        self._storage = storage
        self._transcription = transcription
        self._llm = llm
        self._config = config
        self._verticals = verticals
        self._prompts = PromptRenderer(verticals)

    async def transcribe(self, workspace_id: uuid.UUID, visit_id: uuid.UUID) -> None:
        visit = await self._require_draft_visit(workspace_id, visit_id)
        if visit.processing_status in {"structuring", "generating", "ready"}:
            return
        visit.processing_status = "transcribing"
        visit.processing_failed_step = None
        visit.processing_error = None
        run_id = self._ensure_run_id(visit)

        audio_media = await self._repository.uploaded_audio(workspace_id, visit_id)
        if not audio_media:
            raise ValueError("showing has no uploaded audio to transcribe")
        await self._session.commit()

        for media in audio_media:
            if await self._repository.media_has_transcript(
                workspace_id, visit_id, media.id
            ):
                continue
            audio_url = await self._storage.presign_get(media.object_key, 900)
            started = time.perf_counter()
            try:
                pieces = await self._transcription.transcribe(
                    audio_url, self._config.output_language
                )
            except Exception as exc:
                await self._record_failed_call(
                    visit_id=visit_id,
                    run_id=run_id,
                    step=PipelineStep.TRANSCRIBE,
                    model=self._transcription.model,
                    prompt_version=None,
                    duration_ms=self._elapsed_ms(started),
                    error=exc,
                )
                raise
            if not pieces:
                raise ValueError(
                    "transcription provider returned no transcript segments"
                )
            offset_ms = media.timestamp_offset_ms or 0
            segments = [
                TranscriptSegment(
                    id=uuid.uuid5(
                        media.id,
                        f"{index}:{piece.start_ms}:{piece.end_ms}:{piece.text}",
                    ),
                    visit_id=visit_id,
                    raw_media_id=media.id,
                    text=piece.text,
                    timestamp_start=piece.start_ms + offset_ms,
                    timestamp_end=piece.end_ms + offset_ms,
                    confidence=piece.confidence,
                )
                for index, piece in enumerate(pieces)
            ]
            self._repository.add(
                *segments,
                PipelineRun(
                    visit_id=visit_id,
                    run_id=run_id,
                    step=PipelineStep.TRANSCRIBE,
                    model=self._transcription.model,
                    prompt_version=None,
                    tokens_in=0,
                    tokens_out=0,
                    duration_ms=self._elapsed_ms(started),
                    status="success",
                ),
            )
        await self._session.commit()

    async def detect_zones(self, workspace_id: uuid.UUID, visit_id: uuid.UUID) -> None:
        visit = await self._require_draft_visit(workspace_id, visit_id)
        if visit.processing_status in {"generating", "ready"}:
            return
        run_id = self._ensure_run_id(visit)
        if await self._repository.has_successful_run(
            workspace_id, visit_id, run_id, PipelineStep.ZONE_DETECTION
        ):
            return
        visit.processing_status = "structuring"
        await self._session.commit()
        segments = await self._repository.transcripts(workspace_id, visit_id)
        if not segments:
            raise ValueError("zone detection requires transcript segments")
        pack = self._verticals.get()
        transcript = [self._segment_payload(segment) for segment in segments]
        prompt = self._prompts.render(
            pack,
            "zone_detection",
            zone_taxonomy=pack.zone_taxonomy,
            output_language=self._config.output_language,
            transcript=transcript,
        )
        invocation = await self._invoke_llm(
            visit_id=visit_id,
            run_id=run_id,
            step=PipelineStep.ZONE_DETECTION,
            prompt_version=pack.prompt_version,
            prompt=prompt,
            output_format=ZoneDetectionResult,
        )
        segment_positions = {
            segment.id: position for position, segment in enumerate(segments)
        }
        zones: list[Zone] = []
        previous_end = -1
        for zone_range in invocation.response.parsed.zones:
            start = segment_positions.get(zone_range.start_segment_id)
            end = segment_positions.get(zone_range.end_segment_id)
            if (
                zone_range.zone_type not in pack.zone_taxonomy
                or start is None
                or end is None
                or start > end
                or start <= previous_end
            ):
                continue
            zones.append(
                Zone(
                    visit_id=visit_id,
                    zone_type=zone_range.zone_type,
                    position=len(zones),
                    start_transcript_segment_id=zone_range.start_segment_id,
                    end_transcript_segment_id=zone_range.end_segment_id,
                )
            )
            previous_end = end
        self._repository.add(
            *zones,
            self._successful_run(
                visit_id,
                run_id,
                PipelineStep.ZONE_DETECTION,
                pack.prompt_version,
                invocation,
            ),
        )
        await self._session.commit()

    async def extract_observations(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> None:
        visit = await self._require_draft_visit(workspace_id, visit_id)
        if visit.processing_status in {"generating", "ready"}:
            return
        run_id = self._ensure_run_id(visit)
        if await self._repository.has_successful_run(
            workspace_id, visit_id, run_id, PipelineStep.OBSERVATION_EXTRACTION
        ):
            visit.processing_status = "generating"
            await self._session.commit()
            return
        visit.processing_status = "structuring"
        segments = await self._repository.transcripts(workspace_id, visit_id)
        zones = await self._repository.zones(workspace_id, visit_id)
        if not segments:
            raise ValueError("observation extraction requires transcript segments")
        pack = self._verticals.get()
        batches = self._zone_batches(zones, segments)
        prompt = self._prompts.render(
            pack,
            "observation_extraction",
            observation_schema=pack.observation_schema,
            output_language=self._config.output_language,
            zones=batches,
        )
        invocation = await self._invoke_llm(
            visit_id=visit_id,
            run_id=run_id,
            step=PipelineStep.OBSERVATION_EXTRACTION,
            prompt_version=pack.prompt_version,
            prompt=prompt,
            output_format=ObservationExtractionResult,
        )
        segments_by_id = {segment.id: segment for segment in segments}
        expected_zone_by_segment = {
            uuid.UUID(str(segment["id"])): (
                uuid.UUID(str(batch["zone_id"]))
                if batch["zone_id"] is not None
                else None
            )
            for batch in batches
            for segment in batch["segments"]
        }
        observations: list[Observation] = []
        for extracted in invocation.response.parsed.observations:
            source = segments_by_id.get(extracted.source_transcript_segment_id)
            if (
                source is None
                or extracted.category not in pack.observation_schema
                or extracted.zone_id != expected_zone_by_segment[source.id]
            ):
                continue
            observations.append(
                Observation(
                    visit_id=visit_id,
                    zone_id=extracted.zone_id,
                    category=extracted.category,
                    content=extracted.content,
                    source_type="ai_generated",
                    source_transcript_segment_id=source.id,
                    source_media_id=source.raw_media_id,
                    timestamp_start=source.timestamp_start,
                    timestamp_end=source.timestamp_end,
                    ai_model=invocation.response.model,
                    prompt_version=pack.prompt_version,
                    confidence=extracted.confidence,
                    flags=extracted.flags.model_dump(exclude_none=True),
                    review_status="pending",
                )
            )
        visit.processing_status = "generating"
        self._repository.add(
            *observations,
            self._successful_run(
                visit_id,
                run_id,
                PipelineStep.OBSERVATION_EXTRACTION,
                pack.prompt_version,
                invocation,
            ),
        )
        await self._session.commit()

    async def generate_report(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> None:
        visit = await self._require_draft_visit(workspace_id, visit_id)
        if visit.processing_status == "ready":
            return
        run_id = self._ensure_run_id(visit)
        if await self._repository.has_successful_run(
            workspace_id, visit_id, run_id, PipelineStep.REPORT_GENERATION
        ):
            visit.processing_status = "ready"
            await self._session.commit()
            return
        visit.processing_status = "generating"
        zones = await self._repository.zones(workspace_id, visit_id)
        observations = await self._repository.observations(workspace_id, visit_id)
        pack = self._verticals.get()
        prompt = self._prompts.render(
            pack,
            "report_generation",
            labels={
                "zones": pack.display_labels.zones,
                "observations": pack.display_labels.observations,
                "report": pack.report_template.labels,
            },
            output_language=self._config.output_language,
            zones=[
                self._zone_payload(zone, pack.display_labels.zones) for zone in zones
            ],
            observations=[self._observation_payload(item) for item in observations],
        )
        invocation = await self._invoke_llm(
            visit_id=visit_id,
            run_id=run_id,
            step=PipelineStep.REPORT_GENERATION,
            prompt_version=pack.prompt_version,
            prompt=prompt,
            output_format=RealEstateReportSchema,
        )
        sanitized = self._sanitize_report(
            invocation.response.parsed,
            {observation.id: observation.zone_id for observation in observations},
            {zone.id for zone in zones},
        )
        await self._repository.delete_pending_reports(workspace_id, visit_id)
        report = Report(
            visit_id=visit_id,
            template_id=pack.report_template_id,
            content=sanitized.content.model_dump(mode="json"),
            rendered_html=None,
            status="pending_review",
        )
        visit.processing_status = "ready"
        visit.processing_failed_step = None
        visit.processing_error = None
        report_run = self._successful_run(
            visit_id,
            run_id,
            PipelineStep.REPORT_GENERATION,
            pack.prompt_version,
            invocation,
        )
        if sanitized.dropped_bullets or sanitized.dropped_references:
            report_run.error = (
                "report_integrity:"
                f"dropped_bullets={sanitized.dropped_bullets},"
                f"dropped_refs={sanitized.dropped_references}"
            )
        self._repository.add(report, report_run)
        await self._billing_repository.increment_report_usage(
            workspace_id, date.today().replace(day=1)
        )
        await self._session.commit()

    async def mark_failed(
        self,
        workspace_id: uuid.UUID,
        visit_id: uuid.UUID,
        step: PipelineStep,
        error: Exception,
    ) -> None:
        await self._session.rollback()
        visit = await self._repository.get_visit(workspace_id, visit_id)
        if visit is None:
            return
        visit.processing_status = "failed"
        visit.processing_failed_step = step
        visit.processing_error = self._error_text(error)
        await self._session.commit()

    async def run_step(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID, step: PipelineStep
    ) -> None:
        handlers = {
            PipelineStep.TRANSCRIBE: self.transcribe,
            PipelineStep.ZONE_DETECTION: self.detect_zones,
            PipelineStep.OBSERVATION_EXTRACTION: self.extract_observations,
            PipelineStep.REPORT_GENERATION: self.generate_report,
        }
        try:
            await handlers[step](workspace_id, visit_id)
        except Exception as exc:
            await self.mark_failed(workspace_id, visit_id, step, exc)
            raise

    async def run_all(
        self,
        workspace_id: uuid.UUID,
        visit_id: uuid.UUID,
        start_step: PipelineStep = PipelineStep.TRANSCRIBE,
    ) -> bool:
        start_index = PIPELINE_STEPS.index(start_step)
        for step in PIPELINE_STEPS[start_index:]:
            try:
                await self.run_step(workspace_id, visit_id, step)
            except Exception:
                return False
        return True

    async def _require_draft_visit(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> Visit:
        visit = await self._repository.get_visit(workspace_id, visit_id)
        if visit is None:
            raise ResourceNotFoundError
        if visit.status != "draft":
            raise ResourceConflictError("only draft showings can be processed")
        return visit

    async def _invoke_llm(
        self,
        *,
        visit_id: uuid.UUID,
        run_id: uuid.UUID,
        step: PipelineStep,
        prompt_version: str,
        prompt: str,
        output_format: type[SchemaT],
    ) -> TimedLLMResponse:
        model = self._config.model_for(step)
        started = time.perf_counter()
        try:
            response = await self._llm.parse(
                prompt=prompt,
                model=model,
                max_tokens=self._config.max_tokens,
                output_format=output_format,
            )
        except Exception as exc:
            await self._record_failed_call(
                visit_id=visit_id,
                run_id=run_id,
                step=step,
                model=model,
                prompt_version=prompt_version,
                duration_ms=self._elapsed_ms(started),
                error=exc,
            )
            raise
        return TimedLLMResponse(
            response=response, duration_ms=self._elapsed_ms(started)
        )

    async def _record_failed_call(
        self,
        *,
        visit_id: uuid.UUID,
        run_id: uuid.UUID,
        step: PipelineStep,
        model: str,
        prompt_version: str | None,
        duration_ms: int,
        error: Exception,
    ) -> None:
        await self._session.rollback()
        self._repository.add(
            PipelineRun(
                visit_id=visit_id,
                run_id=run_id,
                step=step,
                model=model,
                prompt_version=prompt_version,
                tokens_in=0,
                tokens_out=0,
                duration_ms=duration_ms,
                status="error",
                error=self._error_text(error),
            )
        )
        await self._session.commit()

    @staticmethod
    def _successful_run(
        visit_id: uuid.UUID,
        run_id: uuid.UUID,
        step: PipelineStep,
        prompt_version: str,
        invocation: TimedLLMResponse,
    ) -> PipelineRun:
        return PipelineRun(
            visit_id=visit_id,
            run_id=run_id,
            step=step,
            model=invocation.response.model,
            prompt_version=prompt_version,
            tokens_in=invocation.response.tokens_in,
            tokens_out=invocation.response.tokens_out,
            duration_ms=invocation.duration_ms,
            status="success",
        )

    @staticmethod
    def _ensure_run_id(visit: Visit) -> uuid.UUID:
        if visit.processing_run_id is None:
            visit.processing_run_id = uuid.uuid4()
        return visit.processing_run_id

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return max(0, round((time.perf_counter() - started) * 1000))

    @staticmethod
    def _error_text(error: Exception) -> str:
        return f"{type(error).__name__}: {error}"[:4000]

    @staticmethod
    def _segment_payload(segment: TranscriptSegment) -> dict[str, object]:
        return {
            "id": str(segment.id),
            "text": segment.text,
            "start_ms": segment.timestamp_start,
            "end_ms": segment.timestamp_end,
        }

    def _zone_batches(
        self, zones: list[Zone], segments: list[TranscriptSegment]
    ) -> list[dict[str, object]]:
        segment_positions = {
            segment.id: position for position, segment in enumerate(segments)
        }
        covered: set[uuid.UUID] = set()
        batches: list[dict[str, object]] = []
        for zone in zones:
            start = segment_positions.get(zone.start_transcript_segment_id)
            end = segment_positions.get(zone.end_transcript_segment_id)
            if start is None or end is None or start > end:
                continue
            evidence = segments[start : end + 1]
            covered.update(segment.id for segment in evidence)
            batches.append(
                {
                    "zone_id": str(zone.id),
                    "zone_type": zone.zone_type,
                    "segments": [self._segment_payload(item) for item in evidence],
                }
            )
        unzoned = [segment for segment in segments if segment.id not in covered]
        if unzoned:
            batches.append(
                {
                    "zone_id": None,
                    "zone_type": None,
                    "segments": [self._segment_payload(item) for item in unzoned],
                }
            )
        return batches

    @staticmethod
    def _zone_payload(zone: Zone, labels: dict[str, str]) -> dict[str, object]:
        return {
            "id": str(zone.id),
            "zone_type": zone.zone_type,
            "label": labels[zone.zone_type],
            "position": zone.position,
        }

    @staticmethod
    def _observation_payload(observation: Observation) -> dict[str, object]:
        return {
            "id": str(observation.id),
            "zone_id": str(observation.zone_id) if observation.zone_id else None,
            "category": observation.category,
            "content": observation.content,
            "flags": observation.flags,
        }

    @classmethod
    def _sanitize_report(
        cls,
        report: RealEstateReportSchema,
        observation_zones: dict[uuid.UUID, uuid.UUID | None],
        zone_ids: set[uuid.UUID],
    ) -> SanitizedReport:
        dropped_bullets = 0
        dropped_references = 0

        def bullets(
            items: list[ReportBullet],
            room_zone_id: uuid.UUID | None = None,
        ) -> list[ReportBullet]:
            nonlocal dropped_bullets, dropped_references
            sanitized: list[ReportBullet] = []
            for item in items:
                valid_ids = [
                    observation_id
                    for observation_id in item.observation_ids
                    if observation_id in observation_zones
                    and (
                        room_zone_id is None
                        or observation_zones[observation_id] == room_zone_id
                    )
                ]
                dropped_references += len(item.observation_ids) - len(valid_ids)
                if valid_ids:
                    sanitized.append(
                        ReportBullet(text=item.text, observation_ids=valid_ids)
                    )
                else:
                    dropped_bullets += 1
            return sanitized

        room_by_room: list[RoomByRoomSection] = []
        for section in report.room_by_room:
            valid_zone_reference = (
                section.zone_id is not None and section.zone_id in zone_ids
            )
            if section.zone_id is None:
                # Visit-level observations have no room binding. Keep them
                # available to highlights/concerns/follow-ups, but never
                # represent them as a room section.
                dropped_bullets += len(section.bullets)
                dropped_references += sum(
                    len(item.observation_ids) for item in section.bullets
                )
                continue
            if not valid_zone_reference:
                sanitized_bullets = bullets(section.bullets)
                dropped_bullets += len(sanitized_bullets)
                continue
            sanitized_bullets = bullets(section.bullets, section.zone_id)
            if not sanitized_bullets:
                continue
            room_by_room.append(
                RoomByRoomSection(
                    zone_id=section.zone_id,
                    zone_type=section.zone_type,
                    bullets=sanitized_bullets,
                )
            )

        content = RealEstateReportSchema(
            executive_summary=report.executive_summary,
            room_by_room=room_by_room,
            highlights=bullets(report.highlights),
            concerns=bullets(report.concerns),
            follow_ups=bullets(report.follow_ups),
        )
        return SanitizedReport(
            content=content,
            dropped_bullets=dropped_bullets,
            dropped_references=dropped_references,
        )
