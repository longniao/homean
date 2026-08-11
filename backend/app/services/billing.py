import hashlib
import hmac
import json
import time
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import WorkspaceSubscription
from app.repositories.billing import BillingRepository
from app.services.context import CurrentContext
from app.services.exceptions import (
    BillingAlreadySubscribedError,
    BillingUnavailableError,
    InvalidBillingEventError,
    SubscriptionRequiredError,
)


class BillingProvider(ABC):
    @abstractmethod
    async def create_checkout_session(
        self,
        *,
        workspace_id: uuid.UUID,
        customer_email: str,
        customer_id: str | None,
        price_id: str,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> str:
        """Create a Stripe Checkout session and return its URL."""

    @abstractmethod
    async def create_portal_session(self, *, customer_id: str, return_url: str) -> str:
        """Create a Stripe customer portal session and return its URL."""

    @abstractmethod
    def verify_webhook(
        self, payload: bytes, signature: str | None
    ) -> dict[str, object]:
        """Verify and decode a Stripe webhook payload."""

    async def get_subscription(self, subscription_id: str) -> dict[str, object] | None:
        """Return authoritative subscription state when the provider supports it."""
        del subscription_id
        return None


class StripeBillingProvider(BillingProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def _post(
        self,
        path: str,
        data: dict[str, str],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, object]:
        secret = self._settings.stripe_secret_key
        if secret is None:
            raise BillingUnavailableError("Stripe billing is not configured")
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{self._settings.stripe_api_base_url.rstrip('/')}/{path.lstrip('/')}",
                data=data,
                headers=headers,
                auth=(secret.get_secret_value(), ""),
            )
        if response.status_code >= 400:
            raise BillingUnavailableError("Stripe billing request failed")
        payload = response.json()
        if not isinstance(payload, dict):
            raise BillingUnavailableError("Stripe returned an invalid response")
        return payload

    async def _get(self, path: str) -> dict[str, object] | None:
        secret = self._settings.stripe_secret_key
        if secret is None:
            raise BillingUnavailableError("Stripe billing is not configured")
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{self._settings.stripe_api_base_url.rstrip('/')}/{path.lstrip('/')}",
                auth=(secret.get_secret_value(), ""),
            )
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise BillingUnavailableError("Stripe billing request failed")
        payload = response.json()
        if not isinstance(payload, dict):
            raise BillingUnavailableError("Stripe returned an invalid response")
        return payload

    async def create_checkout_session(
        self,
        *,
        workspace_id: uuid.UUID,
        customer_email: str,
        customer_id: str | None,
        price_id: str,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> str:
        customer_fields = (
            {"customer": customer_id}
            if customer_id
            else {"customer_email": customer_email}
        )
        payload = await self._post(
            "checkout/sessions",
            {
                "mode": "subscription",
                "line_items[0][price]": price_id,
                "line_items[0][quantity]": "1",
                **customer_fields,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata[workspace_id]": str(workspace_id),
                "subscription_data[metadata][workspace_id]": str(workspace_id),
            },
            idempotency_key=idempotency_key,
        )
        url = payload.get("url")
        if not isinstance(url, str):
            raise BillingUnavailableError("Stripe did not return a checkout URL")
        return url

    async def create_portal_session(self, *, customer_id: str, return_url: str) -> str:
        payload = await self._post(
            "billing_portal/sessions",
            {"customer": customer_id, "return_url": return_url},
        )
        url = payload.get("url")
        if not isinstance(url, str):
            raise BillingUnavailableError("Stripe did not return a portal URL")
        return url

    async def get_subscription(self, subscription_id: str) -> dict[str, object] | None:
        return await self._get(f"subscriptions/{subscription_id}")

    def verify_webhook(
        self, payload: bytes, signature: str | None
    ) -> dict[str, object]:
        secret = self._settings.stripe_webhook_secret
        if secret is None or not signature:
            raise InvalidBillingEventError("missing Stripe webhook signature")
        timestamp: str | None = None
        signatures: list[str] = []
        for item in signature.split(","):
            key, separator, value = item.strip().partition("=")
            if not separator:
                continue
            if key == "t":
                timestamp = value
            elif key == "v1":
                signatures.append(value)
        if (
            not timestamp
            or not timestamp.isascii()
            or not timestamp.isdigit()
            or not signatures
            or any(not value.isascii() for value in signatures)
        ):
            raise InvalidBillingEventError("invalid Stripe webhook signature")
        try:
            timestamp_value = int(timestamp)
        except ValueError as exc:
            raise InvalidBillingEventError("invalid Stripe webhook signature") from exc
        if abs(time.time() - timestamp_value) > 300:
            raise InvalidBillingEventError("invalid Stripe webhook signature")
        signed = timestamp.encode("ascii") + b"." + payload
        expected = hmac.new(
            secret.get_secret_value().encode("utf-8"), signed, hashlib.sha256
        ).hexdigest()
        if not any(hmac.compare_digest(expected, received) for received in signatures):
            raise InvalidBillingEventError("invalid Stripe webhook signature")
        try:
            decoded = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidBillingEventError("invalid Stripe webhook payload") from exc
        if not isinstance(decoded, dict):
            raise InvalidBillingEventError("invalid Stripe webhook payload")
        return decoded


class FakeBillingProvider(BillingProvider):
    """Deterministic provider for route/service tests; never calls Stripe."""

    def __init__(self) -> None:
        self.checkout_urls: list[str] = []
        self.checkout_requests: list[dict[str, object]] = []
        self.portal_urls: list[str] = []
        self.events: list[dict[str, object]] = []
        self.subscription_details: dict[str, dict[str, object]] = {}

    async def create_checkout_session(self, **kwargs: object) -> str:
        self.checkout_requests.append(kwargs)
        url = f"https://checkout.test/session/{kwargs['workspace_id']}"
        self.checkout_urls.append(url)
        return url

    async def create_portal_session(self, **kwargs: object) -> str:
        url = f"https://billing.test/portal/{kwargs['customer_id']}"
        self.portal_urls.append(url)
        return url

    async def get_subscription(self, subscription_id: str) -> dict[str, object] | None:
        return self.subscription_details.get(subscription_id)

    def verify_webhook(
        self, payload: bytes, signature: str | None
    ) -> dict[str, object]:
        del signature
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidBillingEventError("invalid billing event") from exc
        if not isinstance(value, dict):
            raise InvalidBillingEventError("invalid billing event")
        self.events.append(value)
        return value


class BillingService:
    _TERMINAL_STRIPE_STATUSES = {"canceled", "incomplete_expired"}

    def __init__(
        self, session: AsyncSession, settings: Settings, provider: BillingProvider
    ) -> None:
        self._repository = BillingRepository(session)
        self._settings = settings
        self._provider = provider

    async def ensure_trial(self, workspace_id: uuid.UUID) -> WorkspaceSubscription:
        subscription = await self._repository.get_subscription(workspace_id)
        if subscription is not None:
            return subscription
        subscription = WorkspaceSubscription(
            workspace_id=workspace_id,
            plan="trial",
            status="trialing",
            trial_ends_at=datetime.now(UTC) + timedelta(days=14),
        )
        self._repository.add(subscription)
        await self._repository.flush()
        return subscription

    async def get_status(self, context: CurrentContext) -> WorkspaceSubscription:
        return await self.ensure_trial(context.workspace.id)

    @staticmethod
    def is_active(
        subscription: WorkspaceSubscription, now: datetime | None = None
    ) -> bool:
        current = now or datetime.now(UTC)
        if subscription.status == "trialing":
            return (
                subscription.trial_ends_at is not None
                and subscription.trial_ends_at > current
            )
        if subscription.status in {"active", "past_due"}:
            return (
                subscription.current_period_end is None
                or subscription.current_period_end > current
            )
        return False

    @classmethod
    def has_non_terminal_subscription(cls, subscription: WorkspaceSubscription) -> bool:
        """Whether Stripe still owns an existing, non-terminal subscription.

        This is deliberately separate from ``is_active``: a subscription can
        be outside its current entitlement period while Stripe still has an
        attached lifecycle that must be managed instead of duplicated.
        """

        return (
            subscription.plan == "solo_monthly"
            and bool(subscription.stripe_subscription_id)
            and subscription.status not in cls._TERMINAL_STRIPE_STATUSES
        )

    @staticmethod
    def _checkout_idempotency_key(
        workspace_id: uuid.UUID,
        price_id: str,
        subscription: WorkspaceSubscription,
    ) -> str:
        lifecycle_state = "|".join(
            (
                str(subscription.stripe_subscription_id or ""),
                str(subscription.stripe_event_id or ""),
                str(subscription.stripe_event_type or ""),
                (
                    subscription.stripe_event_created_at.isoformat()
                    if subscription.stripe_event_created_at is not None
                    else ""
                ),
                subscription.status,
            )
        )
        digest = hashlib.sha256(
            f"{workspace_id}|{price_id}|{lifecycle_state}".encode()
        ).hexdigest()[:32]
        return f"kawu-checkout-{digest}"

    @classmethod
    def capabilities(cls, subscription: WorkspaceSubscription) -> dict[str, object]:
        has_subscription = cls.has_non_terminal_subscription(subscription)
        paid_customer = subscription.plan == "solo_monthly" and bool(
            subscription.stripe_customer_id
        )
        action = "manage_billing" if has_subscription else "subscribe"
        return {
            "billing_action": action,
            "can_checkout": not has_subscription,
            "can_portal": has_subscription or paid_customer,
            "stripe_customer_attached": bool(subscription.stripe_customer_id),
        }

    async def require_active(self, context: CurrentContext) -> None:
        subscription = await self.get_status(context)
        if not self.is_active(subscription):
            raise SubscriptionRequiredError

    async def create_checkout(self, context: CurrentContext) -> str:
        subscription = await self.get_status(context)
        if self.has_non_terminal_subscription(subscription):
            raise BillingAlreadySubscribedError
        price_id = self._settings.stripe_solo_monthly_price_id
        if not price_id:
            raise BillingUnavailableError("Solo monthly billing is not configured")
        return await self._provider.create_checkout_session(
            workspace_id=context.workspace.id,
            customer_email=context.user.email,
            customer_id=subscription.stripe_customer_id,
            price_id=price_id,
            success_url=f"{self._settings.dashboard_origin}/settings?billing=success",
            cancel_url=f"{self._settings.dashboard_origin}/settings?billing=cancelled",
            idempotency_key=self._checkout_idempotency_key(
                context.workspace.id, price_id, subscription
            ),
        )

    async def create_portal(self, context: CurrentContext) -> str:
        subscription = await self.get_status(context)
        if not self.capabilities(subscription)["can_portal"]:
            raise BillingUnavailableError(
                "No Stripe customer is attached to this workspace"
            )
        return await self._provider.create_portal_session(
            customer_id=subscription.stripe_customer_id or "",
            return_url=f"{self._settings.dashboard_origin}/settings",
        )

    async def process_webhook(self, payload: bytes, signature: str | None) -> None:
        event = self._provider.verify_webhook(payload, signature)
        event_id = event.get("id")
        event_type = event.get("type")
        created = event.get("created")
        data = event.get("data")
        if (
            not isinstance(event_id, str)
            or not event_id
            or not isinstance(event_type, str)
            or not isinstance(created, (int, float))
            or isinstance(created, bool)
            or not isinstance(data, dict)
        ):
            raise InvalidBillingEventError("malformed Stripe webhook event")
        obj = data.get("object")
        if not isinstance(obj, dict):
            raise InvalidBillingEventError("malformed Stripe webhook object")
        try:
            event_created_at = datetime.fromtimestamp(created, UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise InvalidBillingEventError("malformed Stripe event timestamp") from exc
        if not await self._repository.record_webhook_event(
            event_id=event_id,
            event_type=event_type,
            stripe_created_at=event_created_at,
        ):
            return
        if event_type == "checkout.session.completed":
            await self._process_checkout_completed(event_id, event_created_at, obj)
        elif event_type in {
            "customer.subscription.updated",
            "customer.subscription.deleted",
        }:
            await self._process_subscription_event(
                event_id, event_created_at, event_type, obj
            )

    async def _process_checkout_completed(
        self,
        event_id: str,
        event_created_at: datetime,
        checkout: dict[str, object],
    ) -> None:
        metadata = self._metadata(checkout.get("metadata"))
        workspace_id = self._workspace_id(metadata, required=False)
        if checkout.get("mode") != "subscription":
            raise InvalidBillingEventError("Checkout session is not a subscription")
        subscription_id = checkout.get("subscription")
        if not isinstance(subscription_id, str) or not subscription_id:
            raise InvalidBillingEventError("Checkout session has no subscription")
        authoritative = await self._provider.get_subscription(subscription_id)
        source = authoritative or checkout
        source_metadata = self._metadata(source.get("metadata"))
        source_workspace_id = self._workspace_id(source_metadata, required=False)
        if workspace_id is None:
            workspace_id = source_workspace_id
        if workspace_id is None:
            raise InvalidBillingEventError("Stripe workspace metadata is missing")
        if source_workspace_id is not None and source_workspace_id != workspace_id:
            raise InvalidBillingEventError("Stripe workspace metadata mismatch")
        self._validate_price(source, checkout)
        status = source.get("status")
        if not isinstance(status, str) or not status:
            raise InvalidBillingEventError("Stripe subscription has no status")
        existing = await self._repository.get_subscription(workspace_id)
        if existing is not None:
            same_subscription = existing.stripe_subscription_id == subscription_id
            if not same_subscription and existing.status in {"active", "past_due"}:
                return
            if same_subscription and not self._is_newer(
                existing,
                event_created_at,
                event_id,
                "checkout.session.completed",
                subscription_id,
            ):
                return
        customer_id = source.get("customer") or checkout.get("customer")
        await self._repository.upsert_subscription(
            {
                "workspace_id": workspace_id,
                "stripe_customer_id": str(customer_id) if customer_id else None,
                "stripe_subscription_id": subscription_id,
                "stripe_event_id": event_id,
                "stripe_event_type": "checkout.session.completed",
                "stripe_event_created_at": event_created_at,
                "plan": "solo_monthly",
                "status": status,
                "trial_ends_at": None,
                "current_period_end": self._stripe_datetime(
                    source.get("current_period_end")
                ),
                "cancel_at_period_end": bool(source.get("cancel_at_period_end", False)),
            }
        )

    async def _process_subscription_event(
        self,
        event_id: str,
        event_created_at: datetime,
        event_type: str,
        subscription_data: dict[str, object],
    ) -> None:
        subscription_id = subscription_data.get("id")
        if not isinstance(subscription_id, str) or not subscription_id:
            raise InvalidBillingEventError("Stripe subscription event has no id")
        existing_by_id = await self._repository.get_by_stripe_subscription(
            subscription_id
        )
        metadata = self._metadata(subscription_data.get("metadata"))
        workspace_id = self._workspace_id(metadata, required=False)
        authoritative = await self._provider.get_subscription(subscription_id)
        authoritative_workspace_id = (
            self._workspace_id(
                self._metadata(authoritative.get("metadata")), required=False
            )
            if authoritative is not None
            else None
        )
        if (
            workspace_id is not None
            and authoritative_workspace_id is not None
            and workspace_id != authoritative_workspace_id
        ):
            raise InvalidBillingEventError("Stripe workspace metadata mismatch")
        if workspace_id is None:
            workspace_id = authoritative_workspace_id
        if workspace_id is None and existing_by_id is not None:
            workspace_id = existing_by_id.workspace_id
        if workspace_id is None:
            return
        existing = await self._repository.get_subscription(workspace_id)
        if (
            existing is not None
            and existing.stripe_subscription_id is not None
            and existing.stripe_subscription_id != subscription_id
        ):
            return
        if not self._is_newer(
            existing, event_created_at, event_id, event_type, subscription_id
        ):
            return
        source = subscription_data
        if event_type.endswith("updated"):
            if authoritative is None:
                authoritative = await self._provider.get_subscription(subscription_id)
            if authoritative is not None:
                source = authoritative
            if self._price_id(source) or self._price_id(subscription_data):
                self._validate_price(source, subscription_data)
        status = "canceled" if event_type.endswith("deleted") else source.get("status")
        if not isinstance(status, str) or not status:
            raise InvalidBillingEventError("Stripe subscription event has no status")
        customer_id = source.get("customer")
        await self._repository.upsert_subscription(
            {
                "workspace_id": workspace_id,
                "stripe_customer_id": str(customer_id) if customer_id else None,
                "stripe_subscription_id": subscription_id,
                "stripe_event_id": event_id,
                "stripe_event_type": event_type,
                "stripe_event_created_at": event_created_at,
                "plan": "solo_monthly",
                "status": status,
                "trial_ends_at": None,
                "current_period_end": self._stripe_datetime(
                    source.get("current_period_end")
                ),
                "cancel_at_period_end": bool(source.get("cancel_at_period_end", False)),
            }
        )

    def _validate_price(
        self,
        authoritative: dict[str, object],
        checkout: dict[str, object],
    ) -> None:
        expected = self._settings.stripe_solo_monthly_price_id
        if not expected:
            raise BillingUnavailableError("Solo monthly billing is not configured")
        actual = self._price_id(authoritative) or self._price_id(checkout)
        if actual != expected:
            raise InvalidBillingEventError("Checkout price is not configured for Kawu")

    @staticmethod
    def _price_id(source: dict[str, object]) -> str | None:
        items = source.get("items")
        if isinstance(items, dict):
            data = items.get("data")
            if isinstance(data, list) and data:
                first = data[0]
                if isinstance(first, dict):
                    price = first.get("price")
                    if isinstance(price, str):
                        return price
                    if isinstance(price, dict) and isinstance(price.get("id"), str):
                        return price["id"]
        line_items = source.get("line_items")
        if isinstance(line_items, dict):
            data = line_items.get("data")
            if isinstance(data, list) and data:
                first = data[0]
                if isinstance(first, dict):
                    price = first.get("price")
                    if isinstance(price, str):
                        return price
                    if isinstance(price, dict) and isinstance(price.get("id"), str):
                        return price["id"]
        for key in ("price_id",):
            value = source.get(key)
            if isinstance(value, str):
                return value
        metadata = source.get("metadata")
        if isinstance(metadata, dict) and isinstance(metadata.get("price_id"), str):
            return metadata["price_id"]
        return None

    @staticmethod
    def _metadata(value: object) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _workspace_id(
        metadata: dict[str, object], *, required: bool = True
    ) -> uuid.UUID | None:
        raw = metadata.get("workspace_id")
        if raw is None and not required:
            return None
        try:
            return uuid.UUID(str(raw))
        except (ValueError, AttributeError) as exc:
            raise InvalidBillingEventError(
                "Stripe workspace metadata is invalid"
            ) from exc

    @staticmethod
    def _stripe_datetime(value: object) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, (int, float)):
            raise InvalidBillingEventError("Stripe period value is invalid")
        try:
            return datetime.fromtimestamp(value, UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise InvalidBillingEventError("Stripe period value is invalid") from exc

    @staticmethod
    def _is_newer(
        existing: WorkspaceSubscription | None,
        event_created_at: datetime,
        event_id: str,
        event_type: str,
        subscription_id: str,
    ) -> bool:
        if existing is None or existing.stripe_event_created_at is None:
            return True
        if existing.stripe_subscription_id != subscription_id:
            if existing.stripe_subscription_id is None:
                return True
            return event_type == "checkout.session.completed" and (
                existing.status == "canceled"
            )
        if event_created_at > existing.stripe_event_created_at:
            # Cancellation is terminal only for this Stripe subscription ID.
            return existing.status != "canceled" or (
                event_type == "customer.subscription.deleted"
            )
        if event_created_at < existing.stripe_event_created_at:
            return False
        if event_type == "customer.subscription.deleted":
            return True
        if existing.status == "canceled":
            return False
        return event_id > (existing.stripe_event_id or "")

    async def record_report_generation(self, workspace_id: uuid.UUID) -> None:
        period_start = date.today().replace(day=1)
        await self._repository.increment_report_usage(workspace_id, period_start)
