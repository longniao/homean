"""Place captured photos in the room they were taken in."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260813_0017"
down_revision: str | None = "20260813_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ZONE_FK = "fk_raw_media_zone_id_zones"
ZONE_INDEX = "ix_raw_media_zone_id"


def upgrade() -> None:
    op.add_column("raw_media", sa.Column("zone_id", sa.Uuid(), nullable=True))
    op.add_column("raw_media", sa.Column("zone_source", sa.Text(), nullable=True))
    # Zones are rebuilt on reprocessing, so a dropped zone must clear the link
    # rather than delete the capture it points at.
    op.create_foreign_key(
        ZONE_FK, "raw_media", "zones", ["zone_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index(ZONE_INDEX, "raw_media", ["zone_id"], unique=False)


def downgrade() -> None:
    op.drop_index(ZONE_INDEX, table_name="raw_media")
    op.drop_constraint(ZONE_FK, "raw_media", type_="foreignkey")
    op.drop_column("raw_media", "zone_source")
    op.drop_column("raw_media", "zone_id")
