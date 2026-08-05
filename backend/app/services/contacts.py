import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contact
from app.repositories import ContactRepository
from app.schemas.contacts import ContactCreate, ContactUpdate
from app.services.context import CurrentContext
from app.services.exceptions import DomainValidationError, ResourceNotFoundError


class RealEstateContactService:
    def __init__(self, session: AsyncSession) -> None:
        self._repository = ContactRepository(session)

    async def list_contacts(self, context: CurrentContext) -> list[Contact]:
        return await self._repository.list(context.workspace.id)

    async def get_contact(
        self, context: CurrentContext, contact_id: uuid.UUID
    ) -> Contact:
        contact = await self._repository.get(context.workspace.id, contact_id)
        if contact is None:
            raise ResourceNotFoundError
        return contact

    async def create_contact(
        self, context: CurrentContext, payload: ContactCreate
    ) -> Contact:
        contact = Contact(
            workspace_id=context.workspace.id,
            name=payload.name.strip(),
            email=str(payload.email).lower() if payload.email else None,
            phone=payload.phone,
            notes=payload.notes,
            contact_info={},
        )
        self._repository.add(contact)
        await self._repository.session.flush()
        return contact

    async def update_contact(
        self,
        context: CurrentContext,
        contact_id: uuid.UUID,
        payload: ContactUpdate,
    ) -> Contact:
        changes = payload.model_dump(exclude_unset=True)
        if changes.get("name") is None and "name" in changes:
            raise DomainValidationError("name cannot be null")
        if email := changes.get("email"):
            changes["email"] = str(email).lower()
        contact = await self._repository.get(context.workspace.id, contact_id)
        if contact is None:
            raise ResourceNotFoundError
        for field, value in changes.items():
            setattr(contact, field, value)
        await self._repository.session.flush()
        await self._repository.session.refresh(contact)
        return contact

    async def delete_contact(
        self, context: CurrentContext, contact_id: uuid.UUID
    ) -> None:
        contact = await self._repository.get(context.workspace.id, contact_id)
        if contact is None:
            raise ResourceNotFoundError
        await self._repository.delete(contact)
