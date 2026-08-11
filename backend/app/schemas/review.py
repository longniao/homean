import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.pipeline.schemas import RealEstateReportSchema


class ObservationUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    zone_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ObservationUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one observation field is required")
        return self


class ObservationCreate(BaseModel):
    visit_id: uuid.UUID
    content: str = Field(min_length=1, max_length=10000)
    category: str = Field(min_length=1, max_length=100)
    zone_id: uuid.UUID | None = None
    source_transcript_segment_id: uuid.UUID | None = None


class TranscriptSegmentUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=50000)


class ReportUpdate(BaseModel):
    content: RealEstateReportSchema


class ReportRevisionResponse(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    visit_id: uuid.UUID
    edited_by: uuid.UUID
    revision_number: int
    previous_content: dict[str, object]
    new_content: dict[str, object]
    created_at: datetime


class ShowingConfirmationResponse(BaseModel):
    visit_id: uuid.UUID
    report_id: uuid.UUID
    visit_status: str
    report_status: str
