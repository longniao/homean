"""Add durable mobile media identity for idempotent presigning."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260810_0012"
down_revision: str | None = "20260810_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "raw_media",
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_raw_media_visit_client_id",
        "raw_media",
        ["visit_id", "client_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_raw_media_visit_client_id", "raw_media", type_="unique")
    op.drop_column("raw_media", "client_id")
