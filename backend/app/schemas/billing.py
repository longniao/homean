import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, HttpUrl

BillingPlan = Literal["trial", "solo_monthly"]
BillingAction = Literal["subscribe", "manage_billing"]


class BillingStatusResponse(BaseModel):
    workspace_id: uuid.UUID
    plan: BillingPlan
    status: str
    active: bool
    billing_action: BillingAction
    can_checkout: bool
    can_portal: bool
    stripe_customer_attached: bool
    trial_ends_at: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool


class CheckoutRequest(BaseModel):
    plan: Literal["solo_monthly"] = "solo_monthly"


class CheckoutResponse(BaseModel):
    url: HttpUrl


class PortalResponse(BaseModel):
    url: HttpUrl
