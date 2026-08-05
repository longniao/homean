import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class BrandingUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    license_no: str | None = Field(default=None, max_length=100)
    accent_color: str = Field(
        default="#1F6F5B", pattern=r"^#[0-9A-Fa-f]{6}$"
    )


class BrandingResponse(BaseModel):
    id: uuid.UUID | None
    logo_key: str | None
    display_name: str | None
    phone: str | None
    email: EmailStr | None
    license_no: str | None
    accent_color: str
    updated_at: datetime | None


class BrandingLogoPresignRequest(BaseModel):
    content_type: Literal["image/jpeg", "image/png", "image/webp"]


class BrandingLogoPresignResponse(BaseModel):
    logo_key: str
    upload_url: str
    method: Literal["PUT"] = "PUT"
    headers: dict[str, str]
    expires_in: int
