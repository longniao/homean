import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ZoneRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_type: str
    start_segment_id: uuid.UUID
    end_segment_id: uuid.UUID


class ZoneDetectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zones: list[ZoneRange] = Field(default_factory=list)


class SensitiveContentFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sensitive: bool = False
    reason: str | None = None
    suggested_rewrite: str | None = None

    @model_validator(mode="after")
    def validate_sensitive_details(self) -> "SensitiveContentFlags":
        if self.sensitive and (not self.reason or not self.suggested_rewrite):
            raise ValueError(
                "sensitive observations require a reason and suggested rewrite"
            )
        if not self.sensitive:
            self.reason = None
            self.suggested_rewrite = None
        return self


class ExtractedObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_id: uuid.UUID | None = None
    category: str
    content: str = Field(min_length=1)
    source_transcript_segment_id: uuid.UUID
    start_ms: float = Field(ge=0)
    end_ms: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    flags: SensitiveContentFlags = Field(default_factory=SensitiveContentFlags)

    @model_validator(mode="after")
    def validate_timestamps(self) -> "ExtractedObservation":
        if self.start_ms > self.end_ms:
            raise ValueError("start_ms must not be after end_ms")
        return self


class ObservationExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[ExtractedObservation] = Field(default_factory=list)


class ReportBullet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    observation_ids: list[uuid.UUID] = Field(min_length=1)


class RoomByRoomSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_id: uuid.UUID | None
    zone_type: str | None
    bullets: list[ReportBullet] = Field(default_factory=list)


class RealEstateReportSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: str
    room_by_room: list[RoomByRoomSection] = Field(default_factory=list)
    highlights: list[ReportBullet] = Field(default_factory=list)
    concerns: list[ReportBullet] = Field(default_factory=list)
    follow_ups: list[ReportBullet] = Field(default_factory=list)
