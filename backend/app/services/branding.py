import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import WorkspaceBranding
from app.repositories import ReviewRepository
from app.schemas.branding import BrandingUpdate
from app.services.context import CurrentContext
from app.storage import StorageProvider

LOGO_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


@dataclass(frozen=True)
class BrandingLogoUpload:
    logo_key: str
    upload_url: str
    expires_in: int


class RealEstateBrandingService:
    def __init__(
        self, session: AsyncSession, storage: StorageProvider, settings: Settings
    ) -> None:
        self._repository = ReviewRepository(session)
        self._storage = storage
        self._settings = settings

    async def get(self, context: CurrentContext) -> WorkspaceBranding | None:
        return await self._repository.get_branding(context.workspace.id)

    async def update(
        self, context: CurrentContext, payload: BrandingUpdate
    ) -> WorkspaceBranding:
        branding = await self._repository.get_branding(context.workspace.id)
        if branding is None:
            branding = WorkspaceBranding(workspace_id=context.workspace.id)
            self._repository.add(branding)
        for field, value in payload.model_dump().items():
            setattr(branding, field, str(value) if value is not None else None)
        await self._repository.flush()
        await self._repository.session.refresh(branding)
        return branding

    async def presign_logo(
        self, context: CurrentContext, content_type: str
    ) -> BrandingLogoUpload:
        extension = LOGO_TYPES[content_type]
        logo_key = f"{context.workspace.id}/branding/{uuid.uuid4()}.{extension}"
        branding = await self._repository.get_branding(context.workspace.id)
        if branding is None:
            branding = WorkspaceBranding(workspace_id=context.workspace.id)
            self._repository.add(branding)
        branding.logo_key = logo_key
        branding.logo_content_type = content_type
        await self._repository.flush()
        upload_url = await self._storage.presign_put(
            logo_key, content_type, self._settings.presigned_upload_seconds
        )
        return BrandingLogoUpload(
            logo_key=logo_key,
            upload_url=upload_url,
            expires_in=self._settings.presigned_upload_seconds,
        )
