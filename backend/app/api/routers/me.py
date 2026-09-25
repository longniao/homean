from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_billing_provider,
    get_current_context,
    get_storage_provider,
)
from app.core.database import get_session
from app.schemas import MeResponse
from app.schemas.me import AccountDeleteRequest, MeUpdate
from app.services import AccountDeletionService, CurrentContext, MeService
from app.services.billing import BillingProvider
from app.services.exceptions import InvalidCredentialsError
from app.storage.provider import StorageProvider

router = APIRouter(tags=["account"])


@router.get("/me", response_model=MeResponse)
async def get_me(
    context: Annotated[CurrentContext, Depends(get_current_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MeResponse:
    result = await MeService(session).get(context)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return MeResponse.from_result(result)


@router.patch("/me", response_model=MeResponse)
async def update_me(
    payload: MeUpdate,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MeResponse:
    service = MeService(session)
    result = (
        await service.update(context, payload.name)
        if "name" in payload.model_fields_set
        else await service.get(context)
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return MeResponse.from_result(result)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    payload: AccountDeleteRequest,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[StorageProvider, Depends(get_storage_provider)],
    billing_provider: Annotated[BillingProvider, Depends(get_billing_provider)],
) -> None:
    """Delete the caller's account, workspace, media and sessions for good.

    Re-authentication by password keeps a stolen unlocked phone or a leaked
    access token from wiping an agent's records. A wrong password is 403, not
    401, so clients do not mistake it for an expired session.
    """

    service = AccountDeletionService(session, storage, billing_provider)
    try:
        await service.delete(context, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Password does not match"
        ) from exc
