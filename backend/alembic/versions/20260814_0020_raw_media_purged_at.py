"""Mark raw media whose stored object has been purged by retention."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260814_0020"
down_revision: str | None = "20260814_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The row survives the object. Deleting the row would break the evidence
    # chain silently — an observation would point at media that never existed,
    # rather than at media that was retained for a stated period and removed.
    op.add_column(
        "raw_media", sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("raw_media", "purged_at")
