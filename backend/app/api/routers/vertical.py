from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_context
from app.schemas.vertical import (
    VerticalConfigResponse,
    VerticalDisplayLabelsResponse,
)
from app.services import CurrentContext
from app.verticals import VerticalConfigService, get_vertical_config_service

router = APIRouter(tags=["vertical"])


@router.get("/vertical-config", response_model=VerticalConfigResponse)
async def get_vertical_config(
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[VerticalConfigService, Depends(get_vertical_config_service)],
) -> VerticalConfigResponse:
    del context
    pack = service.get("real_estate")
    return VerticalConfigResponse(
        zone_taxonomy=pack.zone_taxonomy,
        observation_schema=pack.observation_schema,
        display_labels=VerticalDisplayLabelsResponse(
            zones=pack.display_labels.zones,
            observations=pack.display_labels.observations,
        ),
    )
