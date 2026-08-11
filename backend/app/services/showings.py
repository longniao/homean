import base64
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.pipeline_config import PipelineStep
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
from app.pipeline import PipelineEnqueuer
from app.repositories import (
    AuthRepository,
    ContactRepository,
    PipelineRepository,
    PropertyRepository,
    ShowingRepository,
)
from app.schemas.showings import MediaPresignRequest, ShowingCreate, ShowingUpdate
from app.services.billing import BillingService
from app.services.context import CurrentContext
from app.services.exceptions import (
    DomainValidationError,
    PipelineUnavailableError,
    ResourceConflictError,
    ResourceNotFoundError,
    VerticalNotSeededError,
)
from app.storage import StorageProvider

MEDIA_RULES: dict[str, dict[str, tuple[str, int]]] = {
    "audio": {
        "audio/mpeg": ("mp3", 500 * 1024 * 1024),
        "audio/mp4": ("m4a", 500 * 1024 * 1024),
        "audio/wav": ("wav", 500 * 1024 * 1024),
        "audio/x-wav": ("wav", 500 * 1024 * 1024),
        "audio/webm": ("webm", 500 * 1024 * 1024),
        "audio/aac": ("aac", 500 * 1024 * 1024),
        "audio/ogg": ("ogg", 500 * 1024 * 1024),
    },
    "photo": {
        "image/jpeg": ("jpg", 25 * 1024 * 1024),
        "image/png": ("png", 25 * 1024 * 1024),
        "image/heic": ("heic", 25 * 1024 * 1024),
        "image/heif": ("heif", 25 * 1024 * 1024),
        "image/webp": ("webp", 25 * 1024 * 1024),
    },
    "video": {
        "video/mp4": ("mp4", 1024 * 1024 * 1024),
        "video/quicktime": ("mov", 1024 * 1024 * 1024),
        "video/webm": ("webm", 1024 * 1024 * 1024),
    },
}


@dataclass(frozen=True)
class ShowingRecord:
    visit: Visit
    subject: Subject | None
    contact: Contact | None


@dataclass(frozen=True)
class ShowingDetail:
    record: ShowingRecord
    media: list[RawMedia]
    zones: list[Zone]
    observations: list[Observation]
    transcript: list[TranscriptSegment]
    report: Report | None


@dataclass(frozen=True)
class ShowingPage:
    items: list[ShowingRecord]
    next_cursor: str | None


@dataclass(frozen=True)
class PresignedUpload:
    media: RawMedia
    upload_url: str
    expires_in: int
    max_size_bytes: int


@dataclass(frozen=True)
class PresignedDownload:
    download_url: str
    expires_in: int


class RealEstateShowingService:
    def __init__(
        self,
        session: AsyncSession,
        storage: StorageProvider,
        pipeline: PipelineEnqueuer,
        settings: Settings,
        billing: BillingService,
    ) -> None:
        self._repository = ShowingRepository(session)
        self._contacts = ContactRepository(session)
        self._properties = PropertyRepository(session)
        self._auth = AuthRepository(session)
        self._pipeline_repository = PipelineRepository(session)
        self._storage = storage
        self._pipeline = pipeline
        self._settings = settings
        self._billing = billing

    async def create_showing(
        self, context: CurrentContext, payload: ShowingCreate
    ) -> ShowingRecord:
        await self._billing.require_active(context)
        contact = await self._optional_contact(context.workspace.id, payload.contact_id)
        subject = None
        if payload.subject_id is not None:
            subject = await self._properties.get(
                context.workspace.id, payload.subject_id
            )
            if subject is None:
                raise ResourceNotFoundError
        elif payload.address is not None:
            subject = await self._create_inline_subject(
                context.workspace.id, payload.address
            )

        profile_context = await self._auth.get_profile(
            context.membership.id, context.workspace.id
        )
        if profile_context is None or profile_context[1].slug != "real_estate":
            raise ResourceNotFoundError
        profile, _ = profile_context
        visit = Visit(
            workspace_id=context.workspace.id,
            subject_id=subject.id if subject else None,
            created_by=context.user.id,
            contact_id=contact.id if contact else None,
            professional_profile_id=profile.id,
            started_at=datetime.now(UTC),
            status="draft",
            processing_status="not_started",
            consent_ack=payload.consent_ack,
        )
        self._repository.add(visit)
        await self._repository.flush()
        return ShowingRecord(visit=visit, subject=subject, contact=contact)

    async def update_showing(
        self,
        context: CurrentContext,
        visit_id: uuid.UUID,
        payload: ShowingUpdate,
    ) -> ShowingRecord:
        visit = await self._repository.get_visit(context.workspace.id, visit_id)
        if visit is None:
            raise ResourceNotFoundError
        if visit.status == "sent_to_client":
            raise ResourceConflictError("sent showings cannot be changed")
        if payload.subject_id is not None:
            subject = await self._properties.get(
                context.workspace.id, payload.subject_id
            )
            if subject is None:
                raise ResourceNotFoundError
        else:
            subject = await self._create_inline_subject(
                context.workspace.id, payload.address or ""
            )
        visit.subject_id = subject.id
        contact = await self._optional_contact(context.workspace.id, visit.contact_id)
        await self._repository.flush()
        await self._repository.session.refresh(visit)
        return ShowingRecord(visit=visit, subject=subject, contact=contact)

    async def presign_media(
        self,
        context: CurrentContext,
        visit_id: uuid.UUID,
        payload: MediaPresignRequest,
    ) -> PresignedUpload:
        content_type = payload.content_type.strip().lower()
        extension, max_size = self._media_rule(payload.type, content_type)
        media_id = uuid.uuid4()
        object_key = f"{context.workspace.id}/{visit_id}/{media_id}.{extension}"
        visit = await self._require_mutable_visit(context.workspace.id, visit_id)
        media = RawMedia(
            id=media_id,
            visit_id=visit.id,
            type=payload.type,
            object_key=object_key,
            content_type=content_type,
            timestamp_offset_ms=payload.timestamp_offset_ms,
            status="pending",
        )
        self._repository.add(media)
        await self._repository.flush()
        upload_url = await self._storage.presign_put(
            object_key, content_type, self._settings.presigned_upload_seconds
        )
        return PresignedUpload(
            media=media,
            upload_url=upload_url,
            expires_in=self._settings.presigned_upload_seconds,
            max_size_bytes=max_size,
        )

    async def complete_media(
        self,
        context: CurrentContext,
        visit_id: uuid.UUID,
        media_id: uuid.UUID,
    ) -> RawMedia:
        await self._require_mutable_visit(context.workspace.id, visit_id)
        media = await self._repository.get_media(
            context.workspace.id, visit_id, media_id
        )
        if media is None:
            raise ResourceNotFoundError
        stored_object = await self._storage.head_object(media.object_key)
        if stored_object is None:
            raise ResourceConflictError("media upload is not present in storage")
        _, max_size = self._media_rule(media.type, media.content_type)
        if stored_object.size_bytes <= 0 or stored_object.size_bytes > max_size:
            raise DomainValidationError(f"media exceeds the {max_size}-byte limit")
        if (
            stored_object.content_type is not None
            and stored_object.content_type.lower() != media.content_type
        ):
            raise DomainValidationError("uploaded content type does not match")
        media.status = "uploaded"
        media.size_bytes = stored_object.size_bytes
        await self._repository.flush()
        await self._repository.session.refresh(media)
        return media

    async def finish_showing(
        self, context: CurrentContext, visit_id: uuid.UUID
    ) -> Visit:
        should_enqueue = False
        visit = await self._require_mutable_visit(context.workspace.id, visit_id)
        if visit.ended_at is None:
            visit.ended_at = datetime.now(UTC)
        if (
            visit.processing_status != "queued"
            and await self._repository.has_completed_audio(
                context.workspace.id, visit_id
            )
        ):
            visit.processing_status = "queued"
            visit.processing_run_id = uuid.uuid4()
            visit.processing_failed_step = None
            visit.processing_error = None
            should_enqueue = True
        await self._repository.flush()
        await self._repository.session.refresh(visit)
        if should_enqueue:
            await self._repository.session.commit()
            try:
                await self._pipeline.enqueue(visit.id, context.workspace.id)
            except Exception as exc:
                visit.processing_status = "failed"
                visit.processing_failed_step = PipelineStep.TRANSCRIBE
                visit.processing_error = f"{type(exc).__name__}: {exc}"[:4000]
                await self._repository.flush()
                await self._repository.session.commit()
                raise PipelineUnavailableError from exc
        return visit

    async def reprocess_showing(
        self, context: CurrentContext, visit_id: uuid.UUID
    ) -> Visit:
        visit = await self._require_mutable_visit(context.workspace.id, visit_id)
        if visit.processing_status in {
            "queued",
            "transcribing",
            "structuring",
            "generating",
        }:
            return visit
        if visit.processing_status != "failed" or not visit.processing_failed_step:
            raise ResourceConflictError("showing does not have a failed pipeline run")

        failed_step = visit.processing_failed_step
        await self._pipeline_repository.delete_pending_reports(
            context.workspace.id, visit_id
        )
        if failed_step in {"transcribe", "zone_detection", "observation_extraction"}:
            await self._pipeline_repository.delete_ai_observations(
                context.workspace.id, visit_id
            )
        if failed_step in {"transcribe", "zone_detection"}:
            await self._pipeline_repository.delete_zones(context.workspace.id, visit_id)
        if failed_step == "transcribe":
            await self._pipeline_repository.delete_transcripts(
                context.workspace.id, visit_id
            )
        visit.processing_status = "queued"
        visit.processing_run_id = uuid.uuid4()
        visit.processing_failed_step = None
        visit.processing_error = None
        await self._repository.flush()
        await self._repository.session.refresh(visit)
        await self._repository.session.commit()
        try:
            await self._pipeline.enqueue(
                visit.id, context.workspace.id, PipelineStep(failed_step)
            )
        except Exception as exc:
            visit.processing_status = "failed"
            visit.processing_failed_step = failed_step
            visit.processing_error = f"{type(exc).__name__}: {exc}"[:4000]
            await self._repository.flush()
            await self._repository.session.commit()
            raise PipelineUnavailableError from exc
        return visit

    async def get_showing(
        self, context: CurrentContext, visit_id: uuid.UUID
    ) -> ShowingDetail:
        visit = await self._repository.get_visit(context.workspace.id, visit_id)
        if visit is None:
            raise ResourceNotFoundError
        subject = None
        if visit.subject_id is not None:
            subject = await self._properties.get(context.workspace.id, visit.subject_id)
            if subject is None:
                raise ResourceNotFoundError
        contact = await self._optional_contact(context.workspace.id, visit.contact_id)
        return ShowingDetail(
            record=ShowingRecord(visit=visit, subject=subject, contact=contact),
            media=await self._repository.detail_media(context.workspace.id, visit_id),
            zones=await self._repository.detail_zones(context.workspace.id, visit_id),
            observations=await self._repository.detail_observations(
                context.workspace.id, visit_id
            ),
            transcript=await self._repository.detail_transcript(
                context.workspace.id, visit_id
            ),
            report=await self._repository.detail_report(context.workspace.id, visit_id),
        )

    async def list_showings(
        self,
        context: CurrentContext,
        *,
        contact_id: uuid.UUID | None,
        subject_id: uuid.UUID | None,
        unassigned: bool | None,
        status: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        query: str | None,
        cursor: str | None,
        limit: int,
    ) -> ShowingPage:
        if date_from is not None and date_to is not None and date_from > date_to:
            raise DomainValidationError("date_from must be before date_to")
        cursor_created_at, cursor_id = self._decode_cursor(cursor)
        rows = await self._repository.list(
            context.workspace.id,
            contact_id=contact_id,
            subject_id=subject_id,
            unassigned=unassigned,
            status=status,
            date_from=date_from,
            date_to=date_to,
            query=query.strip() if query else None,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
            limit=limit + 1,
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [ShowingRecord(*row) for row in rows]
        next_cursor = None
        if has_more and items:
            last = items[-1].visit
            next_cursor = self._encode_cursor(last.created_at, last.id)
        return ShowingPage(items=items, next_cursor=next_cursor)

    async def get_media_download(
        self,
        context: CurrentContext,
        visit_id: uuid.UUID,
        media_id: uuid.UUID,
    ) -> PresignedDownload:
        media = await self._repository.get_media(
            context.workspace.id, visit_id, media_id
        )
        if media is None:
            raise ResourceNotFoundError
        if media.status != "uploaded":
            raise ResourceConflictError("media upload is not complete")
        return PresignedDownload(
            download_url=await self._storage.presign_get(
                media.object_key, self._settings.presigned_download_seconds
            ),
            expires_in=self._settings.presigned_download_seconds,
        )

    async def _optional_contact(
        self, workspace_id: uuid.UUID, contact_id: uuid.UUID | None
    ) -> Contact | None:
        if contact_id is None:
            return None
        contact = await self._contacts.get(workspace_id, contact_id)
        if contact is None:
            raise ResourceNotFoundError
        return contact

    async def _create_inline_subject(
        self, workspace_id: uuid.UUID, address: str
    ) -> Subject:
        vertical = await self._properties.get_real_estate_vertical()
        if vertical is None:
            raise VerticalNotSeededError
        normalized_address = address.strip()
        subject = Subject(
            workspace_id=workspace_id,
            vertical_id=vertical.id,
            subject_type="property",
            display_name=normalized_address,
            location=normalized_address,
            attributes={},
        )
        self._properties.add(subject)
        await self._repository.flush()
        return subject

    async def _require_mutable_visit(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> Visit:
        visit = await self._repository.get_visit(workspace_id, visit_id)
        if visit is None:
            raise ResourceNotFoundError
        if visit.status != "draft":
            raise ResourceConflictError("showing no longer accepts capture changes")
        return visit

    @staticmethod
    def _media_rule(media_type: str, content_type: str) -> tuple[str, int]:
        rule = MEDIA_RULES.get(media_type, {}).get(content_type)
        if rule is None:
            raise DomainValidationError(
                f"{content_type} is not allowed for {media_type} media"
            )
        return rule

    @staticmethod
    def _encode_cursor(created_at: datetime, visit_id: uuid.UUID) -> str:
        payload = json.dumps(
            {"created_at": created_at.isoformat(), "id": str(visit_id)},
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(
        cursor: str | None,
    ) -> tuple[datetime | None, uuid.UUID | None]:
        if cursor is None:
            return None, None
        try:
            padding = "=" * (-len(cursor) % 4)
            payload = json.loads(base64.urlsafe_b64decode(cursor + padding).decode())
            return datetime.fromisoformat(payload["created_at"]), uuid.UUID(
                payload["id"]
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DomainValidationError("invalid cursor") from exc
