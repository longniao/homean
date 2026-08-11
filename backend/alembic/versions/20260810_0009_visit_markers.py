"""Persist timestamp markers created during mobile capture."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260810_0009"
down_revision: str | None = "20260807_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "visit_markers",
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
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "marker_type",
            sa.Text(),
            server_default="voice_tag",
            nullable=False,
        ),
        sa.Column("timestamp_offset_ms", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["visit_id"],
            ["visits.id"],
            name=op.f("fk_visit_markers_visit_id_visits"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_visit_markers_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visit_markers")),
        sa.UniqueConstraint(
            "visit_id",
            "client_id",
            name="uq_visit_markers_visit_client_id",
        ),
    )
    op.create_index(
        "ix_visit_markers_visit_id", "visit_markers", ["visit_id"], unique=False
    )
    op.create_index(
        "ix_visit_markers_created_by", "visit_markers", ["created_by"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_visit_markers_created_by", table_name="visit_markers")
    op.drop_index("ix_visit_markers_visit_id", table_name="visit_markers")
    op.drop_table("visit_markers")
