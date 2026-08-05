"""Allow subject-less draft visits.

Revision ID: 20260805_0005
Revises: 20260804_0004
Create Date: 2026-08-05
"""

from collections.abc import Sequence

from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260805_0005"
down_revision: str | None = "20260804_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "visits",
        "subject_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "visits",
        "subject_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
