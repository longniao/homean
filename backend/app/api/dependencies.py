from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.email import EmailProvider, create_email_provider
from app.pipeline import CeleryPipelineEnqueuer, PipelineEnqueuer
from app.repositories import AuthRepository
from app.services import (
    AuthService,
    CurrentContext,
    RealEstateContactService,
    RealEstateBrandingService,
    RealEstateDeliveryService,
    RealEstatePropertyService,
    RealEstateReviewService,
    RealEstateShowingService,
    ReportRenderer,
    TokenService,
)
from app.services.exceptions import InvalidTokenError
from app.storage import S3Client, StorageProvider
from app.verticals import get_vertical_config_service

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(session, settings)


def get_contact_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RealEstateContactService:
    return RealEstateContactService(session)


def get_property_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RealEstatePropertyService:
    return RealEstatePropertyService(session)


@lru_cache
def get_storage_provider() -> StorageProvider:
    return S3Client(get_settings())


@lru_cache
def get_pipeline_enqueuer() -> PipelineEnqueuer:
    return CeleryPipelineEnqueuer()


def get_showing_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[StorageProvider, Depends(get_storage_provider)],
    pipeline: Annotated[PipelineEnqueuer, Depends(get_pipeline_enqueuer)],
) -> RealEstateShowingService:
    return RealEstateShowingService(session, storage, pipeline, settings)


def get_report_renderer(
    storage: Annotated[StorageProvider, Depends(get_storage_provider)],
) -> ReportRenderer:
    return ReportRenderer(storage, get_vertical_config_service())


def get_review_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    renderer: Annotated[ReportRenderer, Depends(get_report_renderer)],
) -> RealEstateReviewService:
    return RealEstateReviewService(
        session, get_vertical_config_service(), renderer
    )


def get_branding_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[StorageProvider, Depends(get_storage_provider)],
) -> RealEstateBrandingService:
    return RealEstateBrandingService(session, storage, settings)


@lru_cache
def get_email_provider() -> EmailProvider:
    return create_email_provider(get_settings())


def get_delivery_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    renderer: Annotated[ReportRenderer, Depends(get_report_renderer)],
    email_provider: Annotated[EmailProvider, Depends(get_email_provider)],
) -> RealEstateDeliveryService:
    return RealEstateDeliveryService(session, settings, renderer, email_provider)


async def get_current_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = TokenService(settings).decode(credentials.credentials, "access")
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    context = await AuthRepository(session).get_context(claims.sub, claims.workspace_id)
    if context is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return CurrentContext(*context)
