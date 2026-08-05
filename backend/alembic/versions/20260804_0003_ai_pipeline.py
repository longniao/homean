"""Add durable AI pipeline state and evidence metadata.

Revision ID: 20260804_0003
Revises: 20260804_0002
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260804_0003"
down_revision: str | None = "20260804_0002"
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
    op.add_column("visits", sa.Column("processing_failed_step", sa.Text()))
    op.add_column("visits", sa.Column("processing_error", sa.Text()))
    op.add_column("visits", sa.Column("processing_run_id", UUID, nullable=True))

    op.add_column(
        "transcript_segments", sa.Column("confidence", sa.Float(), nullable=True)
    )

    op.add_column(
        "zones", sa.Column("start_transcript_segment_id", UUID, nullable=True)
    )
    op.add_column("zones", sa.Column("end_transcript_segment_id", UUID, nullable=True))
    op.add_column(
        "zones",
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_foreign_key(
        op.f("fk_zones_start_transcript_segment_id_transcript_segments"),
        "zones",
        "transcript_segments",
        ["start_transcript_segment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_zones_end_transcript_segment_id_transcript_segments"),
        "zones",
        "transcript_segments",
        ["end_transcript_segment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_zones_start_transcript_segment_id",
        "zones",
        ["start_transcript_segment_id"],
    )
    op.create_index(
        "ix_zones_end_transcript_segment_id",
        "zones",
        ["end_transcript_segment_id"],
    )

    op.add_column(
        "observations",
        sa.Column("flags", JSONB, server_default="{}", nullable=False),
    )

    op.create_table(
        "pipeline_runs",
        *id_and_timestamps(),
        sa.Column("visit_id", UUID, nullable=False),
        sa.Column("run_id", UUID, nullable=False),
        sa.Column("step", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tokens_out", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["visit_id"],
            ["visits.id"],
            name=op.f("fk_pipeline_runs_visit_id_visits"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipeline_runs")),
    )
    op.create_index("ix_pipeline_runs_visit_id", "pipeline_runs", ["visit_id"])
    op.create_index("ix_pipeline_runs_run_id", "pipeline_runs", ["run_id"])
    op.create_index("ix_pipeline_runs_step", "pipeline_runs", ["step"])
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_runs_status", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_step", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_run_id", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_visit_id", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")

    op.drop_column("observations", "flags")

    op.drop_index("ix_zones_end_transcript_segment_id", table_name="zones")
    op.drop_index("ix_zones_start_transcript_segment_id", table_name="zones")
    op.drop_constraint(
        op.f("fk_zones_end_transcript_segment_id_transcript_segments"),
        "zones",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_zones_start_transcript_segment_id_transcript_segments"),
        "zones",
        type_="foreignkey",
    )
    op.drop_column("zones", "end_transcript_segment_id")
    op.drop_column("zones", "start_transcript_segment_id")
    op.drop_column("zones", "position")

    op.drop_column("transcript_segments", "confidence")
    op.drop_column("visits", "processing_error")
    op.drop_column("visits", "processing_failed_step")
    op.drop_column("visits", "processing_run_id")
