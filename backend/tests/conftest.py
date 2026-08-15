import asyncio
import os
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import get_settings
from app.core.database import dispose_database, get_session_factory
from app.email import FakeEmailProvider
from app.pipeline import FakePipelineEnqueuer
from app.services.renderer import ReportRenderer
from app.storage import FakeStorageProvider
from app.verticals import VerticalConfigService

# Set this during conftest import, before test modules are collected. Some
# tests import the FastAPI app lazily in their test body, while others may do
# so earlier; both cases must receive the same isolated namespace regardless of
# test ordering.
_TEST_RATE_LIMIT_KEY_PREFIX = f"homean:test:{uuid.uuid4().hex}"
os.environ["RATE_LIMIT_KEY_PREFIX"] = _TEST_RATE_LIMIT_KEY_PREFIX
# Every test shares one client address, so the production auth limit is a
# whole-suite budget rather than a per-test one, and adding auth tests
# eventually starves unrelated ones of sign-ups. The limiter itself is covered
# in test_m7_security.py, which configures its own limit explicitly.
os.environ.setdefault("AUTH_RATE_LIMIT", "10000")


class FakeReportRenderer(ReportRenderer):
    async def render_pdf(self, html: str) -> bytes:
        return b"%PDF-1.7\n" + html.encode("utf-8")[:100]


def _render_url(url: str, database: str) -> str:
    return make_url(url).set(database=database).render_as_string(hide_password=False)


def _asyncpg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def _run_migrations(database_url: str) -> None:
    os.environ["DATABASE_URL"] = database_url
    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_config, "head")
    command.check(alembic_config)


async def _clear_redis_namespace(redis_url: str, key_prefix: str) -> None:
    """Remove only this test session's rate-limit keys from Redis.

    Tests use a unique key prefix, so cleanup cannot affect a running API or
    another pytest process that shares the Redis service. Redis is optional in
    the test environment because the middleware has a local fallback; cleanup
    therefore deliberately ignores connection errors.
    """

    redis = Redis.from_url(redis_url, decode_responses=True)
    try:
        keys = [key async for key in redis.scan_iter(match=f"{key_prefix}:*")]
        if keys:
            await redis.delete(*keys)
    except Exception:
        pass
    finally:
        await redis.aclose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def database_url() -> AsyncIterator[str]:
    admin_url = os.environ.get(
        "TEST_DATABASE_ADMIN_URL",
        "postgresql+asyncpg://homean:homean@127.0.0.1:55432/postgres",
    )
    database_name = f"homean_test_{uuid.uuid4().hex}"
    database_url = _render_url(admin_url, database_name)
    redis_url = os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/0")
    rate_limit_key_prefix = _TEST_RATE_LIMIT_KEY_PREFIX

    admin_connection = await asyncpg.connect(_asyncpg_dsn(admin_url))
    try:
        await admin_connection.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await admin_connection.close()

    os.environ.update(
        {
            "DATABASE_URL": database_url,
            "REDIS_URL": redis_url,
            "RATE_LIMIT_KEY_PREFIX": rate_limit_key_prefix,
            "S3_ENDPOINT_URL": "http://127.0.0.1:9000",
            "S3_ACCESS_KEY": "test-access-key",
            "S3_SECRET_KEY": "test-secret-key",
            "S3_BUCKET": "homean-media-test",
            "JWT_SECRET": "test-jwt-secret-with-sufficient-length",
            "APP_ENV": "test",
        }
    )
    get_settings.cache_clear()
    await asyncio.to_thread(_run_migrations, database_url)

    try:
        yield database_url
    finally:
        await dispose_database()
        await _clear_redis_namespace(redis_url, rate_limit_key_prefix)
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


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_app(  # type: ignore[no-untyped-def]
    database_url: str,
    app_storage: FakeStorageProvider,
    app_pipeline: FakePipelineEnqueuer,
    app_email: FakeEmailProvider,
):
    del database_url
    from app.api.dependencies import (
        get_email_provider,
        get_pipeline_enqueuer,
        get_report_renderer,
        get_storage_provider,
    )
    from app.main import app

    app.dependency_overrides[get_storage_provider] = lambda: app_storage
    app.dependency_overrides[get_pipeline_enqueuer] = lambda: app_pipeline
    app.dependency_overrides[get_email_provider] = lambda: app_email
    app.dependency_overrides[get_report_renderer] = lambda: FakeReportRenderer(
        app_storage, VerticalConfigService()
    )
    try:
        async with app.router.lifespan_context(app):
            yield app
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def app_storage() -> FakeStorageProvider:
    return FakeStorageProvider()


@pytest.fixture(scope="session")
def app_pipeline() -> FakePipelineEnqueuer:
    return FakePipelineEnqueuer()


@pytest.fixture(scope="session")
def app_email() -> FakeEmailProvider:
    return FakeEmailProvider()


@pytest.fixture
def storage(app_storage: FakeStorageProvider) -> FakeStorageProvider:
    app_storage.objects.clear()
    app_storage.object_bodies.clear()
    app_storage.presigned_puts.clear()
    app_storage.presigned_gets.clear()
    return app_storage


@pytest.fixture
def pipeline(app_pipeline: FakePipelineEnqueuer) -> FakePipelineEnqueuer:
    app_pipeline.jobs.clear()
    return app_pipeline


@pytest.fixture
def email_provider(app_email: FakeEmailProvider) -> FakeEmailProvider:
    app_email.messages.clear()
    app_email.attempts.clear()
    app_email.error = None
    app_email.error_after_accept = None
    return app_email


@pytest_asyncio.fixture
async def client(test_app) -> AsyncIterator[AsyncClient]:  # type: ignore[no-untyped-def]
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as http_client:
        yield http_client


@pytest_asyncio.fixture
async def session(database_url: str):  # type: ignore[no-untyped-def]
    del database_url
    async with get_session_factory()() as database_session:
        yield database_session
