"""Keep the diarized speaker for each transcript segment."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260814_0019"
down_revision: str | None = "20260814_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable with no backfill. Recordings transcribed before diarization was
    # enabled cannot be attributed after the fact, and guessing a speaker on an
    # evidence record would be worse than leaving it unknown.
    op.add_column(
        "transcript_segments", sa.Column("speaker", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("transcript_segments", "speaker")
