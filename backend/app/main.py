from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.routers import (
    auth_router,
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
from app.core.database import dispose_database, get_session_factory
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


app = FastAPI(title="Kawu API", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(auth_router)
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
