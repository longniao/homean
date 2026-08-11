"""Track Stripe event type for equal-second ordering."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260807_0008"
down_revision: str | None = "20260806_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspace_subscriptions",
        sa.Column("stripe_event_type", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workspace_subscriptions", "stripe_event_type")
