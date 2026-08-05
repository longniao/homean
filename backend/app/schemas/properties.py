import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import Subject


class RealEstateSubjectAttributes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beds: int | None = Field(default=None, ge=0)
    baths: float | None = Field(default=None, ge=0)
    sqft: int | None = Field(default=None, ge=0)
    listing_price: float | None = Field(default=None, ge=0)
    mls_id: str | None = Field(default=None, min_length=1, max_length=100)


class PropertyCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=300)
    address: str = Field(min_length=1, max_length=1000)
    attributes: RealEstateSubjectAttributes = Field(
        default_factory=RealEstateSubjectAttributes
    )


class PropertyUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=300)
    address: str | None = Field(default=None, min_length=1, max_length=1000)
    attributes: RealEstateSubjectAttributes | None = None


class PropertyResponse(BaseModel):
    id: uuid.UUID
    display_name: str
    address: str
    attributes: RealEstateSubjectAttributes
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_subject(cls, subject: Subject) -> "PropertyResponse":
        return cls(
            id=subject.id,
            display_name=subject.display_name,
            address=subject.location or "",
            attributes=RealEstateSubjectAttributes.model_validate(subject.attributes),
            created_at=subject.created_at,
            updated_at=subject.updated_at,
        )
