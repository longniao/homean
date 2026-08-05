"""Add workspace capture fields.

Revision ID: 20260804_0002
Revises: 20260804_0001
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260804_0002"
down_revision: str | None = "20260804_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("contacts", sa.Column("email", sa.Text(), nullable=True))
    op.add_column("contacts", sa.Column("phone", sa.Text(), nullable=True))
    op.add_column("contacts", sa.Column("notes", sa.Text(), nullable=True))

    op.add_column("subjects", sa.Column("workspace_id", UUID, nullable=False))
    op.create_foreign_key(
        op.f("fk_subjects_workspace_id_workspaces"),
        "subjects",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_subjects_workspace_id", "subjects", ["workspace_id"], unique=False
    )

    op.add_column(
        "visits",
        sa.Column(
            "processing_status",
            sa.Text(),
            server_default="not_started",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_visits_processing_status",
        "visits",
        ["processing_status"],
        unique=False,
    )

    op.add_column(
        "raw_media",
        sa.Column(
            "content_type",
            sa.Text(),
            server_default="application/octet-stream",
            nullable=False,
        ),
    )
    op.alter_column("raw_media", "content_type", server_default=None)
    op.add_column(
        "raw_media",
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
    )
    op.add_column("raw_media", sa.Column("size_bytes", sa.BigInteger(), nullable=True))
    op.create_index("ix_raw_media_status", "raw_media", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_raw_media_status", table_name="raw_media")
    op.drop_column("raw_media", "size_bytes")
    op.drop_column("raw_media", "status")
    op.drop_column("raw_media", "content_type")

    op.drop_index("ix_visits_processing_status", table_name="visits")
    op.drop_column("visits", "processing_status")

    op.drop_index("ix_subjects_workspace_id", table_name="subjects")
    op.drop_constraint(
        op.f("fk_subjects_workspace_id_workspaces"),
        "subjects",
        type_="foreignkey",
    )
    op.drop_column("subjects", "workspace_id")

    op.drop_column("contacts", "notes")
    op.drop_column("contacts", "phone")
    op.drop_column("contacts", "email")
