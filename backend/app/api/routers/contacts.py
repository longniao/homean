import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_contact_service, get_current_context
from app.schemas import ContactCreate, ContactResponse, ContactUpdate
from app.services import CurrentContext, RealEstateContactService

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=list[ContactResponse])
async def list_contacts(
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateContactService, Depends(get_contact_service)],
) -> list[ContactResponse]:
    contacts = await service.list_contacts(context)
    return [ContactResponse.model_validate(item) for item in contacts]


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    payload: ContactCreate,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateContactService, Depends(get_contact_service)],
) -> ContactResponse:
    return ContactResponse.model_validate(
        await service.create_contact(context, payload)
    )


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: uuid.UUID,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateContactService, Depends(get_contact_service)],
) -> ContactResponse:
    return ContactResponse.model_validate(
        await service.get_contact(context, contact_id)
    )


@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: uuid.UUID,
    payload: ContactUpdate,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateContactService, Depends(get_contact_service)],
) -> ContactResponse:
    contact = await service.update_contact(context, contact_id, payload)
    return ContactResponse.model_validate(contact)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: uuid.UUID,
    context: Annotated[CurrentContext, Depends(get_current_context)],
    service: Annotated[RealEstateContactService, Depends(get_contact_service)],
) -> Response:
    await service.delete_contact(context, contact_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
