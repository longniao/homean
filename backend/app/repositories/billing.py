import uuid
from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StripeWebhookEvent, WorkspaceReportUsage, WorkspaceSubscription


class BillingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_subscription(
        self, workspace_id: uuid.UUID
    ) -> WorkspaceSubscription | None:
        return await self.session.scalar(
            select(WorkspaceSubscription).where(
                WorkspaceSubscription.workspace_id == workspace_id
            )
        )

    async def get_by_stripe_subscription(
        self, stripe_subscription_id: str
    ) -> WorkspaceSubscription | None:
        return await self.session.scalar(
            select(WorkspaceSubscription).where(
                WorkspaceSubscription.stripe_subscription_id == stripe_subscription_id
            )
        )

    async def record_webhook_event(
        self,
        *,
        event_id: str,
        event_type: str,
        stripe_created_at: object,
    ) -> bool:
        statement = insert(StripeWebhookEvent).values(
            event_id=event_id,
            event_type=event_type,
            stripe_created_at=stripe_created_at,
        )
        result = await self.session.execute(
            statement.on_conflict_do_nothing(
                constraint="uq_stripe_webhook_events_event_id"
            )
        )
        return result.rowcount == 1

    def add(self, *entities: object) -> None:
        self.session.add_all(entities)

    async def flush(self) -> None:
        await self.session.flush()

    async def upsert_subscription(self, values: dict[str, object]) -> None:
        statement = insert(WorkspaceSubscription).values(**values)
        update_values = {
            key: value
            for key, value in values.items()
            if key not in {"workspace_id", "id"}
        }
        event_created_at = values.get("stripe_event_created_at")
        conflict_kwargs: dict[str, object] = {}
        if event_created_at is not None:
            event_type = values.get("stripe_event_type")
            event_id = values.get("stripe_event_id")
            subscription_id = values.get("stripe_subscription_id")
            same_subscription_id = (
                WorkspaceSubscription.stripe_subscription_id == subscription_id
            )
            same_or_unbound = or_(
                WorkspaceSubscription.stripe_subscription_id.is_(None),
                same_subscription_id,
            )
            different_or_unbound = or_(
                WorkspaceSubscription.stripe_subscription_id.is_(None),
                WorkspaceSubscription.stripe_subscription_id != subscription_id,
            )
            not_canceled_or_unbound = or_(
                WorkspaceSubscription.status != "canceled",
                WorkspaceSubscription.stripe_subscription_id.is_(None),
            )
            newer = or_(
                WorkspaceSubscription.stripe_event_created_at.is_(None),
                WorkspaceSubscription.stripe_event_created_at < event_created_at,
            )
            equal_timestamp = (
                WorkspaceSubscription.stripe_event_created_at == event_created_at
            )
            equal_event_order = isinstance(event_id, str) and or_(
                WorkspaceSubscription.stripe_event_id.is_(None),
                WorkspaceSubscription.stripe_event_id < event_id,
            )
            if event_type == "checkout.session.completed":
                # A canceled subscription can be replaced by Checkout, even
                # when Stripe assigned the same second-level timestamp.
                conflict_kwargs["where"] = or_(
                    and_(
                        WorkspaceSubscription.status == "canceled",
                        different_or_unbound,
                    ),
                    and_(
                        newer,
                        same_or_unbound,
                        not_canceled_or_unbound,
                    ),
                    and_(
                        equal_timestamp,
                        same_or_unbound,
                        not_canceled_or_unbound,
                        equal_event_order,
                    ),
                )
            elif event_type == "customer.subscription.deleted":
                # Stripe timestamps have only second precision. A deletion is
                # terminal for the same subscription ID and cannot affect a
                # replacement subscription.
                conflict_kwargs["where"] = and_(
                    same_or_unbound, or_(newer, equal_timestamp)
                )
            elif isinstance(event_id, str):
                # Equal-second non-terminal events are deterministic by event
                # ID, but never resurrect a canceled subscription or replace a
                # newer subscription with an old subscription's event.
                conflict_kwargs["where"] = and_(
                    same_or_unbound,
                    or_(
                        and_(newer, not_canceled_or_unbound),
                        and_(
                            equal_timestamp,
                            not_canceled_or_unbound,
                            or_(
                                WorkspaceSubscription.stripe_event_id.is_(None),
                                WorkspaceSubscription.stripe_event_id < event_id,
                            ),
                        ),
                    ),
                )
            else:
                conflict_kwargs["where"] = newer
        await self.session.execute(
            statement.on_conflict_do_update(
                constraint="uq_workspace_subscriptions_workspace_id",
                set_={**update_values, "updated_at": func.now()},
                **conflict_kwargs,
            )
        )

    async def increment_report_usage(
        self, workspace_id: uuid.UUID, period_start: date
    ) -> None:
        statement = insert(WorkspaceReportUsage).values(
            workspace_id=workspace_id,
            period_start=period_start,
            report_count=1,
        )
        await self.session.execute(
            statement.on_conflict_do_update(
                constraint="uq_workspace_report_usage_period",
                set_={
                    "report_count": WorkspaceReportUsage.report_count + 1,
                    "updated_at": func.now(),
                },
            )
        )
