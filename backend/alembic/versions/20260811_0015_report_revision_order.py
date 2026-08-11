"""Persist report revision order independently of transaction timestamps."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260811_0015"
down_revision: str | None = "20260811_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVISION_NUMBER_UNIQUE_KEY = "uq_report_revisions_report_revision_number"
REVISION_NUMBER_CHECK = "ck_report_revisions_report_revision_number_positive"
OLD_CREATED_ORDER_INDEX = "ix_report_revisions_report_created_id"


def _backfill_revision_numbers() -> None:
    """Assign the former API order to every legacy revision deterministically."""

    # The legacy table's immutability trigger also sees this migration's
    # one-time population of the new column.  Disable only that trigger for
    # the backfill and always restore it before the migration continues.
    op.execute(
        "ALTER TABLE report_revisions DISABLE TRIGGER report_revisions_immutable_update"
    )
    try:
        op.execute(
            """
            WITH ordered_revisions AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY report_id
                        ORDER BY created_at ASC, id ASC
                    )::integer AS revision_number
                FROM report_revisions
            )
            UPDATE report_revisions AS revision
            SET revision_number = ordered_revisions.revision_number
            FROM ordered_revisions
            WHERE revision.id = ordered_revisions.id
            """
        )
    finally:
        op.execute(
            "ALTER TABLE report_revisions "
            "ENABLE TRIGGER report_revisions_immutable_update"
        )


def upgrade() -> None:
    op.add_column(
        "report_revisions",
        sa.Column("revision_number", sa.Integer(), nullable=True),
    )
    _backfill_revision_numbers()
    op.alter_column("report_revisions", "revision_number", nullable=False)
    op.create_check_constraint(
        op.f(REVISION_NUMBER_CHECK),
        "report_revisions",
        "revision_number > 0",
    )
    op.create_unique_constraint(
        REVISION_NUMBER_UNIQUE_KEY,
        "report_revisions",
        ["report_id", "revision_number"],
    )
    op.drop_index(OLD_CREATED_ORDER_INDEX, table_name="report_revisions")


def downgrade() -> None:
    op.create_index(
        OLD_CREATED_ORDER_INDEX,
        "report_revisions",
        ["report_id", "created_at", "id"],
        unique=False,
    )
    op.drop_constraint(
        REVISION_NUMBER_UNIQUE_KEY,
        "report_revisions",
        type_="unique",
    )
    op.drop_constraint(op.f(REVISION_NUMBER_CHECK), "report_revisions", type_="check")
    op.drop_column("report_revisions", "revision_number")
