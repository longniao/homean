"""Make email delivery attempts durable and safe around SMTP ambiguity."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260810_0013"
down_revision: str | None = "20260810_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ``message_id`` is nullable for link-only deliveries and for legacy email
    # attempts whose provider acceptance cannot be established. Only rows
    # already known to be sent get a deterministic backfill.
    op.add_column("report_sends", sa.Column("message_id", sa.Text(), nullable=True))
    op.add_column(
        "report_sends",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "report_sends",
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE report_sends
        SET attempt_count = 1,
            last_attempt_at = created_at
        WHERE channel = 'email'
        """
    )
    op.execute(
        """
        UPDATE report_sends
        SET status = 'outcome_unknown',
            message_id = NULL,
            error = 'Legacy email delivery state was quarantined during upgrade; '
                    || 'the delivery outcome is unknown.'
        WHERE channel = 'email' AND status IN ('pending', 'failed')
        """
    )
    op.execute(
        """
        UPDATE report_sends
        SET message_id = '<kawu-report-' || id::text || '@kawu.local>'
        WHERE channel = 'email' AND status = 'sent' AND message_id IS NULL
        """
    )
    op.create_unique_constraint(
        "uq_report_sends_message_id", "report_sends", ["message_id"]
    )
    op.create_check_constraint(
        op.f("ck_report_sends_report_send_status"),
        "report_sends",
        "status IN ('pending', 'sent', 'failed', 'outcome_unknown')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_report_sends_report_send_status", "report_sends", type_="check"
    )
    op.drop_constraint("uq_report_sends_message_id", "report_sends", type_="unique")
    op.drop_column("report_sends", "last_attempt_at")
    op.drop_column("report_sends", "attempt_count")
    op.drop_column("report_sends", "message_id")
