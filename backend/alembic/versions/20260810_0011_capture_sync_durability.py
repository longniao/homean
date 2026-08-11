"""Add durable mobile capture identity and presign expiry metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260810_0011"
down_revision: str | None = "20260810_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "visits",
        sa.Column("capture_client_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_visits_workspace_capture_client_id",
        "visits",
        ["workspace_id", "capture_client_id"],
    )
    op.add_column(
        "raw_media",
        sa.Column("upload_url_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("raw_media", "upload_url_expires_at")
    op.drop_constraint(
        "uq_visits_workspace_capture_client_id", "visits", type_="unique"
    )
    op.drop_column("visits", "capture_client_id")
