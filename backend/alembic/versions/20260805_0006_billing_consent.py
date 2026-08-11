"""Add workspace billing state, report usage, and recording consent."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260805_0006"
down_revision: str | None = "20260805_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def id_and_timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "id",
            UUID,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.add_column(
        "visits",
        sa.Column(
            "consent_ack", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )

    op.create_table(
        "workspace_subscriptions",
        *id_and_timestamps(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("stripe_customer_id", sa.Text(), nullable=True),
        sa.Column("stripe_subscription_id", sa.Text(), nullable=True),
        sa.Column("plan", sa.Text(), server_default="trial", nullable=False),
        sa.Column("status", sa.Text(), server_default="trialing", nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_workspace_subscriptions_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_subscriptions")),
        sa.UniqueConstraint(
            "workspace_id", name="uq_workspace_subscriptions_workspace_id"
        ),
        sa.UniqueConstraint(
            "stripe_subscription_id",
            name="uq_workspace_subscriptions_stripe_subscription_id",
        ),
    )
    op.create_index(
        "ix_workspace_subscriptions_workspace_id",
        "workspace_subscriptions",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspace_subscriptions_stripe_customer_id",
        "workspace_subscriptions",
        ["stripe_customer_id"],
    )
    op.create_index(
        "ix_workspace_subscriptions_stripe_subscription_id",
        "workspace_subscriptions",
        ["stripe_subscription_id"],
    )
    op.create_index(
        "ix_workspace_subscriptions_status", "workspace_subscriptions", ["status"]
    )

    op.create_table(
        "workspace_report_usage",
        *id_and_timestamps(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("report_count", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_workspace_report_usage_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_report_usage")),
        sa.UniqueConstraint(
            "workspace_id", "period_start", name="uq_workspace_report_usage_period"
        ),
    )
    op.create_index(
        "ix_workspace_report_usage_workspace_id",
        "workspace_report_usage",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspace_report_usage_period_start",
        "workspace_report_usage",
        ["period_start"],
    )

    # Existing workspaces receive the same default 14-day trial as new signups.
    op.execute(
        sa.text(
            "INSERT INTO workspace_subscriptions "
            "(id, workspace_id, plan, status, trial_ends_at) "
            "SELECT gen_random_uuid(), id, 'trial', 'trialing', "
            "now() + interval '14 days' "
            "FROM workspaces"
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workspace_report_usage_period_start", table_name="workspace_report_usage"
    )
    op.drop_index(
        "ix_workspace_report_usage_workspace_id", table_name="workspace_report_usage"
    )
    op.drop_table("workspace_report_usage")
    op.drop_index(
        "ix_workspace_subscriptions_status", table_name="workspace_subscriptions"
    )
    op.drop_index(
        "ix_workspace_subscriptions_stripe_subscription_id",
        table_name="workspace_subscriptions",
    )
    op.drop_index(
        "ix_workspace_subscriptions_stripe_customer_id",
        table_name="workspace_subscriptions",
    )
    op.drop_index(
        "ix_workspace_subscriptions_workspace_id",
        table_name="workspace_subscriptions",
    )
    op.drop_table("workspace_subscriptions")
    op.drop_column("visits", "consent_ack")
