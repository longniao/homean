import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Membership,
    ProfessionalProfile,
    User,
    Vertical,
    Workspace,
)


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email))

    async def get_vertical_by_slug(self, slug: str) -> Vertical | None:
        return await self.session.scalar(select(Vertical).where(Vertical.slug == slug))

    async def get_default_membership(
        self, user_id: uuid.UUID
    ) -> tuple[Membership, Workspace] | None:
        result = await self.session.execute(
            select(Membership, Workspace)
            .join(Workspace, Workspace.id == Membership.workspace_id)
            .where(Membership.user_id == user_id)
            .order_by(Membership.created_at)
            .limit(1)
        )
        return result.tuples().one_or_none()

    async def get_context(
        self, user_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> tuple[User, Workspace, Membership] | None:
        result = await self.session.execute(
            select(User, Workspace, Membership)
            .join(Membership, Membership.user_id == User.id)
            .join(Workspace, Workspace.id == Membership.workspace_id)
            .where(
                User.id == user_id,
                Membership.workspace_id == workspace_id,
            )
        )
        return result.tuples().one_or_none()

    async def get_profile(
        self, membership_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> tuple[ProfessionalProfile, Vertical] | None:
        result = await self.session.execute(
            select(ProfessionalProfile, Vertical)
            .join(Vertical, Vertical.id == ProfessionalProfile.vertical_id)
            .join(Membership, Membership.id == ProfessionalProfile.membership_id)
            .where(
                ProfessionalProfile.membership_id == membership_id,
                Membership.workspace_id == workspace_id,
            )
        )
        return result.tuples().one_or_none()

    def add(self, *entities: object) -> None:
        self.session.add_all(entities)

    async def flush(self) -> None:
        await self.session.flush()
