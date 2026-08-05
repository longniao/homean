import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from app.services.me import MeResult


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str | None
    phone: str | None


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    language: str


class ProfessionalProfileResponse(BaseModel):
    id: uuid.UUID
    role: str
    vertical: str


class MeResponse(BaseModel):
    user: UserResponse
    workspace: WorkspaceResponse
    profile: ProfessionalProfileResponse

    @classmethod
    def from_result(cls, result: MeResult) -> "MeResponse":
        return cls(
            user=UserResponse.model_validate(result.context.user),
            workspace=WorkspaceResponse.model_validate(result.context.workspace),
            profile=ProfessionalProfileResponse(
                id=result.profile.id,
                role=result.profile.role,
                vertical=result.vertical.slug,
            ),
        )
