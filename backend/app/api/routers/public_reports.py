from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import HTMLResponse, Response

from app.api.dependencies import get_delivery_service
from app.services import RealEstateDeliveryService

router = APIRouter(prefix="/r", tags=["public-reports"])


@router.get("/{token}", response_class=HTMLResponse)
async def get_public_report(
    token: str,
    service: Annotated[RealEstateDeliveryService, Depends(get_delivery_service)],
    user_agent: Annotated[str | None, Header()] = None,
) -> HTMLResponse:
    result = await service.get_public_report(token, user_agent, "html")
    return HTMLResponse(result.report.rendered_html or "")


@router.get("/{token}/pdf")
async def get_public_report_pdf(
    token: str,
    service: Annotated[RealEstateDeliveryService, Depends(get_delivery_service)],
    user_agent: Annotated[str | None, Header()] = None,
) -> Response:
    result = await service.get_public_report(token, user_agent, "pdf")
    pdf = await service._renderer.render_pdf(result.report.rendered_html or "")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="showing-report.pdf"'},
    )
