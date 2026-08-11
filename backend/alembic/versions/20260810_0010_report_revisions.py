"""Persist immutable before/after snapshots for report edits."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260810_0010"
down_revision: str | None = "20260810_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_revisions",
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
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("edited_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "previous_content",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "new_content", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_report_revisions_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            name=op.f("fk_report_revisions_report_id_reports"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["visit_id"],
            ["visits.id"],
            name=op.f("fk_report_revisions_visit_id_visits"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["edited_by"],
            ["users.id"],
            name=op.f("fk_report_revisions_edited_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_revisions")),
    )
    for column in ("workspace_id", "report_id", "visit_id", "edited_by"):
        op.create_index(
            f"ix_report_revisions_{column}",
            "report_revisions",
            [column],
            unique=False,
        )
    op.create_index(
        "ix_report_revisions_report_created_id",
        "report_revisions",
        ["report_id", "created_at", "id"],
        unique=False,
    )

    # Revision rows are append-only.  Parent report/visit cleanup is still
    # allowed through the CASCADE foreign keys, but no revision can be edited.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_report_revision_update()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'report revisions are immutable';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER report_revisions_immutable_update
        BEFORE UPDATE ON report_revisions
        FOR EACH ROW
        EXECUTE FUNCTION prevent_report_revision_update();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER report_revisions_immutable_update ON report_revisions")
    op.execute("DROP FUNCTION prevent_report_revision_update()")
    op.drop_index(
        "ix_report_revisions_report_created_id", table_name="report_revisions"
    )
    for column in ("edited_by", "visit_id", "report_id", "workspace_id"):
        op.drop_index(f"ix_report_revisions_{column}", table_name="report_revisions")
    op.drop_table("report_revisions")
