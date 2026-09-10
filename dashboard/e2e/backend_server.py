"""Run the real API with its fake external providers for Playwright."""

import asyncio
import os
import sys
import uuid
from pathlib import Path

import asyncpg
import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)


def render_url(url: str, database: str) -> str:
    return make_url(url).set(database=database).render_as_string(hide_password=False)


def asyncpg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def migrate(database_url: str) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


async def main() -> None:
    admin_url = os.environ.get(
        "TEST_DATABASE_ADMIN_URL",
        "postgresql+asyncpg://homean:homean@127.0.0.1:55432/postgres",
    )
    database_name = os.environ.get(
        "HOMEAN_E2E_DATABASE", f"homean_e2e_{uuid.uuid4().hex}"
    )
    database_url = render_url(admin_url, database_name)
    admin = await asyncpg.connect(asyncpg_dsn(admin_url))
    try:
        await admin.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await admin.close()

    os.environ.update(
        {
            "DATABASE_URL": database_url,
            "REDIS_URL": "redis://127.0.0.1:6379/0",
            "S3_ENDPOINT_URL": "http://127.0.0.1:9000",
            "S3_ACCESS_KEY": "e2e-access-key",
            "S3_SECRET_KEY": "e2e-secret-key",
            "S3_BUCKET": "homean-e2e",
            "JWT_SECRET": "e2e-jwt-secret-with-sufficient-length",
            "APP_ENV": "test",
            "PUBLIC_BASE_URL": "http://127.0.0.1:8001",
            "RATE_LIMIT_KEY_PREFIX": f"homean:e2e:{database_name}",
        }
    )
    await asyncio.to_thread(migrate, database_url)

    from app.api.dependencies import (
        get_email_provider,
        get_pipeline_enqueuer,
        get_storage_provider,
    )
    from app.core.config import get_settings
    from app.core.database import dispose_database
    from app.email import FakeEmailProvider
    from app.main import app
    from app.pipeline import FakePipelineEnqueuer
    from app.storage import FakeStorageProvider
    from app.storage.provider import StoredObject

    class UploadedStorage(FakeStorageProvider):
        async def head_object(self, object_key: str) -> StoredObject:
            del object_key
            return StoredObject(size_bytes=10, content_type="audio/mp4")

    get_settings.cache_clear()
    app.dependency_overrides[get_storage_provider] = UploadedStorage
    from app.core.database import get_session_factory
    from app.core.pipeline_config import PipelineStep
    from app.pipeline import FakeLLMClient, FakeTranscriptionProvider
    from tests.test_pipeline import (
        observation_fixture,
        pipeline_service,
        report_fixture,
        zone_fixture,
    )

    class InlinePipeline(FakePipelineEnqueuer):
        async def enqueue(
            self, visit_id, workspace_id, start_step=PipelineStep.TRANSCRIBE
        ):
            async with get_session_factory()() as session:
                service = pipeline_service(
                    session,
                    UploadedStorage(),
                    FakeTranscriptionProvider(),
                    FakeLLMClient([zone_fixture, observation_fixture, report_fixture]),
                )
                for step in list(PipelineStep)[list(PipelineStep).index(start_step) :]:
                    await service.run_step(workspace_id, visit_id, step)

    app.dependency_overrides[get_pipeline_enqueuer] = InlinePipeline
    app.dependency_overrides[get_email_provider] = FakeEmailProvider
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="warning")
    )
    try:
        await server.serve()
    finally:
        app.dependency_overrides.clear()
        await dispose_database()
        admin = await asyncpg.connect(asyncpg_dsn(admin_url))
        try:
            await admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                database_name,
            )
            await admin.execute(f'DROP DATABASE "{database_name}"')
        finally:
            await admin.close()


if __name__ == "__main__":
    asyncio.run(main())
