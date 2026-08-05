from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_context
from app.core.database import get_session
from app.schemas import MeResponse
from app.services import CurrentContext, MeService

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
