"""Enforce workspace ownership for visit subjects.

Revision ID: 20260811_0014
Revises: 20260810_0013
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260811_0014"
down_revision: str | None = "20260810_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUBJECT_WORKSPACE_KEY = "uq_subjects_workspace_id_id"
OLD_VISIT_SUBJECT_FK = "fk_visits_subject_id_subjects"
VISIT_SUBJECT_WORKSPACE_FK = "fk_visits_workspace_subject_subjects"


def _assert_subject_workspace_boundary(connection: sa.Connection) -> None:
    violating_rows = connection.execute(
        sa.text(
            """
            SELECT count(*)
            FROM visits AS visit
            LEFT JOIN subjects AS subject ON subject.id = visit.subject_id
            WHERE visit.subject_id IS NOT NULL
              AND (
                  subject.id IS NULL
                  OR visit.workspace_id IS DISTINCT FROM subject.workspace_id
              )
            """
        )
    ).scalar_one()
    if violating_rows:
        raise RuntimeError(
            "Cannot add visit subject workspace enforcement: "
            f"{violating_rows} existing visit reference(s) cross a workspace "
            "boundary or reference a missing subject"
        )


def upgrade() -> None:
    connection = op.get_bind()
    _assert_subject_workspace_boundary(connection)

    # A composite foreign key needs a matching unique key on the referenced
    # columns.  The subject id remains globally unique; this key exists for
    # PostgreSQL's composite-FK requirements and makes the tenant boundary
    # enforceable by the database.
    op.create_unique_constraint(
        SUBJECT_WORKSPACE_KEY,
        "subjects",
        ["workspace_id", "id"],
    )
    op.create_foreign_key(
        VISIT_SUBJECT_WORKSPACE_FK,
        "visits",
        "subjects",
        ["workspace_id", "subject_id"],
        ["workspace_id", "id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(OLD_VISIT_SUBJECT_FK, "visits", type_="foreignkey")


def downgrade() -> None:
    op.drop_constraint(
        VISIT_SUBJECT_WORKSPACE_FK,
        "visits",
        type_="foreignkey",
    )
    op.drop_constraint(SUBJECT_WORKSPACE_KEY, "subjects", type_="unique")
    op.create_foreign_key(
        OLD_VISIT_SUBJECT_FK,
        "visits",
        "subjects",
        ["subject_id"],
        ["id"],
        ondelete="RESTRICT",
    )
