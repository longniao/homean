import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
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
    VisitMarker,
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
from app.schemas.showings import (
    MarkerCreate,
    MediaPresignRequest,
    ShowingCreate,
    ShowingUpdate,
)
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
    expires_at: datetime
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

        # A mobile showing carries its durable local UUID as a per-workspace
        # capture key.  The first request may have committed remotely while
        # its response was lost, so retries must return the original visit
        # instead of creating a second visit (or inline subject).
        if payload.capture_client_id is not None:
            workspace_id = context.workspace.id
            existing = await self._repository.get_visit_by_capture_client_id(
                workspace_id, payload.capture_client_id
            )
            if existing is not None:
                if not await self._capture_payload_matches(
                    workspace_id, existing, payload
                ):
                    raise ResourceConflictError(
                        "capture_client_id is already used with different showing data"
                    )
                subject = None
                if existing.subject_id is not None:
                    subject = await self._properties.get(
                        workspace_id, existing.subject_id
                    )
                    if subject is None:
                        raise ResourceNotFoundError
                contact = await self._optional_contact(
                    workspace_id, existing.contact_id
                )
                return ShowingRecord(visit=existing, subject=subject, contact=contact)

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
            started_at=self._capture_start(payload.started_at),
            capture_timezone=payload.capture_timezone,
            status="draft",
            processing_status="not_started",
            consent_ack=payload.consent_ack,
            capture_client_id=payload.capture_client_id,
        )
        self._repository.add(visit)
        try:
            await self._repository.flush()
        except IntegrityError:
            # A concurrent request can pass the preflight lookup and win the
            # unique workspace/capture key first.  Roll back this failed
            # insert, then use the same idempotent path to validate and return
            # the committed visit instead of leaking a 500 or duplicate row.
            if payload.capture_client_id is None:
                raise
            workspace_id = context.workspace.id
            await self._repository.session.rollback()
            existing = await self._repository.get_visit_by_capture_client_id(
                workspace_id, payload.capture_client_id
            )
            if existing is None:
                raise
            if not await self._capture_payload_matches(workspace_id, existing, payload):
                raise ResourceConflictError(
                    "capture_client_id is already used with different showing data"
                ) from None
            subject = None
            if existing.subject_id is not None:
                subject = await self._properties.get(workspace_id, existing.subject_id)
                if subject is None:
                    raise ResourceNotFoundError from None
            contact = await self._optional_contact(workspace_id, existing.contact_id)
            return ShowingRecord(visit=existing, subject=subject, contact=contact)
        return ShowingRecord(visit=visit, subject=subject, contact=contact)

    @staticmethod
    def _capture_start(reported: datetime | None) -> datetime:
        """Trust the capture device's clock, but never accept a future tour.

        A queued offline showing must sync no matter what the device clock
        says, so a skewed future timestamp is clamped rather than rejected —
        stranding a real recording would be far worse than a wrong date.
        """

        now = datetime.now(UTC)
        if reported is None:
            return now
        return min(reported, now)

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
        workspace_id = context.workspace.id
        content_type = payload.content_type.strip().lower()
        extension, max_size = self._media_rule(payload.type, content_type)
        visit = await self._require_mutable_visit(workspace_id, visit_id)
        # These values must remain usable after a failed flush.  A session
        # rollback expires ORM state, including ``visit`` and any loaded media.
        visit_id = visit.id
        client_id = payload.client_id
        media_id = payload.media_id
        media_by_id = None
        if media_id is not None:
            media_by_id = await self._repository.get_media(
                workspace_id, visit_id, media_id
            )
            if media_by_id is None:
                raise ResourceNotFoundError

        media_by_client_id = None
        if client_id is not None:
            media_by_client_id = await self._repository.get_media_by_client_id(
                workspace_id, visit_id, client_id
            )

        if (
            media_by_id is not None
            and media_by_client_id is not None
            and media_by_id.id != media_by_client_id.id
        ):
            raise ResourceConflictError(
                "media_id and client_id identify different media rows"
            )
        media = media_by_id or media_by_client_id
        if media is None:
            media_id = uuid.uuid4()
            object_key = f"{workspace_id}/{visit_id}/{media_id}.{extension}"
            media = RawMedia(
                id=media_id,
                visit_id=visit_id,
                client_id=client_id,
                type=payload.type,
                object_key=object_key,
                content_type=content_type,
                timestamp_offset_ms=payload.timestamp_offset_ms,
                status="pending",
            )
            self._repository.add(media)
            try:
                await self._repository.flush()
            except IntegrityError:
                # A concurrent retry can pass the lookup above and commit the
                # same client identity first.  Reconcile to that row rather
                # than leaking an error or creating another storage object.
                if client_id is None:
                    raise
                await self._repository.session.rollback()
                media = await self._repository.get_media_by_client_id(
                    workspace_id, visit_id, client_id
                )
                if media is None:
                    raise ResourceConflictError(
                        "media client_id could not be reconciled"
                    ) from None

        if client_id is not None:
            if media.client_id is not None and media.client_id != client_id:
                raise ResourceConflictError(
                    "media_id is already used with a different client_id"
                )
            if media.client_id is None:
                # A legacy row has no client identity.  Lock and refresh it
                # before assigning one so concurrent assignments cannot
                # overwrite each other nondeterministically.
                legacy_media_id = media.id
                media = await self._repository.get_media_for_update(
                    workspace_id, visit_id, legacy_media_id
                )
                if media is None:
                    raise ResourceNotFoundError
                if media.client_id is not None:
                    if media.client_id != client_id:
                        raise ResourceConflictError(
                            "media_id is already used with a different client_id"
                        )
                else:
                    media.client_id = client_id
                    try:
                        await self._repository.flush()
                    except IntegrityError:
                        # Another request may have claimed this client_id in a
                        # different row while this legacy row was being
                        # reconciled.  Roll back first, then resolve both
                        # identities from fresh workspace-scoped queries.
                        await self._repository.session.rollback()
                        media = await self._repository.get_media(
                            workspace_id, visit_id, legacy_media_id
                        )
                        owner = await self._repository.get_media_by_client_id(
                            workspace_id, visit_id, client_id
                        )
                        if media is None:
                            raise ResourceNotFoundError from None
                        if owner is not None and owner.id != legacy_media_id:
                            raise ResourceConflictError(
                                "media_id and client_id identify different media rows"
                            ) from None
                        if media.client_id != client_id:
                            raise ResourceConflictError(
                                "media client_id could not be reconciled"
                            ) from None

        self._validate_media_identity(
            media,
            media_type=payload.type,
            content_type=content_type,
            timestamp_offset_ms=payload.timestamp_offset_ms,
        )
        if media.status == "uploaded":
            raise ResourceConflictError("media upload is already complete")
        # The durable object key is intentionally reused.  A refresh must
        # never create an orphan RawMedia row or a second object.

        expires_in = self._settings.presigned_upload_seconds
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
        upload_url = await self._storage.presign_put(
            media.object_key, media.content_type, expires_in
        )
        media.upload_url_expires_at = expires_at
        await self._repository.flush()
        await self._repository.session.refresh(media)
        return PresignedUpload(
            media=media,
            upload_url=upload_url,
            expires_in=expires_in,
            expires_at=expires_at,
            max_size_bytes=max_size,
        )

    @staticmethod
    def _validate_media_identity(
        media: RawMedia,
        *,
        media_type: str,
        content_type: str,
        timestamp_offset_ms: float | None,
    ) -> None:
        if (
            media.type != media_type
            or media.content_type != content_type
            or (
                timestamp_offset_ms is not None
                and media.timestamp_offset_ms != timestamp_offset_ms
            )
        ):
            raise ResourceConflictError(
                "media identity is already used with different capture data"
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

    async def create_marker(
        self,
        context: CurrentContext,
        visit_id: uuid.UUID,
        payload: MarkerCreate,
    ) -> VisitMarker:
        visit = await self._require_mutable_visit(context.workspace.id, visit_id)
        marker = VisitMarker(
            visit_id=visit.id,
            client_id=payload.client_id,
            created_by=context.user.id,
            marker_type=payload.marker_type,
            timestamp_offset_ms=payload.timestamp_offset_ms,
        )
        existing = await self._repository.get_marker(visit.id, payload.client_id)
        if existing is not None:
            if (
                existing.marker_type != payload.marker_type
                or existing.timestamp_offset_ms != payload.timestamp_offset_ms
            ):
                raise ResourceConflictError(
                    "marker client_id is already used with different capture data"
                )
            return existing
        marker = await self._repository.insert_marker(marker)
        if (
            marker.marker_type != payload.marker_type
            or marker.timestamp_offset_ms != payload.timestamp_offset_ms
        ):
            raise ResourceConflictError(
                "marker client_id is already used with different capture data"
            )
        return marker

    async def list_markers(
        self, context: CurrentContext, visit_id: uuid.UUID
    ) -> list[VisitMarker]:
        visit = await self._repository.get_visit(context.workspace.id, visit_id)
        if visit is None:
            raise ResourceNotFoundError
        return await self._repository.list_markers(context.workspace.id, visit_id)

    async def finish_showing(
        self, context: CurrentContext, visit_id: uuid.UUID
    ) -> Visit:
        should_enqueue = False
        visit = await self._require_mutable_visit(context.workspace.id, visit_id)
        if not await self._repository.has_completed_audio(
            context.workspace.id, visit_id
        ):
            raise ResourceConflictError("missing_audio")
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

    async def _capture_payload_matches(
        self,
        workspace_id: uuid.UUID,
        visit: Visit,
        payload: ShowingCreate,
    ) -> bool:
        if visit.contact_id != payload.contact_id:
            return False
        if visit.consent_ack != payload.consent_ack:
            return False
        if payload.subject_id is not None:
            return visit.subject_id == payload.subject_id
        if payload.address is not None:
            if visit.subject_id is None:
                return False
            subject = await self._properties.get(workspace_id, visit.subject_id)
            return subject is not None and subject.location == payload.address.strip()
        # A dashboard user may attach a subject after the mobile create
        # response was lost.  The original subjectless payload remains
        # compatible with that visit; a supplied subject/address is checked
        # above as an immutable capture field.
        return True

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
            encoded_payload = (cursor + padding).encode("ascii")
            payload = json.loads(
                base64.b64decode(encoded_payload, altchars=b"-_", validate=True).decode(
                    "utf-8"
                )
            )
        except (
            binascii.Error,
            UnicodeDecodeError,
            UnicodeEncodeError,
            json.JSONDecodeError,
        ) as exc:
            raise DomainValidationError("invalid cursor") from exc

        if not isinstance(payload, dict):
            raise DomainValidationError("invalid cursor")
        try:
            created_at = payload["created_at"]
            visit_id = payload["id"]
            if not isinstance(created_at, str) or not isinstance(visit_id, str):
                raise TypeError("cursor fields must be strings")
            return datetime.fromisoformat(created_at), uuid.UUID(visit_id)
        except (KeyError, TypeError, ValueError) as exc:
            raise DomainValidationError("invalid cursor") from exc
