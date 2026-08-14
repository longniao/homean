"""Record which consent wording was attested to, and when it was received."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260814_0018"
down_revision: str | None = "20260813_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Both nullable with no backfill. Visits captured before this recorded only
    # that an attestation happened, and inventing a wording or a time for them
    # would be worse than leaving the gap visible.
    op.add_column("visits", sa.Column("consent_text_version", sa.Text(), nullable=True))
    op.add_column(
        "visits",
        sa.Column("consent_recorded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("visits", "consent_recorded_at")
    op.drop_column("visits", "consent_text_version")
