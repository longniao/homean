from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_storage_provider
from app.api.errors import register_exception_handlers
from app.api.routers import (
    auth_router,
    billing_router,
    branding_router,
    contacts_router,
    delivery_router,
    me_router,
    properties_router,
    public_reports_router,
    review_router,
    showings_router,
    vertical_router,
)
from app.core.config import get_settings
from app.core.database import dispose_database, get_session, get_session_factory
from app.core.security import (
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
    configure_observability,
)
from app.storage import StorageProvider
from app.verticals import get_vertical_config_service, seed_verticals


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    vertical_config = get_vertical_config_service()
    app.state.vertical_config = vertical_config
    async with get_session_factory()() as session:
        async with session.begin():
            await seed_verticals(session, vertical_config)
    yield
    await dispose_database()


settings = get_settings()
configure_observability(settings)
app = FastAPI(title="Kawu API", lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, settings=settings)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.dashboard_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
register_exception_handlers(app)
app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(me_router)
app.include_router(contacts_router)
app.include_router(properties_router)
app.include_router(showings_router)
app.include_router(review_router)
app.include_router(branding_router)
app.include_router(delivery_router)
app.include_router(public_reports_router)
app.include_router(vertical_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
async def ready(
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[StorageProvider, Depends(get_storage_provider)],
) -> JSONResponse:
    checks: dict[str, str] = {}
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    redis = Redis.from_url(settings.redis_url)
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    finally:
        await redis.aclose()
    try:
        await storage.check_ready()
        checks["s3"] = "ok"
    except Exception:
        checks["s3"] = "error"
    ready_status = "ok" if all(value == "ok" for value in checks.values()) else "error"
    return JSONResponse(
        {"status": ready_status, "checks": checks},
        status_code=status.HTTP_200_OK
        if ready_status == "ok"
        else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
