import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contact


class ContactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, workspace_id: uuid.UUID) -> list[Contact]:
        result = await self.session.scalars(
            select(Contact)
            .where(Contact.workspace_id == workspace_id)
            .order_by(Contact.name, Contact.id)
        )
        return list(result)

    async def get(
        self, workspace_id: uuid.UUID, contact_id: uuid.UUID
    ) -> Contact | None:
        return await self.session.scalar(
            select(Contact).where(
                Contact.id == contact_id,
                Contact.workspace_id == workspace_id,
            )
        )

    def add(self, contact: Contact) -> None:
        self.session.add(contact)

    async def delete(self, contact: Contact) -> None:
        await self.session.delete(contact)
