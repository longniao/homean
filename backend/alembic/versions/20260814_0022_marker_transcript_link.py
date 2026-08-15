"""Resolve each voice tag to the transcript segment it bookmarks."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260814_0022"
down_revision: str | None = "20260814_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEGMENT_FK = "fk_visit_markers_transcript_segment_id"
SEGMENT_INDEX = "ix_visit_markers_transcript_segment_id"


def upgrade() -> None:
    op.add_column(
        "visit_markers", sa.Column("transcript_segment_id", sa.Uuid(), nullable=True)
    )
    # Reprocessing rebuilds transcripts, so a dropped segment must clear the
    # link rather than delete the agent's marker: the tap is the agent's, the
    # segment it resolves to is derived and can be recomputed.
    op.create_foreign_key(
        SEGMENT_FK,
        "visit_markers",
        "transcript_segments",
        ["transcript_segment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        SEGMENT_INDEX, "visit_markers", ["transcript_segment_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(SEGMENT_INDEX, table_name="visit_markers")
    op.drop_constraint(SEGMENT_FK, "visit_markers", type_="foreignkey")
    op.drop_column("visit_markers", "transcript_segment_id")
