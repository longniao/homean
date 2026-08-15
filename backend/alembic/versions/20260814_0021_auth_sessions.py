"""Back refresh tokens with revocable, absolutely-expiring server sessions."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260814_0021"
down_revision: str | None = "20260814_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TOKEN_HASH_INDEX = "ix_auth_sessions_refresh_token_hash"


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Only the digest is stored. A database copy therefore cannot be
        # replayed as a set of working refresh tokens.
        sa.Column("refresh_token_hash", sa.Text(), nullable=False),
        # Absolute, set once at login and never moved. Refreshing issues a new
        # access token but must not buy the session more life, or a stolen
        # token in continuous use would never expire.
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        TOKEN_HASH_INDEX, "auth_sessions", ["refresh_token_hash"], unique=True
    )
    # No backfill. Pre-launch refresh tokens were stateless JWTs that cannot be
    # revoked, so they are deliberately abandoned rather than adopted: every
    # existing client is signed out once and must authenticate again.


def downgrade() -> None:
    op.drop_index(TOKEN_HASH_INDEX, table_name="auth_sessions")
    op.drop_table("auth_sessions")
