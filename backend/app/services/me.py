from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProfessionalProfile, Vertical
from app.repositories import AuthRepository
from app.services.context import CurrentContext


@dataclass(frozen=True)
class MeResult:
    context: CurrentContext
    profile: ProfessionalProfile
    vertical: Vertical


class MeService:
    def __init__(self, session: AsyncSession) -> None:
        self._repository = AuthRepository(session)

    async def get(self, context: CurrentContext) -> MeResult | None:
        profile_context = await self._repository.get_profile(
            context.membership.id, context.workspace.id
        )
        if profile_context is None:
            return None
        profile, vertical = profile_context
        return MeResult(context=context, profile=profile, vertical=vertical)

    async def update(
        self, context: CurrentContext, name: str | None
    ) -> MeResult | None:
        context.user.name = name
        await self._repository.flush()
        return await self.get(context)
