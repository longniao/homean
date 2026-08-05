"""Create the Kawu core schema.

Revision ID: 20260804_0001
Revises:
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260804_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


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
    op.create_table(
        "users",
        *id_and_timestamps(),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "workspaces",
        *id_and_timestamps(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), server_default="en", nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
    )

    op.create_table(
        "verticals",
        *id_and_timestamps(),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("zone_taxonomy", JSONB, nullable=False),
        sa.Column("observation_schema", JSONB, nullable=False),
        sa.Column("zone_labels", JSONB, nullable=False),
        sa.Column("observation_labels", JSONB, nullable=False),
        sa.Column("prompt_templates", JSONB, nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("report_template_id", sa.Text(), nullable=False),
        sa.Column("report_labels", JSONB, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_verticals")),
    )
    op.create_index("ix_verticals_slug", "verticals", ["slug"], unique=True)

    op.create_table(
        "memberships",
        *id_and_timestamps(),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_memberships_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_memberships_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint(
            "user_id", "workspace_id", name="uq_memberships_user_workspace"
        ),
    )
    op.create_index(
        "ix_memberships_workspace_id", "memberships", ["workspace_id"], unique=False
    )

    op.create_table(
        "professional_profiles",
        *id_and_timestamps(),
        sa.Column("membership_id", UUID, nullable=False),
        sa.Column("vertical_id", UUID, nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["memberships.id"],
            name=op.f("fk_professional_profiles_membership_id_memberships"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vertical_id"],
            ["verticals.id"],
            name=op.f("fk_professional_profiles_vertical_id_verticals"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_professional_profiles")),
        sa.UniqueConstraint(
            "membership_id",
            "vertical_id",
            name="uq_professional_profiles_membership_vertical",
        ),
    )
    op.create_index(
        "ix_professional_profiles_membership_id",
        "professional_profiles",
        ["membership_id"],
        unique=False,
    )
    op.create_index(
        "ix_professional_profiles_vertical_id",
        "professional_profiles",
        ["vertical_id"],
        unique=False,
    )

    op.create_table(
        "contacts",
        *id_and_timestamps(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("contact_info", JSONB, server_default="{}", nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_contacts_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
    )
    op.create_index(
        "ix_contacts_workspace_id", "contacts", ["workspace_id"], unique=False
    )

    op.create_table(
        "subjects",
        *id_and_timestamps(),
        sa.Column("vertical_id", UUID, nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("attributes", JSONB, server_default="{}", nullable=False),
        sa.ForeignKeyConstraint(
            ["vertical_id"],
            ["verticals.id"],
            name=op.f("fk_subjects_vertical_id_verticals"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subjects")),
    )
    op.create_index(
        "ix_subjects_vertical_id", "subjects", ["vertical_id"], unique=False
    )

    op.create_table(
        "visits",
        *id_and_timestamps(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("subject_id", UUID, nullable=False),
        sa.Column("created_by", UUID, nullable=False),
        sa.Column("contact_id", UUID, nullable=True),
        sa.Column("professional_profile_id", UUID, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'confirmed', 'sent_to_client')",
            name=op.f("ck_visits_visit_status"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_visits_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_visits_subject_id_subjects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_visits_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contacts.id"],
            name=op.f("fk_visits_contact_id_contacts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["professional_profile_id"],
            ["professional_profiles.id"],
            name=op.f("fk_visits_professional_profile_id_professional_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visits")),
    )
    for column in (
        "workspace_id",
        "subject_id",
        "created_by",
        "contact_id",
        "professional_profile_id",
        "status",
    ):
        op.create_index(f"ix_visits_{column}", "visits", [column], unique=False)

    op.create_table(
        "zones",
        *id_and_timestamps(),
        sa.Column("visit_id", UUID, nullable=False),
        sa.Column("zone_type", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["visit_id"],
            ["visits.id"],
            name=op.f("fk_zones_visit_id_visits"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_zones")),
    )
    op.create_index("ix_zones_visit_id", "zones", ["visit_id"], unique=False)

    op.create_table(
        "raw_media",
        *id_and_timestamps(),
        sa.Column("visit_id", UUID, nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("storage_url", sa.Text(), nullable=False),
        sa.Column("timestamp_offset", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["visit_id"],
            ["visits.id"],
            name=op.f("fk_raw_media_visit_id_visits"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_raw_media")),
    )
    op.create_index("ix_raw_media_visit_id", "raw_media", ["visit_id"], unique=False)

    op.create_table(
        "transcript_segments",
        *id_and_timestamps(),
        sa.Column("visit_id", UUID, nullable=False),
        sa.Column("raw_media_id", UUID, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("timestamp_start", sa.Float(), nullable=True),
        sa.Column("timestamp_end", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["visit_id"],
            ["visits.id"],
            name=op.f("fk_transcript_segments_visit_id_visits"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["raw_media_id"],
            ["raw_media.id"],
            name=op.f("fk_transcript_segments_raw_media_id_raw_media"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transcript_segments")),
    )
    op.create_index(
        "ix_transcript_segments_visit_id",
        "transcript_segments",
        ["visit_id"],
        unique=False,
    )
    op.create_index(
        "ix_transcript_segments_raw_media_id",
        "transcript_segments",
        ["raw_media_id"],
        unique=False,
    )

    op.create_table(
        "observations",
        *id_and_timestamps(),
        sa.Column("visit_id", UUID, nullable=False),
        sa.Column("zone_id", UUID, nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_transcript_segment_id", UUID, nullable=True),
        sa.Column("source_media_id", UUID, nullable=True),
        sa.Column("timestamp_start", sa.Float(), nullable=True),
        sa.Column("timestamp_end", sa.Float(), nullable=True),
        sa.Column("ai_model", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("review_status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("reviewed_by", UUID, nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["visit_id"],
            ["visits.id"],
            name=op.f("fk_observations_visit_id_visits"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["zone_id"],
            ["zones.id"],
            name=op.f("fk_observations_zone_id_zones"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_transcript_segment_id"],
            ["transcript_segments.id"],
            name=op.f(
                "fk_observations_source_transcript_segment_id_transcript_segments"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_media_id"],
            ["raw_media.id"],
            name=op.f("fk_observations_source_media_id_raw_media"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            name=op.f("fk_observations_reviewed_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_observations")),
    )
    for column in (
        "visit_id",
        "zone_id",
        "source_transcript_segment_id",
        "source_media_id",
        "review_status",
        "reviewed_by",
    ):
        op.create_index(
            f"ix_observations_{column}", "observations", [column], unique=False
        )

    op.create_table(
        "reports",
        *id_and_timestamps(),
        sa.Column("visit_id", UUID, nullable=False),
        sa.Column("template_id", sa.Text(), nullable=False),
        sa.Column("content", JSONB, server_default="{}", nullable=False),
        sa.Column("rendered_html", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.ForeignKeyConstraint(
            ["visit_id"],
            ["visits.id"],
            name=op.f("fk_reports_visit_id_visits"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
    )
    op.create_index("ix_reports_visit_id", "reports", ["visit_id"], unique=False)
    op.create_index("ix_reports_status", "reports", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("observations")
    op.drop_table("transcript_segments")
    op.drop_table("raw_media")
    op.drop_table("zones")
    op.drop_table("visits")
    op.drop_table("subjects")
    op.drop_table("contacts")
    op.drop_table("professional_profiles")
    op.drop_table("memberships")
    op.drop_table("verticals")
    op.drop_table("workspaces")
    op.drop_table("users")
