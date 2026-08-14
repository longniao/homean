import uuid
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import (
    Observation,
    RawMedia,
    Report,
    TranscriptSegment,
    Visit,
    VisitMarker,
    Zone,
)
from app.schemas.contacts import ContactResponse
from app.schemas.properties import PropertyResponse

ShowingStatus = Literal["draft", "confirmed", "sent_to_client"]
MediaType = Literal["audio", "photo", "video"]
MarkerType = Literal["voice_tag"]


class ShowingCreate(BaseModel):
    subject_id: uuid.UUID | None = None
    address: str | None = Field(default=None, min_length=1, max_length=1000)
    contact_id: uuid.UUID | None = None
    consent_ack: bool = False
    # The version of the consent wording the client actually displayed. Absent
    # when a client attested from bundled text it could not verify against the
    # server, which is recorded as unknown rather than assumed current.
    consent_text_version: str | None = Field(default=None, min_length=1, max_length=64)
    capture_client_id: uuid.UUID | None = None
    # Offline captures reach the server long after the tour, so the client
    # reports when it actually happened and in which zone.  Both are optional;
    # a visit created without them falls back to server time in UTC.
    started_at: datetime | None = None
    capture_timezone: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_subject_source(self) -> "ShowingCreate":
        if self.subject_id is not None and self.address is not None:
            raise ValueError("provide at most one of subject_id or address")
        return self

    @field_validator("started_at")
    @classmethod
    def require_aware_start(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("started_at must include a UTC offset")
        return value

    @field_validator("capture_timezone")
    @classmethod
    def require_known_zone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("capture_timezone must be an IANA time zone") from exc
        return value


class ShowingUpdate(BaseModel):
    subject_id: uuid.UUID | None = None
    address: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_subject_source(self) -> "ShowingUpdate":
        if (self.subject_id is None) == (self.address is None):
            raise ValueError("provide exactly one of subject_id or address")
        return self


class MediaPresignRequest(BaseModel):
    # ``client_id`` is the durable local media UUID.  It is required by mobile
    # retries, but remains optional for older/dashboard capture callers.
    client_id: uuid.UUID | None = None
    # Supplying an existing media id refreshes the URL for that exact row and
    # object.  Omitting it creates or reconciles the initial presign by client_id.
    media_id: uuid.UUID | None = None
    type: MediaType
    content_type: str = Field(min_length=1, max_length=200)
    timestamp_offset_ms: float | None = Field(default=None, ge=0)


class MediaPresignResponse(BaseModel):
    media_id: uuid.UUID
    upload_url: str
    method: Literal["PUT"] = "PUT"
    headers: dict[str, str]
    expires_in: int
    expires_at: datetime
    max_size_bytes: int


class MediaResponse(BaseModel):
    id: uuid.UUID
    type: str
    content_type: str
    timestamp_offset_ms: float | None
    status: str
    size_bytes: int | None
    created_at: datetime

    @classmethod
    def from_media(cls, media: RawMedia) -> "MediaResponse":
        return cls.model_validate(media, from_attributes=True)


class MediaDownloadResponse(BaseModel):
    download_url: str
    expires_in: int


class MarkerCreate(BaseModel):
    client_id: uuid.UUID
    marker_type: MarkerType = "voice_tag"
    timestamp_offset_ms: float = Field(ge=0, allow_inf_nan=False)


class MarkerResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    marker_type: MarkerType
    timestamp_offset_ms: float
    created_at: datetime

    @classmethod
    def from_marker(cls, marker: VisitMarker) -> "MarkerResponse":
        return cls.model_validate(marker, from_attributes=True)


class ZoneResponse(BaseModel):
    id: uuid.UUID
    zone_type: str
    position: int
    start_transcript_segment_id: uuid.UUID | None
    end_transcript_segment_id: uuid.UUID | None

    @classmethod
    def from_zone(cls, zone: Zone) -> "ZoneResponse":
        return cls.model_validate(zone, from_attributes=True)


class ObservationResponse(BaseModel):
    id: uuid.UUID
    zone_id: uuid.UUID | None
    category: str
    content: str
    source_type: str
    source_transcript_segment_id: uuid.UUID | None
    source_media_id: uuid.UUID | None
    timestamp_start: float | None
    timestamp_end: float | None
    ai_model: str | None
    prompt_version: str | None
    confidence: float | None
    flags: dict[str, object]
    review_status: str
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None

    @classmethod
    def from_observation(cls, observation: Observation) -> "ObservationResponse":
        return cls.model_validate(observation, from_attributes=True)


class TranscriptSegmentResponse(BaseModel):
    id: uuid.UUID
    raw_media_id: uuid.UUID
    text: str
    original_text: str | None
    timestamp_start: float | None
    timestamp_end: float | None
    confidence: float | None

    @classmethod
    def from_segment(cls, segment: TranscriptSegment) -> "TranscriptSegmentResponse":
        return cls.model_validate(segment, from_attributes=True)


class ReportResponse(BaseModel):
    id: uuid.UUID
    template_id: str
    content: dict[str, object]
    rendered_html: str | None
    status: str

    @classmethod
    def from_report(cls, report: Report) -> "ReportResponse":
        return cls.model_validate(report, from_attributes=True)


class ShowingResponse(BaseModel):
    id: uuid.UUID
    status: ShowingStatus
    processing_status: str
    processing_failed_step: str | None
    processing_error: str | None
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime
    consent_ack: bool
    property: PropertyResponse | None
    contact: ContactResponse | None


class ShowingDetailResponse(ShowingResponse):
    media: list[MediaResponse]
    zones: list[ZoneResponse]
    observations: list[ObservationResponse]
    transcript: list[TranscriptSegmentResponse]
    report: ReportResponse | None


class ShowingFinishResponse(BaseModel):
    id: uuid.UUID
    status: ShowingStatus
    processing_status: str
    processing_failed_step: str | None
    processing_error: str | None
    ended_at: datetime

    @classmethod
    def from_visit(cls, visit: Visit) -> "ShowingFinishResponse":
        return cls.model_validate(visit, from_attributes=True)


class ShowingListResponse(BaseModel):
    items: list[ShowingResponse]
    next_cursor: str | None
