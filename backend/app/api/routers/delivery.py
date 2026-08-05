import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_context, get_delivery_service
from app.schemas.delivery import (
    SendReportRequest,
    SendReportResponse,
    ShareLinkCreate,
    ShareLinkResponse,
)
from app.services import CurrentContext, RealEstateDeliveryService
from app.services.delivery import ShareLinkResult

router = APIRouter(prefix="/showings", tags=["delivery"])


def _share_response(result: ShareLinkResult) -> ShareLinkResponse:
    return ShareLinkResponse(
        id=result.link.id,
        token=result.link.token,
        url=result.url,
        expires_at=result.link.expires_at,
        revoked_at=result.link.revoked_at,
    )


@router.post("/{visit_id}/share-links", response_model=ShareLinkResponse)
async def create_share_link(
    visit_id: uuid.UUID,
    payload: ShareLinkCreate,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateDeliveryService, Depends(get_delivery_service)],
) -> ShareLinkResponse:
    return _share_response(
        await service.create_share_link(context, visit_id, payload.expires_at)
    )


@router.post(
    "/{visit_id}/share-links/{link_id}/revoke", response_model=ShareLinkResponse
)
async def revoke_share_link(
    visit_id: uuid.UUID,
    link_id: uuid.UUID,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateDeliveryService, Depends(get_delivery_service)],
) -> ShareLinkResponse:
    return _share_response(await service.revoke_share_link(context, visit_id, link_id))


@router.post("/{visit_id}/send", response_model=SendReportResponse)
async def send_report(
    visit_id: uuid.UUID,
    payload: SendReportRequest,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateDeliveryService, Depends(get_delivery_service)],
) -> SendReportResponse:
    result = await service.send_report(
        context,
        visit_id,
        payload.channel,
        str(payload.to_email) if payload.to_email else None,
    )
    return SendReportResponse(
        send_id=result.send.id,
        visit_status=result.visit.status,
        channel=result.send.channel,
        share_url=result.share_url,
        to_email=result.send.to_email,
    )
