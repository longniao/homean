import asyncio
import json
import os
import uuid
from datetime import UTC, datetime

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from alembic import command
from app.core.database_url import create_async_engine_for_url


def _asyncpg_dsn(url: str) -> str:
    return (
        make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)
    )


def _run_alembic(database_url: str, revision: str, *, downgrade: bool = False) -> None:
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        alembic_config = Config("alembic.ini")
        alembic_config.set_main_option("sqlalchemy.url", database_url)
        if downgrade:
            command.downgrade(alembic_config, revision)
        else:
            command.upgrade(alembic_config, revision)
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url


EXPECTED_TABLES = {
    "alembic_version",
    "contacts",
    "memberships",
    "observations",
    "pipeline_runs",
    "professional_profiles",
    "raw_media",
    "reports",
    "report_revisions",
    "report_sends",
    "report_share_links",
    "report_share_views",
    "stripe_webhook_events",
    "subjects",
    "transcript_segments",
    "users",
    "verticals",
    "visits",
    "visit_markers",
    "workspaces",
    "workspace_branding",
    "workspace_report_usage",
    "workspace_subscriptions",
    "zones",
}


async def test_migration_up_from_empty_database(database_url: str) -> None:
    engine = create_async_engine_for_url(database_url)
    try:
        async with engine.connect() as connection:
            schema = await connection.run_sync(inspect_schema)
            revision = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
    finally:
        await engine.dispose()

    assert schema["tables"] == EXPECTED_TABLES
    assert revision == "20260814_0020"
    for table in EXPECTED_TABLES - {"alembic_version"}:
        assert {"id", "created_at", "updated_at"} <= schema["columns"][table]
    assert {
        "source_transcript_segment_id",
        "source_media_id",
        "timestamp_start",
        "timestamp_end",
        "ai_model",
        "prompt_version",
        "confidence",
        "source_type",
        "review_status",
        "reviewed_by",
        "reviewed_at",
        "flags",
    } <= schema["columns"]["observations"]
    assert {
        "visit_id",
        "run_id",
        "step",
        "model",
        "prompt_version",
        "tokens_in",
        "tokens_out",
        "duration_ms",
        "status",
        "error",
    } <= schema["columns"]["pipeline_runs"]
    assert "original_text" in schema["columns"]["transcript_segments"]
    assert "ix_memberships_workspace_id" in schema["indexes"]["memberships"]
    assert "ix_contacts_workspace_id" in schema["indexes"]["contacts"]
    assert "ix_visits_workspace_id" in schema["indexes"]["visits"]
    assert "ix_visits_subject_id" in schema["indexes"]["visits"]
    assert "capture_client_id" in schema["columns"]["visits"]
    assert (
        "uq_visits_workspace_capture_client_id"
        in schema["unique_constraints"]["visits"]
    )
    assert schema["nullable"]["visits"]["subject_id"] is True
    assert "uq_subjects_workspace_id_id" in schema["unique_constraints"]["subjects"]
    assert "fk_visits_subject_id_subjects" not in schema["foreign_keys"]["visits"]
    assert schema["foreign_keys"]["visits"]["fk_visits_workspace_subject_subjects"] == {
        "constrained_columns": ("workspace_id", "subject_id"),
        "referred_table": "subjects",
        "referred_columns": ("workspace_id", "id"),
    }
    assert schema["nullable"]["visits"]["consent_ack"] is False
    assert "token_lookup_hash" in schema["columns"]["report_share_links"]
    assert (
        "ix_report_share_links_token_lookup_hash"
        in schema["indexes"]["report_share_links"]
    )
    assert {"event_id", "event_type", "stripe_created_at"} <= schema["columns"][
        "stripe_webhook_events"
    ]
    assert {"stripe_event_created_at", "stripe_event_type"} <= schema["columns"][
        "workspace_subscriptions"
    ]
    assert "ix_visits_contact_id" in schema["indexes"]["visits"]
    assert "ix_subjects_workspace_id" in schema["indexes"]["subjects"]
    assert "ix_raw_media_status" in schema["indexes"]["raw_media"]
    assert "upload_url_expires_at" in schema["columns"]["raw_media"]
    assert "client_id" in schema["columns"]["raw_media"]
    assert "uq_raw_media_visit_client_id" in schema["unique_constraints"]["raw_media"]
    assert "ix_pipeline_runs_visit_id" in schema["indexes"]["pipeline_runs"]
    assert "ix_observations_visit_id" in schema["indexes"]["observations"]
    assert "ix_transcript_segments_visit_id" in schema["indexes"]["transcript_segments"]
    assert any("sent_to_client" in check for check in schema["visit_checks"])
    assert {
        "visit_id",
        "client_id",
        "created_by",
        "marker_type",
        "timestamp_offset_ms",
    } <= schema["columns"]["visit_markers"]
    assert "ix_visit_markers_visit_id" in schema["indexes"]["visit_markers"]
    assert {
        "workspace_id",
        "report_id",
        "visit_id",
        "edited_by",
        "revision_number",
        "previous_content",
        "new_content",
    } <= schema["columns"]["report_revisions"]
    assert "ix_report_revisions_workspace_id" in schema["indexes"]["report_revisions"]
    assert (
        "uq_report_revisions_report_revision_number"
        in schema["unique_constraints"]["report_revisions"]
    )
    assert {
        "message_id",
        "attempt_count",
        "last_attempt_at",
    } <= schema["columns"]["report_sends"]
    assert "uq_report_sends_message_id" in schema["unique_constraints"]["report_sends"]


async def test_head_enforces_visit_subject_workspace_boundary(
    database_url: str,
) -> None:
    connection = await asyncpg.connect(_asyncpg_dsn(database_url))
    try:
        async with connection.transaction():
            user_a_id, user_b_id = uuid.uuid4(), uuid.uuid4()
            workspace_a_id, workspace_b_id = uuid.uuid4(), uuid.uuid4()
            vertical_id = uuid.uuid4()
            membership_a_id, membership_b_id = uuid.uuid4(), uuid.uuid4()
            profile_a_id, profile_b_id = uuid.uuid4(), uuid.uuid4()
            subject_id = uuid.uuid4()
            visit_a_id, visit_b_id, subjectless_visit_id = (
                uuid.uuid4() for _ in range(3)
            )

            await connection.executemany(
                "INSERT INTO users (id, email, password_hash) VALUES ($1, $2, $3)",
                [
                    (user_a_id, f"{user_a_id}@example.com", "test-hash"),
                    (user_b_id, f"{user_b_id}@example.com", "test-hash"),
                ],
            )
            await connection.executemany(
                "INSERT INTO workspaces (id, name) VALUES ($1, $2)",
                [
                    (workspace_a_id, "Workspace A"),
                    (workspace_b_id, "Workspace B"),
                ],
            )
            await connection.execute(
                """
                INSERT INTO verticals (
                    id, slug, version, display_name, zone_taxonomy,
                    observation_schema, zone_labels, observation_labels,
                    prompt_templates, prompt_version, report_template_id,
                    report_labels
                ) VALUES (
                    $1, $2, 1, 'Real Estate', '[]'::jsonb,
                    '[]'::jsonb, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb,
                    'test', 'test', '{}'::jsonb
                )
                """,
                vertical_id,
                f"real_estate_{vertical_id}",
            )
            await connection.executemany(
                """
                INSERT INTO memberships (id, user_id, workspace_id)
                VALUES ($1, $2, $3)
                """,
                [
                    (membership_a_id, user_a_id, workspace_a_id),
                    (membership_b_id, user_b_id, workspace_b_id),
                ],
            )
            await connection.executemany(
                """
                INSERT INTO professional_profiles (id, membership_id, vertical_id, role)
                VALUES ($1, $2, $3, 'buyers_agent')
                """,
                [
                    (profile_a_id, membership_a_id, vertical_id),
                    (profile_b_id, membership_b_id, vertical_id),
                ],
            )
            await connection.execute(
                """
                INSERT INTO subjects (
                    id, workspace_id, vertical_id, subject_type, display_name
                ) VALUES ($1, $2, $3, 'property', 'Workspace A subject')
                """,
                subject_id,
                workspace_a_id,
                vertical_id,
            )

            await connection.execute(
                """
                INSERT INTO visits (
                    id, workspace_id, subject_id, created_by,
                    professional_profile_id, status
                ) VALUES ($1, $2, $3, $4, $5, 'draft')
                """,
                visit_a_id,
                workspace_a_id,
                subject_id,
                user_a_id,
                profile_a_id,
            )

            with pytest.raises(asyncpg.exceptions.ForeignKeyViolationError):
                async with connection.transaction():
                    await connection.execute(
                        """
                        INSERT INTO visits (
                            id, workspace_id, subject_id, created_by,
                            professional_profile_id, status
                        ) VALUES ($1, $2, $3, $4, $5, 'draft')
                        """,
                        visit_b_id,
                        workspace_b_id,
                        subject_id,
                        user_b_id,
                        profile_b_id,
                    )

            await connection.execute(
                """
                INSERT INTO visits (
                    id, workspace_id, subject_id, created_by,
                    professional_profile_id, status
                ) VALUES ($1, $2, NULL, $3, $4, 'draft')
                """,
                subjectless_visit_id,
                workspace_b_id,
                user_b_id,
                profile_b_id,
            )

            with pytest.raises(asyncpg.exceptions.ForeignKeyViolationError):
                async with connection.transaction():
                    await connection.execute(
                        "UPDATE visits SET workspace_id = $1 WHERE id = $2",
                        workspace_b_id,
                        visit_a_id,
                    )

            assert (
                await connection.fetchval(
                    "SELECT subject_id FROM visits WHERE id = $1",
                    subjectless_visit_id,
                )
                is None
            )
    finally:
        await connection.close()


async def test_migration_0002_backfills_populated_subject_workspaces(
    database_url: str,
) -> None:
    del database_url
    admin_url = os.environ.get(
        "TEST_DATABASE_ADMIN_URL",
        "postgresql+asyncpg://homean:homean@127.0.0.1:55432/postgres",
    )
    database_name = f"homean_migration_{uuid.uuid4().hex}"
    legacy_url = (
        make_url(admin_url)
        .set(database=database_name)
        .render_as_string(hide_password=False)
    )

    admin_connection = await asyncpg.connect(_asyncpg_dsn(admin_url))
    try:
        await admin_connection.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await admin_connection.close()

    user_a_id, user_b_id = uuid.uuid4(), uuid.uuid4()
    workspace_a_id, workspace_b_id = uuid.uuid4(), uuid.uuid4()
    vertical_id = uuid.uuid4()
    membership_a_id, membership_b_id = uuid.uuid4(), uuid.uuid4()
    profile_a_id, profile_b_id = uuid.uuid4(), uuid.uuid4()
    contact_a_id, contact_b_id = uuid.uuid4(), uuid.uuid4()
    subject_id = uuid.uuid4()
    shared_subject_id = uuid.uuid4()
    orphan_subject_id = uuid.uuid4()
    visit_id = uuid.uuid4()
    shared_visit_a_id, shared_visit_b_id = uuid.uuid4(), uuid.uuid4()
    zone_id, media_id, segment_id, observation_id, report_id = (
        uuid.uuid4() for _ in range(5)
    )
    shared_visit_a_at = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
    shared_visit_b_at = datetime(2026, 1, 3, 12, 0, tzinfo=UTC)

    try:
        await asyncio.to_thread(_run_alembic, legacy_url, "20260804_0001")
        connection = await asyncpg.connect(_asyncpg_dsn(legacy_url))
        try:
            await connection.executemany(
                "INSERT INTO users (id, email, password_hash) VALUES ($1, $2, $3)",
                [
                    (user_a_id, "agent-a@example.com", "legacy-hash-a"),
                    (user_b_id, "agent-b@example.com", "legacy-hash-b"),
                ],
            )
            await connection.executemany(
                "INSERT INTO workspaces (id, name) VALUES ($1, $2)",
                [
                    (workspace_a_id, "Agent A workspace"),
                    (workspace_b_id, "Agent B workspace"),
                ],
            )
            await connection.execute(
                """
                INSERT INTO verticals (
                    id, slug, version, display_name, zone_taxonomy,
                    observation_schema, zone_labels, observation_labels,
                    prompt_templates, prompt_version, report_template_id,
                    report_labels
                ) VALUES (
                    $1, 'real_estate', 1, 'Real Estate', '[]'::jsonb,
                    '[]'::jsonb, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb,
                    'test', 'test', '{}'::jsonb
                )
                """,
                vertical_id,
            )
            await connection.executemany(
                """
                INSERT INTO memberships (id, user_id, workspace_id)
                VALUES ($1, $2, $3)
                """,
                [
                    (membership_a_id, user_a_id, workspace_a_id),
                    (membership_b_id, user_b_id, workspace_b_id),
                ],
            )
            await connection.executemany(
                """
                INSERT INTO professional_profiles (id, membership_id, vertical_id, role)
                VALUES ($1, $2, $3, 'buyers_agent')
                """,
                [
                    (profile_a_id, membership_a_id, vertical_id),
                    (profile_b_id, membership_b_id, vertical_id),
                ],
            )
            await connection.executemany(
                """
                INSERT INTO contacts (id, workspace_id, name, contact_info)
                VALUES ($1, $2, $3, '{}'::jsonb)
                """,
                [
                    (contact_a_id, workspace_a_id, "Buyer A"),
                    (contact_b_id, workspace_b_id, "Buyer B"),
                ],
            )
            await connection.executemany(
                """
                INSERT INTO subjects (
                    id, vertical_id, subject_type, display_name, location, attributes
                ) VALUES ($1, $2, 'property', $3, $4, $5::jsonb)
                """,
                [
                    (subject_id, vertical_id, "Single tenant subject", "A", "{}"),
                    (
                        shared_subject_id,
                        vertical_id,
                        "Legacy shared subject",
                        "Shared",
                        '{"beds": 3}',
                    ),
                    (
                        orphan_subject_id,
                        vertical_id,
                        "Unassigned legacy subject",
                        None,
                        "{}",
                    ),
                ],
            )
            await connection.executemany(
                """
                INSERT INTO visits (
                    id, created_at, updated_at, workspace_id, subject_id,
                    created_by, contact_id, professional_profile_id, status
                ) VALUES ($1, $2, $2, $3, $4, $5, $6, $7, 'confirmed')
                """,
                [
                    (
                        visit_id,
                        shared_visit_a_at,
                        workspace_a_id,
                        subject_id,
                        user_a_id,
                        contact_a_id,
                        profile_a_id,
                    ),
                    (
                        shared_visit_a_id,
                        shared_visit_a_at,
                        workspace_a_id,
                        shared_subject_id,
                        user_a_id,
                        contact_a_id,
                        profile_a_id,
                    ),
                    (
                        shared_visit_b_id,
                        shared_visit_b_at,
                        workspace_b_id,
                        shared_subject_id,
                        user_b_id,
                        contact_b_id,
                        profile_b_id,
                    ),
                ],
            )
            await connection.execute(
                """
                INSERT INTO zones (id, visit_id, zone_type)
                VALUES ($1, $2, 'kitchen')
                """,
                zone_id,
                shared_visit_b_id,
            )
            await connection.execute(
                """
                INSERT INTO raw_media (
                    id, visit_id, type, storage_url, timestamp_offset
                )
                VALUES ($1, $2, 'audio', 'legacy/audio.m4a', 4.5)
                """,
                media_id,
                shared_visit_b_id,
            )
            await connection.execute(
                """
                INSERT INTO transcript_segments (
                    id, visit_id, raw_media_id, text, timestamp_start, timestamp_end
                ) VALUES ($1, $2, $3, 'Bright kitchen', 4.5, 6.0)
                """,
                segment_id,
                shared_visit_b_id,
                media_id,
            )
            await connection.execute(
                """
                INSERT INTO observations (
                    id, visit_id, zone_id, category, content, source_type,
                    source_transcript_segment_id, source_media_id, review_status
                ) VALUES (
                    $1, $2, $3, 'pro', 'Bright kitchen', 'ai_generated', $4, $5,
                    'pending'
                )
                """,
                observation_id,
                shared_visit_b_id,
                zone_id,
                segment_id,
                media_id,
            )
            await connection.execute(
                """
                INSERT INTO reports (id, visit_id, template_id, content, status)
                VALUES ($1, $2, 'test', '{}'::jsonb, 'draft')
                """,
                report_id,
                shared_visit_b_id,
            )
        finally:
            await connection.close()

        await asyncio.to_thread(_run_alembic, legacy_url, "20260804_0002")
        connection = await asyncpg.connect(_asyncpg_dsn(legacy_url))
        try:
            subjects = await connection.fetch(
                """
                SELECT id, display_name, workspace_id
                FROM subjects
                ORDER BY display_name, id
                """
            )
            subjects_by_id = {row["id"]: row for row in subjects}
            assert subjects_by_id[subject_id]["workspace_id"] == workspace_a_id
            assert subjects_by_id[shared_subject_id]["workspace_id"] == workspace_a_id

            shared_subjects = [
                row
                for row in subjects
                if row["display_name"] == "Legacy shared subject"
            ]
            assert len(shared_subjects) == 2
            shared_copy = next(
                row for row in shared_subjects if row["workspace_id"] == workspace_b_id
            )
            assert shared_copy["id"] != shared_subject_id

            orphan_row = subjects_by_id[orphan_subject_id]
            assert orphan_row["workspace_id"] not in {
                workspace_a_id,
                workspace_b_id,
            }
            assert (
                await connection.fetchval(
                    "SELECT count(*) FROM memberships WHERE workspace_id = $1",
                    orphan_row["workspace_id"],
                )
                == 0
            )

            visit_subjects = await connection.fetch(
                """
                SELECT visit.id, visit.workspace_id, visit.subject_id,
                       subject.workspace_id AS subject_workspace_id
                FROM visits AS visit
                JOIN subjects AS subject ON subject.id = visit.subject_id
                ORDER BY visit.id
                """
            )
            assert all(
                row["workspace_id"] == row["subject_workspace_id"]
                for row in visit_subjects
            )
            shared_visit_b = next(
                row for row in visit_subjects if row["id"] == shared_visit_b_id
            )
            assert shared_visit_b["subject_id"] == shared_copy["id"]
            assert shared_visit_b["subject_id"] != shared_subject_id

            assert (
                await connection.fetchval(
                    "SELECT count(*) FROM observations WHERE id = $1", observation_id
                )
                == 1
            )
            assert (
                await connection.fetchval(
                    "SELECT count(*) FROM transcript_segments WHERE id = $1", segment_id
                )
                == 1
            )
            media_defaults = await connection.fetchrow(
                "SELECT content_type, status FROM raw_media WHERE id = $1", media_id
            )
            assert media_defaults["content_type"] == "application/octet-stream"
            assert media_defaults["status"] == "pending"

            column = await connection.fetchval(
                """
                SELECT is_nullable
                FROM information_schema.columns
                WHERE table_name = 'subjects' AND column_name = 'workspace_id'
                """
            )
            assert column == "NO"
            assert (
                await connection.fetchval(
                    """
                    SELECT count(*)
                    FROM pg_constraint
                    WHERE conname = 'fk_subjects_workspace_id_workspaces'
                    """
                )
                == 1
            )
            assert (
                await connection.fetchval(
                    """
                    SELECT count(*)
                    FROM pg_indexes
                    WHERE tablename = 'subjects'
                      AND indexname = 'ix_subjects_workspace_id'
                    """
                )
                == 1
            )

            with pytest.raises(asyncpg.exceptions.NotNullViolationError):
                await connection.execute(
                    """
                    INSERT INTO subjects (
                        id, vertical_id, subject_type, display_name, workspace_id
                    ) VALUES ($1, $2, 'property', 'Missing workspace', NULL)
                    """,
                    uuid.uuid4(),
                    vertical_id,
                )
            with pytest.raises(asyncpg.exceptions.ForeignKeyViolationError):
                await connection.execute(
                    """
                    INSERT INTO subjects (
                        id, vertical_id, subject_type, display_name, workspace_id
                    ) VALUES ($1, $2, 'property', 'Unknown workspace', $3)
                    """,
                    uuid.uuid4(),
                    vertical_id,
                    uuid.uuid4(),
                )
        finally:
            await connection.close()
    finally:
        admin_connection = await asyncpg.connect(_asyncpg_dsn(admin_url))
        try:
            await admin_connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                database_name,
            )
            await admin_connection.execute(f'DROP DATABASE "{database_name}"')
        finally:
            await admin_connection.close()


async def test_migration_0013_quarantines_legacy_email_outcomes(
    database_url: str,
) -> None:
    admin_url = os.environ.get(
        "TEST_DATABASE_ADMIN_URL",
        "postgresql+asyncpg://homean:homean@127.0.0.1:55432/postgres",
    )
    database_name = f"homean_migration_{uuid.uuid4().hex}"
    legacy_url = (
        make_url(admin_url)
        .set(database=database_name)
        .render_as_string(hide_password=False)
    )

    admin_connection = await asyncpg.connect(_asyncpg_dsn(admin_url))
    try:
        await admin_connection.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await admin_connection.close()

    try:
        await asyncio.to_thread(_run_alembic, legacy_url, "20260810_0012")
        user_id, workspace_id, vertical_id = (uuid.uuid4() for _ in range(3))
        membership_id, profile_id, subject_id = (uuid.uuid4() for _ in range(3))
        visit_id, report_id, share_link_id = (uuid.uuid4() for _ in range(3))
        pending_id, failed_id, sent_id, link_id = (uuid.uuid4() for _ in range(4))
        created_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

        connection = await asyncpg.connect(_asyncpg_dsn(legacy_url))
        try:
            await connection.execute(
                "INSERT INTO users (id, email, password_hash) VALUES ($1, $2, $3)",
                user_id,
                f"{user_id}@example.com",
                "legacy-hash",
            )
            await connection.execute(
                "INSERT INTO workspaces (id, name) VALUES ($1, 'Legacy workspace')",
                workspace_id,
            )
            await connection.execute(
                """
                INSERT INTO verticals (
                    id, slug, version, display_name, zone_taxonomy,
                    observation_schema, zone_labels, observation_labels,
                    prompt_templates, prompt_version, report_template_id,
                    report_labels
                ) VALUES (
                    $1, 'real_estate', 1, 'Real Estate', '[]'::jsonb,
                    '[]'::jsonb, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb,
                    'test', 'test', '{}'::jsonb
                )
                """,
                vertical_id,
            )
            await connection.execute(
                """
                INSERT INTO memberships (id, user_id, workspace_id)
                VALUES ($1, $2, $3)
                """,
                membership_id,
                user_id,
                workspace_id,
            )
            await connection.execute(
                """
                INSERT INTO professional_profiles (id, membership_id, vertical_id, role)
                VALUES ($1, $2, $3, 'buyers_agent')
                """,
                profile_id,
                membership_id,
                vertical_id,
            )
            await connection.execute(
                """
                INSERT INTO subjects (
                    id, workspace_id, vertical_id, subject_type, display_name
                )
                VALUES ($1, $2, $3, 'property', 'Legacy property')
                """,
                subject_id,
                workspace_id,
                vertical_id,
            )
            await connection.execute(
                """
                INSERT INTO visits (
                    id, workspace_id, subject_id, created_by,
                    professional_profile_id, status
                ) VALUES ($1, $2, $3, $4, $5, 'confirmed')
                """,
                visit_id,
                workspace_id,
                subject_id,
                user_id,
                profile_id,
            )
            await connection.execute(
                """
                INSERT INTO reports (id, visit_id, template_id, status)
                VALUES ($1, $2, 'test', 'confirmed')
                """,
                report_id,
                visit_id,
            )
            await connection.execute(
                """
                INSERT INTO report_share_links (
                    id, workspace_id, report_id, created_by, token,
                    token_lookup_hash
                ) VALUES ($1, $2, $3, $4, 'legacy-token', 'legacy-hash')
                """,
                share_link_id,
                workspace_id,
                report_id,
                user_id,
            )
            for send_id, channel, status, to_email, error in (
                (pending_id, "email", "pending", "pending@example.com", None),
                (failed_id, "email", "failed", "failed@example.com", "old failure"),
                (sent_id, "email", "sent", "sent@example.com", None),
                (link_id, "link_only", "sent", None, None),
            ):
                await connection.execute(
                    """
                    INSERT INTO report_sends (
                        id, created_at, updated_at, workspace_id, visit_id,
                        report_id, share_link_id, sent_by, channel, to_email,
                        status, provider_message_id, error
                    ) VALUES ($1, $2, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    send_id,
                    created_at,
                    workspace_id,
                    visit_id,
                    report_id,
                    share_link_id,
                    user_id,
                    channel,
                    to_email,
                    status,
                    None,
                    error,
                )
        finally:
            await connection.close()

        await asyncio.to_thread(_run_alembic, legacy_url, "head")
        connection = await asyncpg.connect(_asyncpg_dsn(legacy_url))
        try:
            rows = await connection.fetch(
                """
                SELECT id, channel, status, message_id, attempt_count,
                       last_attempt_at, error
                FROM report_sends
                ORDER BY id
                """
            )
        finally:
            await connection.close()

        by_id = {row["id"]: row for row in rows}
        for legacy_id in (pending_id, failed_id):
            assert by_id[legacy_id]["status"] == "outcome_unknown"
            assert by_id[legacy_id]["message_id"] is None
            assert by_id[legacy_id]["attempt_count"] == 1
            assert by_id[legacy_id]["last_attempt_at"] == created_at
            assert "quarantined during upgrade" in by_id[legacy_id]["error"]

        assert by_id[sent_id]["status"] == "sent"
        assert by_id[sent_id]["message_id"] == (f"<kawu-report-{sent_id}@kawu.local>")
        assert by_id[link_id]["message_id"] is None
        assert by_id[link_id]["attempt_count"] == 0

        await asyncio.to_thread(
            _run_alembic,
            legacy_url,
            "20260810_0013",
            downgrade=True,
        )
        connection = await asyncpg.connect(_asyncpg_dsn(legacy_url))
        try:
            constraints = await connection.fetch(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'visits'::regclass
                  AND contype = 'f'
                """
            )
            constraint_names = {row["conname"] for row in constraints}
            assert "fk_visits_subject_id_subjects" in constraint_names
            assert "fk_visits_workspace_subject_subjects" not in constraint_names
            assert (
                await connection.fetchval(
                    """
                    SELECT count(*)
                    FROM pg_constraint
                    WHERE conrelid = 'subjects'::regclass
                      AND conname = 'uq_subjects_workspace_id_id'
                    """
                )
                == 0
            )
            assert (
                await connection.fetchval(
                    """
                    SELECT is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'visits' AND column_name = 'subject_id'
                    """
                )
                == "YES"
            )
        finally:
            await connection.close()
    finally:
        admin_connection = await asyncpg.connect(_asyncpg_dsn(admin_url))
        try:
            await admin_connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                database_name,
            )
            await admin_connection.execute(f'DROP DATABASE "{database_name}"')
        finally:
            await admin_connection.close()


async def test_migration_0015_backfills_populated_report_revisions(
    database_url: str,
) -> None:
    """Backfill repeated-state report histories without reconstructing a graph."""

    del database_url
    admin_url = os.environ.get(
        "TEST_DATABASE_ADMIN_URL",
        "postgresql+asyncpg://homean:homean@127.0.0.1:55432/postgres",
    )
    database_name = f"homean_migration_{uuid.uuid4().hex}"
    legacy_url = (
        make_url(admin_url)
        .set(database=database_name)
        .render_as_string(hide_password=False)
    )

    admin_connection = await asyncpg.connect(_asyncpg_dsn(admin_url))
    try:
        await admin_connection.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await admin_connection.close()

    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    workspace_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    vertical_id = uuid.UUID("00000000-0000-0000-0000-000000000003")
    membership_id = uuid.UUID("00000000-0000-0000-0000-000000000004")
    profile_id = uuid.UUID("00000000-0000-0000-0000-000000000005")
    subject_id = uuid.UUID("00000000-0000-0000-0000-000000000006")
    visit_id = uuid.UUID("00000000-0000-0000-0000-000000000007")
    report_id = uuid.UUID("00000000-0000-0000-0000-000000000008")
    revision_rows = [
        (
            uuid.UUID("00000000-0000-0000-0000-000000000101"),
            datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            {"state": "A"},
            {"state": "B"},
        ),
        (
            uuid.UUID("00000000-0000-0000-0000-000000000102"),
            datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            {"state": "B"},
            {"state": "A"},
        ),
        (
            uuid.UUID("00000000-0000-0000-0000-000000000103"),
            datetime(2026, 1, 2, 12, 0, tzinfo=UTC),
            {"state": "A"},
            {"state": "C"},
        ),
        (
            uuid.UUID("00000000-0000-0000-0000-000000000104"),
            datetime(2026, 1, 3, 12, 0, tzinfo=UTC),
            {"state": "C"},
            {"state": "D"},
        ),
    ]

    try:
        await asyncio.to_thread(_run_alembic, legacy_url, "20260811_0014")
        connection = await asyncpg.connect(_asyncpg_dsn(legacy_url))
        try:
            await connection.execute(
                "INSERT INTO users (id, email, password_hash) VALUES ($1, $2, $3)",
                user_id,
                "legacy-revisions@example.com",
                "legacy-hash",
            )
            await connection.execute(
                "INSERT INTO workspaces (id, name) VALUES ($1, $2)",
                workspace_id,
                "Legacy revisions workspace",
            )
            await connection.execute(
                """
                INSERT INTO verticals (
                    id, slug, version, display_name, zone_taxonomy,
                    observation_schema, zone_labels, observation_labels,
                    prompt_templates, prompt_version, report_template_id,
                    report_labels
                ) VALUES (
                    $1, 'real_estate', 1, 'Real Estate', '[]'::jsonb,
                    '[]'::jsonb, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb,
                    'test', 'test', '{}'::jsonb
                )
                """,
                vertical_id,
            )
            await connection.execute(
                """
                INSERT INTO memberships (id, user_id, workspace_id)
                VALUES ($1, $2, $3)
                """,
                membership_id,
                user_id,
                workspace_id,
            )
            await connection.execute(
                """
                INSERT INTO professional_profiles (id, membership_id, vertical_id, role)
                VALUES ($1, $2, $3, 'buyers_agent')
                """,
                profile_id,
                membership_id,
                vertical_id,
            )
            await connection.execute(
                """
                INSERT INTO subjects (
                    id, workspace_id, vertical_id, subject_type, display_name
                ) VALUES ($1, $2, $3, 'property', 'Legacy report subject')
                """,
                subject_id,
                workspace_id,
                vertical_id,
            )
            await connection.execute(
                """
                INSERT INTO visits (
                    id, workspace_id, subject_id, created_by,
                    professional_profile_id, status
                ) VALUES ($1, $2, $3, $4, $5, 'draft')
                """,
                visit_id,
                workspace_id,
                subject_id,
                user_id,
                profile_id,
            )
            await connection.execute(
                """
                INSERT INTO reports (id, visit_id, template_id, content, status)
                VALUES ($1, $2, 'test', '{"state": "A"}'::jsonb, 'draft')
                """,
                report_id,
                visit_id,
            )
            await connection.executemany(
                """
                INSERT INTO report_revisions (
                    id, created_at, updated_at, workspace_id, report_id,
                    visit_id, edited_by, previous_content, new_content
                ) VALUES ($1, $2, $2, $3, $4, $5, $6, $7, $8)
                """,
                [
                    (
                        revision_id,
                        created_at,
                        workspace_id,
                        report_id,
                        visit_id,
                        user_id,
                        json.dumps(previous_content),
                        json.dumps(new_content),
                    )
                    for (
                        revision_id,
                        created_at,
                        previous_content,
                        new_content,
                    ) in revision_rows
                ],
            )
            snapshots_before = await connection.fetch(
                """
                SELECT id, created_at, updated_at, workspace_id, report_id,
                       visit_id, edited_by, previous_content, new_content
                FROM report_revisions
                ORDER BY created_at ASC, id ASC
                """
            )
        finally:
            await connection.close()

        await asyncio.to_thread(_run_alembic, legacy_url, "20260811_0015")
        connection = await asyncpg.connect(_asyncpg_dsn(legacy_url))
        try:
            revisions = await connection.fetch(
                """
                SELECT id, created_at, updated_at, workspace_id, report_id,
                       visit_id, edited_by, revision_number, previous_content,
                       new_content
                FROM report_revisions
                ORDER BY revision_number ASC
                """
            )
            assert [row["revision_number"] for row in revisions] == [1, 2, 3, 4]
            assert [row["id"] for row in revisions] == [
                revision_id for revision_id, *_ in revision_rows
            ]
            assert [
                (
                    row["id"],
                    row["created_at"],
                    row["updated_at"],
                    row["workspace_id"],
                    row["report_id"],
                    row["visit_id"],
                    row["edited_by"],
                    row["previous_content"],
                    row["new_content"],
                )
                for row in revisions
            ] == [tuple(row) for row in snapshots_before]

            assert (
                await connection.fetchval(
                    """
                    SELECT is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'report_revisions'
                      AND column_name = 'revision_number'
                    """
                )
                == "NO"
            )
            constraints = await connection.fetch(
                """
                SELECT conname, contype::text AS contype,
                       pg_get_constraintdef(oid) AS definition
                FROM pg_constraint
                WHERE conrelid = 'report_revisions'::regclass
                  AND conname IN (
                      'ck_report_revisions_report_revision_number_positive',
                      'uq_report_revisions_report_revision_number'
                  )
                """
            )
            constraints_by_name = {row["conname"]: row for row in constraints}
            assert (
                constraints_by_name[
                    "ck_report_revisions_report_revision_number_positive"
                ]["contype"]
                == "c"
            )
            assert (
                "revision_number > 0"
                in constraints_by_name[
                    "ck_report_revisions_report_revision_number_positive"
                ]["definition"]
            )
            assert (
                constraints_by_name["uq_report_revisions_report_revision_number"][
                    "contype"
                ]
                == "u"
            )
            assert (
                "UNIQUE (report_id, revision_number)"
                in constraints_by_name["uq_report_revisions_report_revision_number"][
                    "definition"
                ]
            )
            assert (
                await connection.fetchval(
                    """
                    SELECT count(*)
                    FROM pg_indexes
                    WHERE tablename = 'report_revisions'
                      AND indexname = 'ix_report_revisions_report_created_id'
                    """
                )
                == 0
            )

            revision_insert = """
                INSERT INTO report_revisions (
                    id, workspace_id, report_id, visit_id, edited_by,
                    revision_number, previous_content, new_content
                ) VALUES ($1, $2, $3, $4, $5, $6, '{}'::jsonb, '{}'::jsonb)
            """
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                async with connection.transaction():
                    await connection.execute(
                        revision_insert,
                        uuid.UUID("00000000-0000-0000-0000-000000000105"),
                        workspace_id,
                        report_id,
                        visit_id,
                        user_id,
                        0,
                    )
            with pytest.raises(asyncpg.exceptions.NotNullViolationError):
                async with connection.transaction():
                    await connection.execute(
                        revision_insert,
                        uuid.UUID("00000000-0000-0000-0000-000000000107"),
                        workspace_id,
                        report_id,
                        visit_id,
                        user_id,
                        None,
                    )
            with pytest.raises(asyncpg.exceptions.UniqueViolationError):
                async with connection.transaction():
                    await connection.execute(
                        revision_insert,
                        uuid.UUID("00000000-0000-0000-0000-000000000106"),
                        workspace_id,
                        report_id,
                        visit_id,
                        user_id,
                        1,
                    )
        finally:
            await connection.close()

        await asyncio.to_thread(
            _run_alembic,
            legacy_url,
            "20260811_0014",
            downgrade=True,
        )
        connection = await asyncpg.connect(_asyncpg_dsn(legacy_url))
        try:
            assert (
                await connection.fetchval(
                    """
                    SELECT count(*)
                    FROM information_schema.columns
                    WHERE table_name = 'report_revisions'
                      AND column_name = 'revision_number'
                    """
                )
                == 0
            )
            assert (
                await connection.fetchval(
                    """
                    SELECT count(*)
                    FROM pg_indexes
                    WHERE tablename = 'report_revisions'
                      AND indexname = 'ix_report_revisions_report_created_id'
                    """
                )
                == 1
            )
        finally:
            await connection.close()
    finally:
        admin_connection = await asyncpg.connect(_asyncpg_dsn(admin_url))
        try:
            await admin_connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                database_name,
            )
            await admin_connection.execute(f'DROP DATABASE "{database_name}"')
        finally:
            await admin_connection.close()


def inspect_schema(sync_connection):  # type: ignore[no-untyped-def]
    inspector = inspect(sync_connection)
    tables = set(inspector.get_table_names())
    inspected_tables = tables - {"alembic_version"}
    return {
        "tables": tables,
        "columns": {
            table: {column["name"] for column in inspector.get_columns(table)}
            for table in inspected_tables
        },
        "nullable": {
            table: {
                column["name"]: column["nullable"]
                for column in inspector.get_columns(table)
            }
            for table in inspected_tables
        },
        "indexes": {
            table: {index["name"] for index in inspector.get_indexes(table)}
            for table in inspected_tables
        },
        "unique_constraints": {
            table: {
                constraint["name"]
                for constraint in inspector.get_unique_constraints(table)
            }
            for table in inspected_tables
        },
        "foreign_keys": {
            table: {
                constraint["name"]: {
                    "constrained_columns": tuple(constraint["constrained_columns"]),
                    "referred_table": constraint["referred_table"],
                    "referred_columns": tuple(constraint["referred_columns"]),
                }
                for constraint in inspector.get_foreign_keys(table)
            }
            for table in inspected_tables
        },
        "visit_checks": [
            constraint["sqltext"]
            for constraint in inspector.get_check_constraints("visits")
        ],
    }
