import io
import json
import logging
import sys

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr, ValidationError
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.core.config import Settings
from app.core.security import (
    JsonLogFormatter,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    configure_observability,
    sanitize_sentry_event,
    sanitize_sentry_transaction,
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+asyncpg://test:test@localhost/test",
        "redis_url": "redis://localhost/0",
        "s3_endpoint_url": "http://localhost:9000",
        "s3_access_key": "access",
        "s3_secret_key": SecretStr("secret"),
        "s3_bucket": "bucket",
        "jwt_secret": SecretStr("a-sufficiently-long-test-secret"),
        "auth_rate_limit": 2,
        "public_share_rate_limit": 2,
        "rate_limit_window_seconds": 60,
    }
    values.update(overrides)
    return Settings(**values)


def test_presigned_url_ttls_are_positive_and_capped_at_fifteen_minutes() -> None:
    settings = _settings(
        presigned_upload_seconds=3600,
        presigned_download_seconds=901,
    )
    assert settings.presigned_upload_seconds == 900
    assert settings.presigned_download_seconds == 900

    with pytest.raises(ValidationError):
        _settings(presigned_upload_seconds=0)
    with pytest.raises(ValidationError):
        _settings(presigned_download_seconds=-1)


async def _ok(request) -> PlainTextResponse:  # type: ignore[no-untyped-def]
    del request
    return PlainTextResponse("ok")


class _RedisCounter:
    def __init__(self, *, error: bool = False) -> None:
        self.count = 0
        self.error = error

    async def incr(self, key: str) -> int:
        del key
        if self.error:
            raise ConnectionError("redis unavailable")
        self.count += 1
        return self.count

    async def expire(self, key: str, seconds: int) -> None:
        del key, seconds


class _PerKeyRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        del key, seconds


async def _rate_limited_client(redis: _RedisCounter) -> AsyncClient:
    base = Starlette(routes=[Route("/auth/login", _ok, methods=["POST"])])
    middleware = RateLimitMiddleware(base, _settings())
    middleware._redis = redis
    return AsyncClient(transport=ASGITransport(app=middleware), base_url="http://test")


@pytest.mark.asyncio
async def test_redis_rate_limit_blocks_after_configured_window_count() -> None:
    client = await _rate_limited_client(_RedisCounter())
    async with client:
        assert (await client.post("/auth/login")).status_code == 200
        assert (await client.post("/auth/login")).status_code == 200
        blocked = await client.post("/auth/login")
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "60"


@pytest.mark.asyncio
async def test_rate_limit_uses_local_fallback_when_redis_is_down() -> None:
    client = await _rate_limited_client(_RedisCounter(error=True))
    async with client:
        assert (await client.post("/auth/login")).status_code == 200
        assert (await client.post("/auth/login")).status_code == 200
        blocked = await client.post("/auth/login")
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_trusted_forwarded_client_ips_get_distinct_rate_limit_buckets() -> None:
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    redis = _PerKeyRedis()
    base = Starlette(routes=[Route("/auth/login", _ok, methods=["POST"])])
    limited = RateLimitMiddleware(
        base, _settings(auth_rate_limit=1, rate_limit_window_seconds=60)
    )
    # This models Uvicorn's trusted Render ingress boundary. The application
    # middleware itself never parses user-supplied X-Forwarded-For headers.
    app = ProxyHeadersMiddleware(limited, trusted_hosts="*")
    limited._redis = redis
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        first_a = await client.post(
            "/auth/login", headers={"X-Forwarded-For": "198.51.100.10"}
        )
        first_b = await client.post(
            "/auth/login", headers={"X-Forwarded-For": "198.51.100.11"}
        )
        second_a = await client.post(
            "/auth/login", headers={"X-Forwarded-For": "198.51.100.10"}
        )
    assert first_a.status_code == first_b.status_code == 200
    assert second_a.status_code == 429
    assert len(redis.counts) == 2


@pytest.mark.asyncio
async def test_rate_limit_keys_use_configured_namespace() -> None:
    redis = _PerKeyRedis()
    base = Starlette(routes=[Route("/auth/login", _ok, methods=["POST"])])
    limited = RateLimitMiddleware(
        base,
        _settings(rate_limit_key_prefix="homean:test:isolated"),
    )
    limited._redis = redis

    async with AsyncClient(
        transport=ASGITransport(app=limited), base_url="http://test"
    ) as client:
        response = await client.post("/auth/login")

    assert response.status_code == 200
    assert len(redis.counts) == 1
    assert next(iter(redis.counts)).startswith(
        "homean:test:isolated:ratelimit:auth:127.0.0.1:"
    )


def test_sentry_sanitizers_remove_pii_credentials_and_share_tokens() -> None:
    event = {
        "request": {
            "url": "https://api.example/r/secret-token?email=buyer@example.com",
            "headers": {
                "authorization": "Bearer secret",
                "cookie": "refresh=secret",
                "content-type": "application/json",
            },
            "cookies": {"refresh": "secret"},
            "data": {"transcript": "private"},
            "query_string": "email=buyer@example.com",
        },
        "logentry": {"message": "private transcript"},
        "tags": {"email": "buyer@example.com"},
        "transaction": "/r/secret-token",
        "user": {"email": "buyer@example.com"},
        "message": "private report contents",
        "breadcrumbs": [{"message": "private"}],
        "extra": {"report": "private"},
        "contexts": {"transcript": "private"},
    }
    sanitized = sanitize_sentry_event(event)
    request = sanitized["request"]
    assert request["url"] == "https://api.example/r/[token]"
    assert request["headers"] == {"content-type": "application/json"}
    assert "cookies" not in request and "data" not in request
    assert sanitized["transaction"] == "/r/[token]"
    assert "user" not in sanitized and "message" not in sanitized
    assert "logentry" not in sanitized and "tags" not in sanitized

    transaction = sanitize_sentry_transaction(event)
    assert transaction["request"]["url"] == "https://api.example/r/[token]"
    assert "breadcrumbs" not in transaction
    assert "extra" not in transaction and "contexts" not in transaction


def test_observability_preserves_safe_exception_diagnostics_only() -> None:
    try:
        raise ValueError("private transcript and password")
    except ValueError:
        record = logging.LogRecord(
            name="homean.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="private transcript and password",
            args=(),
            exc_info=sys.exc_info(),
        )
    payload = json.loads(JsonLogFormatter().format(record))
    assert payload["message"] == "exception"
    assert payload["exception_type"] == "ValueError"
    assert payload["stacktrace"][-1]["function"] == (
        "test_observability_preserves_safe_exception_diagnostics_only"
    )
    serialized = json.dumps(payload)
    assert "private transcript" not in serialized
    assert "password" not in serialized

    task_record = logging.LogRecord(
        name="celery.worker",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Task payload contains private transcript and provider token",
        args=(),
        exc_info=None,
    )
    task_payload = json.loads(JsonLogFormatter().format(task_record))
    assert task_payload["message"] == "log_event"
    assert "private transcript" not in json.dumps(task_payload)
    assert "provider token" not in json.dumps(task_payload)

    event = {
        "exception": {
            "values": [
                {
                    "type": "RuntimeError",
                    "value": "private report and token",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "/private/customer/report.py",
                                "function": "render_report",
                                "lineno": 42,
                                "vars": {"body": "transcript"},
                            }
                        ]
                    },
                }
            ]
        }
    }
    sanitized = sanitize_sentry_event(event)
    exception = sanitized["exception"]["values"][0]
    assert exception["type"] == "RuntimeError"
    assert "value" not in exception
    frame = exception["stacktrace"]["frames"][0]
    assert frame == {
        "filename": "report.py",
        "function": "render_report",
        "lineno": 42,
    }
    assert "transcript" not in json.dumps(sanitized)
    transaction_sanitized = sanitize_sentry_transaction(event)
    transaction_exception = transaction_sanitized["exception"]["values"][0]
    assert transaction_exception["type"] == "RuntimeError"
    assert "value" not in transaction_exception


def test_configure_observability_does_not_duplicate_json_handler() -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        root.handlers[:] = []
        settings = _settings(sentry_dsn=None)
        configure_observability(settings)
        configure_observability(settings)
        handlers = [
            handler
            for handler in root.handlers
            if getattr(handler, "_homean_observability", False)
        ]
        assert len(handlers) == 1
    finally:
        root.handlers[:] = original_handlers
        root.setLevel(original_level)


def test_celery_post_setup_logger_is_sanitized_json_and_idempotent(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    import importlib

    from app.core.config import get_settings

    for key, value in {
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
        "REDIS_URL": "redis://localhost/0",
        "S3_ENDPOINT_URL": "http://localhost:9000",
        "S3_ACCESS_KEY": "access",
        "S3_SECRET_KEY": "secret",
        "S3_BUCKET": "bucket",
        "JWT_SECRET": "a-sufficiently-long-test-secret",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    importlib.import_module("app.pipeline.celery_app")
    from celery.signals import after_setup_logger

    logger = logging.getLogger("celery.test.effective")
    logger.handlers[:] = []
    stream = io.StringIO()
    logger.addHandler(logging.StreamHandler(stream))
    try:
        after_setup_logger.send(sender=logger, logger=logger)
        after_setup_logger.send(sender=logger, logger=logger)
        handlers = [
            handler
            for handler in logger.handlers
            if getattr(handler, "_homean_observability", False)
        ]
        assert len(handlers) == 1
        handlers[0].stream = stream
        try:
            raise RuntimeError("private task payload and credentials")
        except RuntimeError:
            logger.exception("private task payload and credentials")
        payload = json.loads(stream.getvalue())
        assert payload["message"] == "exception"
        assert payload["exception_type"] == "RuntimeError"
        assert "private task payload" not in stream.getvalue()
        assert "credentials" not in stream.getvalue()
        assert payload["stacktrace"][-1]["function"] == (
            "test_celery_post_setup_logger_is_sanitized_json_and_idempotent"
        )
    finally:
        logger.handlers[:] = []
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_security_headers_middleware_covers_public_error_responses() -> None:
    async def missing(request) -> PlainTextResponse:  # type: ignore[no-untyped-def]
        del request
        return PlainTextResponse("missing", status_code=404)

    app = SecurityHeadersMiddleware(Starlette(routes=[Route("/r/bad", missing)]))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/r/bad")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "private, no-store, max-age=0"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["x-robots-tag"] == "noindex, nofollow, noarchive"
    assert response.headers["x-content-type-options"] == "nosniff"


class _ReadySession:
    def __init__(self, error: bool = False) -> None:
        self.error = error

    async def execute(self, statement) -> None:  # type: ignore[no-untyped-def]
        del statement
        if self.error:
            raise ConnectionError("database unavailable")


class _ReadyStorage:
    def __init__(self, error: bool = False) -> None:
        self.error = error

    async def check_ready(self) -> None:
        if self.error:
            raise ConnectionError("object storage unavailable")


class _ReadyRedis:
    error = False

    @classmethod
    def from_url(cls, url: str) -> "_ReadyRedis":
        del url
        return cls()

    async def ping(self) -> bool:
        if self.error:
            raise ConnectionError("redis unavailable")
        return True

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "database", "redis", "s3"])
async def test_ready_reports_success_and_individual_dependency_failures(
    monkeypatch, failure: str | None
) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import get_settings

    for key, value in {
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
        "REDIS_URL": "redis://localhost/0",
        "S3_ENDPOINT_URL": "http://localhost:9000",
        "S3_ACCESS_KEY": "access",
        "S3_SECRET_KEY": "secret",
        "S3_BUCKET": "bucket",
        "JWT_SECRET": "a-sufficiently-long-test-secret",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    import app.main as main_module

    class RedisForCase(_ReadyRedis):
        error = failure == "redis"

    monkeypatch.setattr(main_module, "Redis", RedisForCase)
    response = await main_module.ready(
        _ReadySession(failure == "database"), _ReadyStorage(failure == "s3")
    )
    payload = json.loads(response.body)
    assert payload["status"] == ("ok" if failure is None else "error")
    assert response.status_code == (200 if failure is None else 503)
    for name in ("database", "redis", "s3"):
        assert payload["checks"][name] == ("error" if failure == name else "ok")
    get_settings.cache_clear()
