"""Add workspace capture fields.

Revision ID: 20260804_0002
Revises: 20260804_0001
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260804_0002"
down_revision: str | None = "20260804_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _backfill_subject_workspaces(connection: sa.Connection) -> None:
    """Assign every legacy subject to exactly one tenant-owned subject row.

    Revision 0001 allowed one subject to be referenced by visits in multiple
    workspaces and did not require a subject to have a visit at all.  The
    canonical subject keeps its existing id and is assigned to the workspace
    of its earliest visit (created_at, then id).  Additional workspace uses
    receive copies, and their visits are rewired to those copies.  Orphaned
    subjects are put in a new workspace with no membership, so they cannot be
    exposed to an existing tenant based on an arbitrary ownership guess.
    """
    connection.execute(
        sa.text(
            """
            CREATE TEMP TABLE _legacy_subject_workspace_map (
                legacy_subject_id UUID NOT NULL,
                workspace_id UUID NOT NULL,
                subject_id UUID NOT NULL,
                is_canonical BOOLEAN NOT NULL,
                PRIMARY KEY (legacy_subject_id, workspace_id),
                UNIQUE (subject_id)
            ) ON COMMIT DROP
            """
        )
    )
    connection.execute(
        sa.text(
            """
            WITH first_visit_by_workspace AS (
                SELECT DISTINCT ON (v.subject_id, v.workspace_id)
                    v.subject_id AS legacy_subject_id,
                    v.workspace_id,
                    v.created_at AS first_visit_at,
                    v.id AS first_visit_id
                FROM visits AS v
                WHERE v.subject_id IS NOT NULL
                ORDER BY v.subject_id, v.workspace_id, v.created_at, v.id
            ),
            ranked_workspaces AS (
                SELECT
                    legacy_subject_id,
                    workspace_id,
                    row_number() OVER (
                        PARTITION BY legacy_subject_id
                        ORDER BY first_visit_at, first_visit_id, workspace_id
                    ) AS workspace_rank
                FROM first_visit_by_workspace
            )
            INSERT INTO _legacy_subject_workspace_map (
                legacy_subject_id,
                workspace_id,
                subject_id,
                is_canonical
            )
            SELECT
                legacy_subject_id,
                workspace_id,
                CASE
                    WHEN workspace_rank = 1 THEN legacy_subject_id
                    ELSE gen_random_uuid()
                END,
                workspace_rank = 1
            FROM ranked_workspaces
            """
        )
    )

    quarantine_workspace_id = connection.execute(
        sa.text(
            """
            INSERT INTO workspaces (name, language)
            SELECT 'Legacy subject quarantine (20260804_0002)', 'en'
            WHERE EXISTS (
                SELECT 1
                FROM subjects AS s
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM visits AS v
                    WHERE v.subject_id = s.id
                )
            )
            RETURNING id
            """
        )
    ).scalar_one_or_none()
    if quarantine_workspace_id is not None:
        connection.execute(
            sa.text(
                """
                INSERT INTO _legacy_subject_workspace_map (
                    legacy_subject_id,
                    workspace_id,
                    subject_id,
                    is_canonical
                )
                SELECT s.id, :workspace_id, s.id, TRUE
                FROM subjects AS s
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM visits AS v
                    WHERE v.subject_id = s.id
                )
                """
            ),
            {"workspace_id": quarantine_workspace_id},
        )

    connection.execute(
        sa.text(
            """
            INSERT INTO subjects (
                id,
                created_at,
                updated_at,
                workspace_id,
                vertical_id,
                subject_type,
                display_name,
                location,
                attributes
            )
            SELECT
                mapping.subject_id,
                subject.created_at,
                subject.updated_at,
                mapping.workspace_id,
                subject.vertical_id,
                subject.subject_type,
                subject.display_name,
                subject.location,
                subject.attributes
            FROM _legacy_subject_workspace_map AS mapping
            JOIN subjects AS subject
                ON subject.id = mapping.legacy_subject_id
            WHERE mapping.subject_id <> mapping.legacy_subject_id
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE subjects AS subject
            SET workspace_id = mapping.workspace_id
            FROM _legacy_subject_workspace_map AS mapping
            WHERE mapping.subject_id = subject.id
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE visits AS visit
            SET subject_id = mapping.subject_id
            FROM _legacy_subject_workspace_map AS mapping
            WHERE mapping.legacy_subject_id = visit.subject_id
              AND mapping.workspace_id = visit.workspace_id
              AND mapping.subject_id <> visit.subject_id
            """
        )
    )

    unassigned_subjects = connection.execute(
        sa.text("SELECT count(*) FROM subjects WHERE workspace_id IS NULL")
    ).scalar_one()
    if unassigned_subjects:
        raise RuntimeError(
            "0002 subject workspace backfill left subjects without a workspace"
        )

    cross_workspace_visits = connection.execute(
        sa.text(
            """
            SELECT count(*)
            FROM visits AS visit
            JOIN subjects AS subject ON subject.id = visit.subject_id
            WHERE visit.workspace_id <> subject.workspace_id
            """
        )
    ).scalar_one()
    if cross_workspace_visits:
        raise RuntimeError(
            "0002 subject workspace backfill left cross-workspace visit references"
        )


def upgrade() -> None:
    op.add_column("contacts", sa.Column("email", sa.Text(), nullable=True))
    op.add_column("contacts", sa.Column("phone", sa.Text(), nullable=True))
    op.add_column("contacts", sa.Column("notes", sa.Text(), nullable=True))

    op.add_column("subjects", sa.Column("workspace_id", UUID, nullable=True))
    _backfill_subject_workspaces(op.get_bind())
    op.alter_column(
        "subjects",
        "workspace_id",
        existing_type=UUID,
        nullable=False,
    )
    op.create_foreign_key(
        op.f("fk_subjects_workspace_id_workspaces"),
        "subjects",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_subjects_workspace_id", "subjects", ["workspace_id"], unique=False
    )

    op.add_column(
        "visits",
        sa.Column(
            "processing_status",
            sa.Text(),
            server_default="not_started",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_visits_processing_status",
        "visits",
        ["processing_status"],
        unique=False,
    )

    op.add_column(
        "raw_media",
        sa.Column(
            "content_type",
            sa.Text(),
            server_default="application/octet-stream",
            nullable=False,
        ),
    )
    op.alter_column("raw_media", "content_type", server_default=None)
    op.add_column(
        "raw_media",
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
    )
    op.add_column("raw_media", sa.Column("size_bytes", sa.BigInteger(), nullable=True))
    op.create_index("ix_raw_media_status", "raw_media", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_raw_media_status", table_name="raw_media")
    op.drop_column("raw_media", "size_bytes")
    op.drop_column("raw_media", "status")
    op.drop_column("raw_media", "content_type")

    op.drop_index("ix_visits_processing_status", table_name="visits")
    op.drop_column("visits", "processing_status")

    op.drop_index("ix_subjects_workspace_id", table_name="subjects")
    op.drop_constraint(
        op.f("fk_subjects_workspace_id_workspaces"),
        "subjects",
        type_="foreignkey",
    )
    op.drop_column("subjects", "workspace_id")

    op.drop_column("contacts", "notes")
    op.drop_column("contacts", "phone")
    op.drop_column("contacts", "email")
