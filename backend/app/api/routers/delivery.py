import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_context, get_delivery_service
from app.schemas.delivery import (
    DeliverySendResponse,
    DeliveryShareLinkResponse,
    DeliverySummaryResponse,
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


@router.get("/{visit_id}/delivery", response_model=DeliverySummaryResponse)
async def get_delivery(
    visit_id: uuid.UUID,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateDeliveryService, Depends(get_delivery_service)],
) -> DeliverySummaryResponse:
    result = await service.get_delivery(context, visit_id)
    return DeliverySummaryResponse(
        share_links=[
            DeliveryShareLinkResponse(
                token=item.link.token,
                url=item.url,
                created_at=item.link.created_at,
                expires_at=item.link.expires_at,
                revoked=item.link.revoked_at is not None,
                open_count=item.open_count,
            )
            for item in result.share_links
        ],
        sends=[
            DeliverySendResponse(
                channel=item.channel,
                to_email=item.to_email,
                sent_at=item.created_at,
            )
            for item in result.sends
        ],
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
