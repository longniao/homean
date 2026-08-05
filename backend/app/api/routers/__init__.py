from app.api.routers.auth import router as auth_router
from app.api.routers.branding import router as branding_router
from app.api.routers.contacts import router as contacts_router
from app.api.routers.delivery import router as delivery_router
from app.api.routers.me import router as me_router
from app.api.routers.properties import router as properties_router
from app.api.routers.public_reports import router as public_reports_router
from app.api.routers.review import router as review_router
from app.api.routers.showings import router as showings_router
from app.api.routers.vertical import router as vertical_router

__all__ = [
    "auth_router",
    "branding_router",
    "contacts_router",
    "delivery_router",
    "me_router",
    "properties_router",
    "public_reports_router",
    "review_router",
    "showings_router",
    "vertical_router",
]
