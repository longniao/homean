"""Make Stripe webhook processing durable and public token lookup indexed."""

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260806_0007"
down_revision: str | None = "20260805_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _token_lookup_hash(token: str) -> str:
    return hashlib.sha256(b"kawu-share-token-v1:\0" + token.encode("ascii")).hexdigest()


def upgrade() -> None:
    op.add_column(
        "workspace_subscriptions",
        sa.Column("stripe_event_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "workspace_subscriptions",
        sa.Column("stripe_event_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_workspace_subscriptions_stripe_event_id",
        "workspace_subscriptions",
        ["stripe_event_id"],
    )

    op.create_table(
        "stripe_webhook_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
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
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("stripe_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stripe_webhook_events")),
        sa.UniqueConstraint("event_id", name="uq_stripe_webhook_events_event_id"),
    )
    op.create_index(
        "ix_stripe_webhook_events_event_id", "stripe_webhook_events", ["event_id"]
    )

    op.add_column(
        "report_share_links",
        sa.Column("token_lookup_hash", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_report_share_links_token_lookup_hash",
        "report_share_links",
        ["token_lookup_hash"],
    )
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, token FROM report_share_links")).mappings()
    for row in rows:
        bind.execute(
            sa.text(
                "UPDATE report_share_links SET token_lookup_hash = :token_lookup_hash "
                "WHERE id = :id"
            ),
            {"id": row["id"], "token_lookup_hash": _token_lookup_hash(row["token"])},
        )
    op.alter_column("report_share_links", "token_lookup_hash", nullable=False)


def downgrade() -> None:
    op.drop_index(
        "ix_report_share_links_token_lookup_hash", table_name="report_share_links"
    )
    op.drop_column("report_share_links", "token_lookup_hash")
    op.drop_index(
        "ix_stripe_webhook_events_event_id", table_name="stripe_webhook_events"
    )
    op.drop_table("stripe_webhook_events")
    op.drop_index(
        "ix_workspace_subscriptions_stripe_event_id",
        table_name="workspace_subscriptions",
    )
    op.drop_column("workspace_subscriptions", "stripe_event_created_at")
    op.drop_column("workspace_subscriptions", "stripe_event_id")
