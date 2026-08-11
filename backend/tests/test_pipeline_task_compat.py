import pytest


@pytest.fixture
def pipeline_modules(monkeypatch):  # type: ignore[no-untyped-def]
    for key, value in {
        "DATABASE_URL": "postgresql+asyncpg://kawu:kawu@localhost/kawu",
        "REDIS_URL": "redis://localhost/0",
        "S3_ENDPOINT_URL": "http://localhost:9000",
        "S3_ACCESS_KEY": "access",
        "S3_SECRET_KEY": "secret",
        "S3_BUCKET": "bucket",
        "JWT_SECRET": "a-sufficiently-long-test-secret",
    }.items():
        monkeypatch.setenv(key, value)

    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.pipeline import tasks
    from app.pipeline.celery_app import celery_app

    return tasks, celery_app


def test_homean_pipeline_tasks_keep_legacy_celery_aliases(pipeline_modules) -> None:  # type: ignore[no-untyped-def]
    _, celery_app = pipeline_modules
    registered = celery_app.tasks
    for step in (
        "transcribe",
        "detect_zones",
        "extract_observations",
        "generate_report",
    ):
        assert f"homean.pipeline.{step}" in registered
        assert f"kawu.pipeline.{step}" in registered


def test_legacy_task_alias_executes_the_same_pipeline_step(
    monkeypatch, pipeline_modules
) -> None:  # type: ignore[no-untyped-def]
    tasks, _ = pipeline_modules
    calls: list[tuple[str, str, object]] = []

    def fake_run(workspace_id: str, visit_id: str, step: object) -> None:
        calls.append((workspace_id, visit_id, step))

    monkeypatch.setattr(tasks, "_run", fake_run)
    tasks.legacy_generate_visit_report.run("workspace-id", "visit-id")

    assert calls == [("workspace-id", "visit-id", tasks.PipelineStep.REPORT_GENERATION)]
