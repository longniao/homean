"""Add review, branding, sharing, and delivery persistence.

Revision ID: 20260804_0004
Revises: 20260804_0003
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260804_0004"
down_revision: str | None = "20260804_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def id_and_timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "id",
            UUID,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.add_column(
        "transcript_segments", sa.Column("original_text", sa.Text(), nullable=True)
    )

    op.create_table(
        "workspace_branding",
        *id_and_timestamps(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("logo_key", sa.Text(), nullable=True),
        sa.Column("logo_content_type", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("license_no", sa.Text(), nullable=True),
        sa.Column(
            "accent_color", sa.Text(), server_default="#1F6F5B", nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_workspace_branding_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_branding")),
        sa.UniqueConstraint(
            "workspace_id", name="uq_workspace_branding_workspace_id"
        ),
    )
    op.create_index(
        "ix_workspace_branding_workspace_id",
        "workspace_branding",
        ["workspace_id"],
    )

    op.create_table(
        "report_share_links",
        *id_and_timestamps(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("report_id", UUID, nullable=False),
        sa.Column("created_by", UUID, nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_report_share_links_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            name=op.f("fk_report_share_links_report_id_reports"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_report_share_links_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_share_links")),
    )
    op.create_index(
        "ix_report_share_links_workspace_id", "report_share_links", ["workspace_id"]
    )
    op.create_index(
        "ix_report_share_links_report_id", "report_share_links", ["report_id"]
    )
    op.create_index(
        "ix_report_share_links_created_by", "report_share_links", ["created_by"]
    )
    op.create_index(
        "ix_report_share_links_token", "report_share_links", ["token"], unique=True
    )
    op.create_index(
        "ix_report_share_links_expires_at", "report_share_links", ["expires_at"]
    )
    op.create_index(
        "ix_report_share_links_revoked_at", "report_share_links", ["revoked_at"]
    )

    op.create_table(
        "report_share_views",
        *id_and_timestamps(),
        sa.Column("share_link_id", UUID, nullable=False),
        sa.Column("user_agent_hash", sa.Text(), nullable=False),
        sa.Column("view_type", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["share_link_id"],
            ["report_share_links.id"],
            name=op.f("fk_report_share_views_share_link_id_report_share_links"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_share_views")),
    )
    op.create_index(
        "ix_report_share_views_share_link_id",
        "report_share_views",
        ["share_link_id"],
    )

    op.create_table(
        "report_sends",
        *id_and_timestamps(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("visit_id", UUID, nullable=False),
        sa.Column("report_id", UUID, nullable=False),
        sa.Column("share_link_id", UUID, nullable=False),
        sa.Column("sent_by", UUID, nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("to_email", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_report_sends_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["visit_id"],
            ["visits.id"],
            name=op.f("fk_report_sends_visit_id_visits"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            name=op.f("fk_report_sends_report_id_reports"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["share_link_id"],
            ["report_share_links.id"],
            name=op.f("fk_report_sends_share_link_id_report_share_links"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sent_by"],
            ["users.id"],
            name=op.f("fk_report_sends_sent_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_sends")),
    )
    for column in (
        "workspace_id",
        "visit_id",
        "report_id",
        "share_link_id",
        "sent_by",
        "status",
    ):
        op.create_index(f"ix_report_sends_{column}", "report_sends", [column])


def downgrade() -> None:
    for column in reversed(
        (
            "workspace_id",
            "visit_id",
            "report_id",
            "share_link_id",
            "sent_by",
            "status",
        )
    ):
        op.drop_index(f"ix_report_sends_{column}", table_name="report_sends")
    op.drop_table("report_sends")

    op.drop_index(
        "ix_report_share_views_share_link_id", table_name="report_share_views"
    )
    op.drop_table("report_share_views")

    op.drop_index("ix_report_share_links_revoked_at", table_name="report_share_links")
    op.drop_index("ix_report_share_links_expires_at", table_name="report_share_links")
    op.drop_index("ix_report_share_links_token", table_name="report_share_links")
    op.drop_index("ix_report_share_links_created_by", table_name="report_share_links")
    op.drop_index("ix_report_share_links_report_id", table_name="report_share_links")
    op.drop_index("ix_report_share_links_workspace_id", table_name="report_share_links")
    op.drop_table("report_share_links")

    op.drop_index(
        "ix_workspace_branding_workspace_id", table_name="workspace_branding"
    )
    op.drop_table("workspace_branding")

    op.drop_column("transcript_segments", "original_text")
