import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subject, Vertical


class PropertyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, workspace_id: uuid.UUID) -> list[Subject]:
        result = await self.session.scalars(
            select(Subject)
            .where(Subject.workspace_id == workspace_id)
            .order_by(Subject.display_name, Subject.id)
        )
        return list(result)

    async def get(
        self, workspace_id: uuid.UUID, subject_id: uuid.UUID
    ) -> Subject | None:
        return await self.session.scalar(
            select(Subject).where(
                Subject.id == subject_id,
                Subject.workspace_id == workspace_id,
            )
        )

    async def get_real_estate_vertical(self) -> Vertical | None:
        return await self.session.scalar(
            select(Vertical).where(Vertical.slug == "real_estate")
        )

    def add(self, subject: Subject) -> None:
        self.session.add(subject)

    async def delete(self, subject: Subject) -> None:
        await self.session.delete(subject)
