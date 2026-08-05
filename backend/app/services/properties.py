import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subject
from app.repositories import PropertyRepository
from app.schemas.properties import PropertyCreate, PropertyUpdate
from app.services.context import CurrentContext
from app.services.exceptions import (
    DomainValidationError,
    ResourceConflictError,
    ResourceNotFoundError,
    VerticalNotSeededError,
)


class RealEstatePropertyService:
    def __init__(self, session: AsyncSession) -> None:
        self._repository = PropertyRepository(session)

    async def list_properties(self, context: CurrentContext) -> list[Subject]:
        return await self._repository.list(context.workspace.id)

    async def get_property(
        self, context: CurrentContext, subject_id: uuid.UUID
    ) -> Subject:
        subject = await self._repository.get(context.workspace.id, subject_id)
        if subject is None:
            raise ResourceNotFoundError
        return subject

    async def create_property(
        self, context: CurrentContext, payload: PropertyCreate
    ) -> Subject:
        vertical = await self._repository.get_real_estate_vertical()
        if vertical is None:
            raise VerticalNotSeededError
        subject = Subject(
            workspace_id=context.workspace.id,
            vertical_id=vertical.id,
            subject_type="property",
            display_name=payload.display_name.strip(),
            location=payload.address.strip(),
            attributes=payload.attributes.model_dump(exclude_none=True),
        )
        self._repository.add(subject)
        await self._repository.session.flush()
        return subject

    async def update_property(
        self,
        context: CurrentContext,
        subject_id: uuid.UUID,
        payload: PropertyUpdate,
    ) -> Subject:
        changes = payload.model_dump(exclude_unset=True)
        for required_field in ("display_name", "address"):
            if changes.get(required_field) is None and required_field in changes:
                raise DomainValidationError(f"{required_field} cannot be null")
        subject = await self._repository.get(context.workspace.id, subject_id)
        if subject is None:
            raise ResourceNotFoundError
        if "display_name" in changes:
            subject.display_name = changes["display_name"].strip()
        if "address" in changes:
            subject.location = changes["address"].strip()
        if payload.attributes is not None:
            subject.attributes = {
                **subject.attributes,
                **payload.attributes.model_dump(exclude_unset=True),
            }
        await self._repository.session.flush()
        await self._repository.session.refresh(subject)
        return subject

    async def delete_property(
        self, context: CurrentContext, subject_id: uuid.UUID
    ) -> None:
        try:
            subject = await self._repository.get(context.workspace.id, subject_id)
            if subject is None:
                raise ResourceNotFoundError
            await self._repository.delete(subject)
            await self._repository.session.flush()
        except IntegrityError as exc:
            await self._repository.session.rollback()
            raise ResourceConflictError("property is used by a showing") from exc
