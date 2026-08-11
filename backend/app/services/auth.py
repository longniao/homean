import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import Membership, ProfessionalProfile, User, Workspace
from app.repositories import AuthRepository
from app.services.billing import BillingService, StripeBillingProvider
from app.services.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidTokenError,
    VerticalNotSeededError,
)

REAL_ESTATE_VERTICAL = "real_estate"
BUYERS_AGENT_ROLE = "buyers_agent"


class TokenClaims(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sub: uuid.UUID
    workspace_id: uuid.UUID
    type: Literal["access", "refresh"]
    jti: uuid.UUID
    iat: datetime
    exp: datetime


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int


class TokenService:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret.get_secret_value()
        self._algorithm = settings.jwt_algorithm
        self._access_lifetime = timedelta(minutes=settings.access_token_minutes)
        self._refresh_lifetime = timedelta(days=settings.refresh_token_days)

    def create_pair(self, user_id: uuid.UUID, workspace_id: uuid.UUID) -> TokenPair:
        return TokenPair(
            access_token=self._encode(
                user_id, workspace_id, "access", self._access_lifetime
            ),
            refresh_token=self._encode(
                user_id, workspace_id, "refresh", self._refresh_lifetime
            ),
            access_expires_in=int(self._access_lifetime.total_seconds()),
        )

    def decode(
        self, token: str, expected_type: Literal["access", "refresh"]
    ) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={
                    "require": [
                        "sub",
                        "workspace_id",
                        "type",
                        "jti",
                        "iat",
                        "exp",
                    ]
                },
            )
            claims = TokenClaims.model_validate(payload)
        except (jwt.PyJWTError, ValueError) as exc:
            raise InvalidTokenError from exc
        if claims.type != expected_type:
            raise InvalidTokenError
        return claims

    def _encode(
        self,
        user_id: uuid.UUID,
        workspace_id: uuid.UUID,
        token_type: Literal["access", "refresh"],
        lifetime: timedelta,
    ) -> str:
        issued_at = datetime.now(UTC)
        return jwt.encode(
            {
                "sub": str(user_id),
                "workspace_id": str(workspace_id),
                "type": token_type,
                "jti": str(uuid.uuid4()),
                "iat": issued_at,
                "exp": issued_at + lifetime,
            },
            self._secret,
            algorithm=self._algorithm,
        )


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._repository = AuthRepository(session)
        self._passwords = PasswordHash.recommended()
        self._tokens = TokenService(settings)
        self._billing = BillingService(
            session, settings, StripeBillingProvider(settings)
        )

    async def signup(self, email: str, password: str) -> TokenPair:
        normalized_email = email.strip().lower()
        if await self._repository.get_user_by_email(normalized_email):
            raise EmailAlreadyRegisteredError

        vertical = await self._repository.get_vertical_by_slug(REAL_ESTATE_VERTICAL)
        if vertical is None:
            raise VerticalNotSeededError

        user = User(
            email=normalized_email,
            password_hash=self._passwords.hash(password),
        )
        workspace = Workspace(
            name=f"{normalized_email.split('@', maxsplit=1)[0]}'s Workspace",
            language="en",
        )
        self._repository.add(user, workspace)
        await self._repository.flush()

        membership = Membership(user_id=user.id, workspace_id=workspace.id)
        self._repository.add(membership)
        await self._repository.flush()

        profile = ProfessionalProfile(
            membership_id=membership.id,
            vertical_id=vertical.id,
            role=BUYERS_AGENT_ROLE,
        )
        self._repository.add(profile)
        await self._repository.flush()
        await self._billing.ensure_trial(workspace.id)
        await self._repository.flush()

        return self._tokens.create_pair(user.id, workspace.id)

    async def login(self, email: str, password: str) -> TokenPair:
        normalized_email = email.strip().lower()
        user = await self._repository.get_user_by_email(normalized_email)
        if user is None or not self._passwords.verify(password, user.password_hash):
            raise InvalidCredentialsError

        membership_context = await self._repository.get_default_membership(user.id)
        if membership_context is None:
            raise InvalidCredentialsError
        membership, workspace = membership_context
        return self._tokens.create_pair(membership.user_id, workspace.id)

    async def refresh(self, refresh_token: str) -> TokenPair:
        claims = self._tokens.decode(refresh_token, "refresh")
        if not await self._repository.get_context(claims.sub, claims.workspace_id):
            raise InvalidCredentialsError
        return self._tokens.create_pair(claims.sub, claims.workspace_id)
