import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_current_context, get_property_service
from app.schemas import PropertyCreate, PropertyResponse, PropertyUpdate
from app.services import CurrentContext, RealEstatePropertyService

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("", response_model=list[PropertyResponse])
async def list_properties(
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstatePropertyService, Depends(get_property_service)],
) -> list[PropertyResponse]:
    properties = await service.list_properties(context)
    return [PropertyResponse.from_subject(item) for item in properties]


@router.post("", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    payload: PropertyCreate,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstatePropertyService, Depends(get_property_service)],
) -> PropertyResponse:
    return PropertyResponse.from_subject(
        await service.create_property(context, payload)
    )


@router.get("/{subject_id}", response_model=PropertyResponse)
async def get_property(
    subject_id: uuid.UUID,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstatePropertyService, Depends(get_property_service)],
) -> PropertyResponse:
    return PropertyResponse.from_subject(
        await service.get_property(context, subject_id)
    )


@router.patch("/{subject_id}", response_model=PropertyResponse)
async def update_property(
    subject_id: uuid.UUID,
    payload: PropertyUpdate,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstatePropertyService, Depends(get_property_service)],
) -> PropertyResponse:
    subject = await service.update_property(context, subject_id, payload)
    return PropertyResponse.from_subject(subject)


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    subject_id: uuid.UUID,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstatePropertyService, Depends(get_property_service)],
) -> Response:
    await service.delete_property(context, subject_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
