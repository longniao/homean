from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.api.dependencies import get_branding_service, get_current_context
from app.models import WorkspaceBranding
from app.schemas.branding import (
    BrandingLogoPresignRequest,
    BrandingLogoPresignResponse,
    BrandingResponse,
    BrandingUpdate,
)
from app.services import CurrentContext, RealEstateBrandingService

router = APIRouter(prefix="/branding", tags=["branding"])


def _branding_response(branding: WorkspaceBranding | None) -> BrandingResponse:
    if branding is None:
        return BrandingResponse(
            id=None,
            logo_key=None,
            display_name=None,
            phone=None,
            email=None,
            license_no=None,
            accent_color="#1F6F5B",
            updated_at=None,
        )
    return BrandingResponse.model_validate(branding, from_attributes=True)


@router.get("", response_model=BrandingResponse)
async def get_branding(
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateBrandingService, Depends(get_branding_service)],
) -> BrandingResponse:
    return _branding_response(await service.get(context))


@router.get("/preview", response_class=HTMLResponse)
async def get_branding_preview(
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateBrandingService, Depends(get_branding_service)],
) -> HTMLResponse:
    return HTMLResponse(await service.render_preview(context))


@router.put("", response_model=BrandingResponse)
async def update_branding(
    payload: BrandingUpdate,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateBrandingService, Depends(get_branding_service)],
) -> BrandingResponse:
    return _branding_response(await service.update(context, payload))


@router.post("/logo/presign", response_model=BrandingLogoPresignResponse)
async def presign_branding_logo(
    payload: BrandingLogoPresignRequest,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateBrandingService, Depends(get_branding_service)],
) -> BrandingLogoPresignResponse:
    upload = await service.presign_logo(context, payload.content_type)
    return BrandingLogoPresignResponse(
        logo_key=upload.logo_key,
        upload_url=upload.upload_url,
        headers={"Content-Type": payload.content_type},
        expires_in=upload.expires_in,
    )
