import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, model_validator


class ShareLinkCreate(BaseModel):
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_expiry(self) -> "ShareLinkCreate":
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ValueError("expires_at must include a timezone")
            if self.expires_at <= datetime.now(UTC):
                raise ValueError("expires_at must be in the future")
        return self


class ShareLinkResponse(BaseModel):
    id: uuid.UUID
    token: str
    url: str
    expires_at: datetime | None
    revoked_at: datetime | None


class SendReportRequest(BaseModel):
    channel: Literal["email", "link_only"]
    to_email: EmailStr | None = None

    @model_validator(mode="after")
    def require_email_recipient(self) -> "SendReportRequest":
        if self.channel == "email" and self.to_email is None:
            raise ValueError("to_email is required for email delivery")
        return self


class SendReportResponse(BaseModel):
    send_id: uuid.UUID
    visit_status: str
    channel: str
    share_url: str
    to_email: EmailStr | None
