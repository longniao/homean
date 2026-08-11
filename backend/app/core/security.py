import asyncio
import copy
import json
import logging
import os
import time
import traceback
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings

logger = logging.getLogger("kawu.request")

_SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-csrf-token",
}
_SAFE_LOG_EVENTS = {
    "request_complete",
    "request_failed",
    "sentry_not_installed",
}
_sentry_initialized = False


def _safe_log_path(path: str) -> str:
    """Keep public share tokens out of request logs."""
    if path == "/r" or not path.startswith("/r/"):
        return path
    suffix = path[len("/r/") :]
    token, separator, rest = suffix.partition("/")
    if not token:
        return "/r"
    return f"/r/[token]{separator}{rest}" if separator else "/r/[token]"


def _safe_sentry_url(value: object) -> object:
    if not isinstance(value, str):
        return value
    parsed = urlsplit(value)
    path = _safe_log_path(parsed.path)
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _sanitize_sentry_request(request: object) -> None:
    if not isinstance(request, dict):
        return
    if "url" in request:
        request["url"] = _safe_sentry_url(request["url"])
    headers = request.get("headers")
    if isinstance(headers, dict):
        request["headers"] = {
            key: value
            for key, value in headers.items()
            if str(key).lower() not in _SENSITIVE_HEADERS
        }
    for key in ("cookies", "data", "query_string", "env"):
        request.pop(key, None)


def _sanitize_sentry_exception(exception: object) -> object:
    """Keep exception type/frames while dropping values, locals, and paths."""
    if not isinstance(exception, dict):
        return exception
    values = exception.get("values")
    if not isinstance(values, list):
        return {}
    clean_values: list[dict[str, object]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        clean: dict[str, object] = {}
        if isinstance(value.get("type"), str):
            clean["type"] = value["type"]
        stacktrace = value.get("stacktrace")
        if isinstance(stacktrace, dict):
            frames = stacktrace.get("frames")
            clean_frames: list[dict[str, object]] = []
            if isinstance(frames, list):
                for frame in frames:
                    if not isinstance(frame, dict):
                        continue
                    clean_frame: dict[str, object] = {}
                    filename = frame.get("filename")
                    if isinstance(filename, str):
                        clean_frame["filename"] = os.path.basename(filename)
                    function = frame.get("function")
                    if isinstance(function, str):
                        clean_frame["function"] = function
                    lineno = frame.get("lineno")
                    if isinstance(lineno, int):
                        clean_frame["lineno"] = lineno
                    if clean_frame:
                        clean_frames.append(clean_frame)
            if clean_frames:
                clean["stacktrace"] = {"frames": clean_frames}
        if clean:
            clean_values.append(clean)
    return {"values": clean_values}


def sanitize_sentry_event(
    event: dict[str, object], hint: object = None
) -> dict[str, object]:
    """Remove credentials, PII, evidence text, and share tokens from Sentry payloads."""
    del hint
    sanitized = copy.deepcopy(event)
    _sanitize_sentry_request(sanitized.get("request"))
    if isinstance(sanitized.get("transaction"), str):
        sanitized["transaction"] = _safe_log_path(sanitized["transaction"])
    sanitized.pop("user", None)
    sanitized.pop("message", None)
    sanitized.pop("logentry", None)
    sanitized.pop("tags", None)
    if "exception" in sanitized:
        sanitized["exception"] = _sanitize_sentry_exception(sanitized["exception"])
    sanitized.pop("breadcrumbs", None)
    sanitized.pop("extra", None)
    sanitized.pop("contexts", None)
    return sanitized


def sanitize_sentry_transaction(
    event: dict[str, object], hint: object = None
) -> dict[str, object]:
    del hint
    sanitized = copy.deepcopy(event)
    _sanitize_sentry_request(sanitized.get("request"))
    if isinstance(sanitized.get("transaction"), str):
        sanitized["transaction"] = _safe_log_path(sanitized["transaction"])
    sanitized.pop("user", None)
    sanitized.pop("message", None)
    sanitized.pop("logentry", None)
    sanitized.pop("tags", None)
    if "exception" in sanitized:
        sanitized["exception"] = _sanitize_sentry_exception(sanitized["exception"])
    sanitized.pop("breadcrumbs", None)
    sanitized.pop("extra", None)
    sanitized.pop("contexts", None)
    return sanitized


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": _safe_log_path(request.url.path),
                },
            )
            raise
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_complete",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": _safe_log_path(request.url.path),
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000),
            },
        )
        return response


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = "exception" if record.exc_info else "log_event"
        if (
            not record.exc_info
            and not record.args
            and isinstance(record.msg, str)
            and record.msg in _SAFE_LOG_EVENTS
        ):
            message = record.msg
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            # Exception messages can contain provider payloads or evidence
            # text. Keep the event name, type, and frames instead.
            # Framework log messages are likewise not trusted: Celery may
            # interpolate task arguments into them, so only static events
            # from our own request/observability logger are retained.
            "message": message,
        }
        for key in ("request_id", "method", "path", "status", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            exception_type, _, tb = record.exc_info
            if exception_type is not None:
                payload["exception_type"] = exception_type.__name__
            if tb is not None:
                payload["stacktrace"] = [
                    {
                        "filename": os.path.basename(frame.filename),
                        "function": frame.name,
                        "lineno": frame.lineno,
                    }
                    for frame in traceback.extract_tb(tb)
                ]
        return json.dumps(payload, separators=(",", ":"))


def configure_json_logger(log: logging.Logger) -> None:
    """Install one sanitized JSON handler on a framework-owned logger."""

    handler = next(
        (
            candidate
            for candidate in log.handlers
            if getattr(candidate, "_kawu_observability", False)
        ),
        None,
    )
    for existing in list(log.handlers):
        if existing is not handler:
            log.removeHandler(existing)
    if handler is None:
        handler = logging.StreamHandler()
        handler._kawu_observability = True  # type: ignore[attr-defined]
        log.addHandler(handler)
    handler.setFormatter(JsonLogFormatter())
    log.propagate = False


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app: Callable[..., Awaitable[Response]], settings: Settings
    ) -> None:
        super().__init__(app)
        self._settings = settings
        self._buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.05,
            socket_timeout=0.05,
        )

    @staticmethod
    def _category(path: str) -> tuple[str, int] | None:
        if path in {"/auth/login", "/auth/signup", "/auth/refresh"}:
            return "auth", 0
        if path == "/r" or path.startswith("/r/"):
            return "public_share", 0
        return None

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        category = self._category(request.url.path)
        if category is None:
            return await call_next(request)
        name, _ = category
        limit = (
            self._settings.auth_rate_limit
            if name == "auth"
            else self._settings.public_share_rate_limit
        )
        client = request.client.host if request.client else "unknown"
        key = (name, client)
        now = time.monotonic()
        redis_key = (
            f"{self._settings.rate_limit_key_prefix}:ratelimit:{name}:{client}:"
            f"{int(time.time()) // self._settings.rate_limit_window_seconds}"
        )
        try:
            redis_count = int(await self._redis.incr(redis_key))
            if redis_count == 1:
                await self._redis.expire(
                    redis_key, self._settings.rate_limit_window_seconds + 1
                )
            if redis_count > limit:
                return JSONResponse(
                    {"detail": "Too many requests"},
                    status_code=429,
                    headers={
                        "Retry-After": str(self._settings.rate_limit_window_seconds)
                    },
                )
            return await call_next(request)
        except Exception:
            # A rate limiter must not take the API down when Redis is restarting.
            # The local fallback still protects each API process in that window.
            pass
        async with self._lock:
            values = [
                timestamp
                for timestamp in self._buckets[key]
                if timestamp > now - self._settings.rate_limit_window_seconds
            ]
            if len(values) >= limit:
                retry_after = max(
                    1,
                    int(values[0] + self._settings.rate_limit_window_seconds - now),
                )
                self._buckets[key] = values
                return JSONResponse(
                    {"detail": "Too many requests"},
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )
            values.append(now)
            self._buckets[key] = values
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=()")
        if request.url.path == "/r" or request.url.path.startswith("/r/"):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
                "font-src data:",
            )
            response.headers.setdefault("Cache-Control", "private, no-store, max-age=0")
            response.headers.setdefault("Pragma", "no-cache")
            response.headers.setdefault("X-Robots-Tag", "noindex, nofollow, noarchive")
        return response


def configure_observability(settings: Settings) -> None:
    root = logging.getLogger()
    # The application logger is the canonical access log. Remove handlers
    # installed by a previous framework/default logging configuration so a
    # repeated initialization cannot emit every record twice.
    for existing in list(root.handlers):
        if not getattr(existing, "_kawu_observability", False):
            root.removeHandler(existing)
    configure_json_logger(root)
    root.setLevel(logging.INFO)
    global _sentry_initialized
    if settings.sentry_dsn and not _sentry_initialized:
        try:
            import sentry_sdk

            sentry_sdk.init(
                settings.sentry_dsn,
                environment=settings.app_env,
                send_default_pii=False,
                before_send=sanitize_sentry_event,
                before_send_transaction=sanitize_sentry_transaction,
            )
            _sentry_initialized = True
        except ImportError:
            logger.warning("sentry_not_installed")
