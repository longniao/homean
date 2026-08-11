from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status

from app.api.dependencies import get_billing_service, get_current_context
from app.models import WorkspaceSubscription
from app.schemas.billing import (
    BillingStatusResponse,
    CheckoutRequest,
    CheckoutResponse,
    PortalResponse,
)
from app.services import BillingService, CurrentContext

router = APIRouter(prefix="/billing", tags=["billing"])


def _status_response(
    context: CurrentContext, subscription: WorkspaceSubscription
) -> BillingStatusResponse:
    return BillingStatusResponse(
        workspace_id=context.workspace.id,
        plan=subscription.plan,
        status=subscription.status,
        active=BillingService.is_active(subscription),
        **BillingService.capabilities(subscription),
        trial_ends_at=subscription.trial_ends_at,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
    )


@router.get("", response_model=BillingStatusResponse)
async def get_billing_status(
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[BillingService, Depends(get_billing_service)],
) -> BillingStatusResponse:
    return _status_response(context, await service.get_status(context))


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    payload: CheckoutRequest,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[BillingService, Depends(get_billing_service)],
) -> CheckoutResponse:
    del payload
    return CheckoutResponse(url=await service.create_checkout(context))


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[BillingService, Depends(get_billing_service)],
) -> PortalResponse:
    return PortalResponse(url=await service.create_portal(context))


@router.post("/webhook", status_code=status.HTTP_204_NO_CONTENT)
async def stripe_webhook(
    request: Request,
    service: Annotated[BillingService, Depends(get_billing_service)],
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> None:
    await service.process_webhook(await request.body(), stripe_signature)
