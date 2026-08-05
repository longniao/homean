from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

EXPECTED_TABLES = {
    "alembic_version",
    "contacts",
    "memberships",
    "observations",
    "pipeline_runs",
    "professional_profiles",
    "raw_media",
    "reports",
    "subjects",
    "transcript_segments",
    "users",
    "verticals",
    "visits",
    "workspaces",
    "zones",
}


async def test_migration_up_from_empty_database(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            schema = await connection.run_sync(inspect_schema)
            revision = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
    finally:
        await engine.dispose()

    assert schema["tables"] == EXPECTED_TABLES
    assert revision == "20260804_0003"
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
    assert "ix_memberships_workspace_id" in schema["indexes"]["memberships"]
    assert "ix_contacts_workspace_id" in schema["indexes"]["contacts"]
    assert "ix_visits_workspace_id" in schema["indexes"]["visits"]
    assert "ix_visits_subject_id" in schema["indexes"]["visits"]
    assert "ix_visits_contact_id" in schema["indexes"]["visits"]
    assert "ix_subjects_workspace_id" in schema["indexes"]["subjects"]
    assert "ix_raw_media_status" in schema["indexes"]["raw_media"]
    assert "ix_pipeline_runs_visit_id" in schema["indexes"]["pipeline_runs"]
    assert "ix_observations_visit_id" in schema["indexes"]["observations"]
    assert "ix_transcript_segments_visit_id" in schema["indexes"]["transcript_segments"]
    assert any("sent_to_client" in check for check in schema["visit_checks"])


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
        "indexes": {
            table: {index["name"] for index in inspector.get_indexes(table)}
            for table in inspected_tables
        },
        "visit_checks": [
            constraint["sqltext"]
            for constraint in inspector.get_check_constraints("visits")
        ],
    }
