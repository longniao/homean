import pytest
from sqlalchemy.engine import make_url

from app.core.database_url import normalize_database_url


def test_render_postgres_url_selects_asyncpg_driver() -> None:
    url = normalize_database_url("postgres://user:pass@db.render.com:5432/kawu")
    assert url == "postgresql+asyncpg://user:pass@db.render.com:5432/kawu"
    assert make_url(url).drivername == "postgresql+asyncpg"


def test_postgresql_url_selects_asyncpg_driver() -> None:
    url = normalize_database_url("postgresql://user:pass@localhost/kawu")
    assert make_url(url).drivername == "postgresql+asyncpg"


def test_existing_asyncpg_url_is_unchanged() -> None:
    value = "postgresql+asyncpg://user:pass@localhost/kawu"
    assert normalize_database_url(value) == value


def test_runtime_engine_normalizes_render_url(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from pydantic import SecretStr

    from app.core import database, database_url
    from app.core.config import Settings

    settings = Settings(
        database_url="postgres://user:pass@db.render.com:5432/kawu",
        redis_url="redis://localhost/0",
        s3_endpoint_url="http://localhost:9000",
        s3_access_key="access",
        s3_secret_key=SecretStr("secret"),
        s3_bucket="bucket",
        jwt_secret=SecretStr("a-sufficiently-long-test-secret"),
    )
    captured: dict[str, object] = {}

    def fake_create_engine(url: str, **kwargs: object) -> object:
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(database_url, "create_async_engine", fake_create_engine)
    database.get_engine.cache_clear()
    try:
        database.get_engine()
    finally:
        database.get_engine.cache_clear()
    assert make_url(str(captured["url"])).drivername == "postgresql+asyncpg"


@pytest.mark.parametrize(
    "database_url",
    [
        "postgres://user:pass@db.render.com:5432/kawu",
        "postgresql://user:pass@db.render.com:5432/kawu",
    ],
)
def test_pipeline_worker_engine_normalizes_render_urls(
    monkeypatch, database_url: str
) -> None:  # type: ignore[no-untyped-def]
    from app.core import database_url as database_url_module
    from app.core.config import get_settings

    for key, value in {
        "DATABASE_URL": database_url,
        "REDIS_URL": "redis://localhost/0",
        "S3_ENDPOINT_URL": "http://localhost:9000",
        "S3_ACCESS_KEY": "access",
        "S3_SECRET_KEY": "secret",
        "S3_BUCKET": "bucket",
        "JWT_SECRET": "a-sufficiently-long-test-secret",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    from app.pipeline import tasks

    captured: dict[str, object] = {}

    def fake_create_engine(url: str, **kwargs: object) -> object:
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(database_url_module, "create_async_engine", fake_create_engine)
    try:
        tasks._create_pipeline_engine(database_url)
        assert make_url(str(captured["url"])).drivername == "postgresql+asyncpg"
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    "database_url",
    [
        "postgres://user:pass@db.render.com:5432/kawu",
        "postgresql://user:pass@db.render.com:5432/kawu",
    ],
)
def test_cost_report_engine_normalizes_render_urls(
    monkeypatch, database_url: str
) -> None:  # type: ignore[no-untyped-def]
    from app.core import database_url as database_url_module
    from scripts import ai_cost_report

    captured: dict[str, object] = {}

    def fake_create_engine(url: str, **kwargs: object) -> object:
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(database_url_module, "create_async_engine", fake_create_engine)
    ai_cost_report._create_cost_report_engine(database_url)
    assert make_url(str(captured["url"])).drivername == "postgresql+asyncpg"
