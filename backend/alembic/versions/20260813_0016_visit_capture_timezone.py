"""Record the timezone a visit was captured in so reports can print its date."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260813_0016"
down_revision: str | None = "20260811_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable with no backfill: existing visits have no recoverable capture
    # zone, and the renderer falls back to UTC for them.
    op.add_column(
        "visits",
        sa.Column("capture_timezone", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("visits", "capture_timezone")
