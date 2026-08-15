import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import AuthSession, Membership, ProfessionalProfile, User, Workspace
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
#: Namespaced so a digest from this table can never collide with, or be
#: replayed against, the share-link digests hashed elsewhere.
_REFRESH_TOKEN_HASH_PREFIX = b"homean-refresh-token-v1:\0"


def refresh_token_hash(token: str) -> str:
    """Digest a refresh token for storage and lookup.

    A plain SHA-256 is right here and a password hash would not be: these are
    256 bits of random, so there is no low-entropy secret to slow an attacker
    down over, and lookup has to stay a single indexed read.
    """

    # Request payloads are UTF-8 text, while issued opaque tokens happen to be
    # URL-safe ASCII.  Hash the boundary value as UTF-8 so malformed input is
    # still an ordinary cache miss rather than an encoding exception.
    return hashlib.sha256(
        _REFRESH_TOKEN_HASH_PREFIX + token.encode("utf-8", errors="surrogatepass")
    ).hexdigest()


class TokenClaims(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sub: uuid.UUID
    workspace_id: uuid.UUID
    #: The session this token was minted for. Revoking that session invalidates
    #: the token, which a self-contained JWT could never allow.
    sid: uuid.UUID
    type: Literal["access"]
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

    @property
    def session_lifetime(self) -> timedelta:
        return self._refresh_lifetime

    def issue_access_token(
        self, user_id: uuid.UUID, workspace_id: uuid.UUID, session_id: uuid.UUID
    ) -> tuple[str, int]:
        """Mint a short-lived access token naming the session that backs it."""

        issued_at = datetime.now(UTC)
        token = jwt.encode(
            {
                "sub": str(user_id),
                "workspace_id": str(workspace_id),
                "sid": str(session_id),
                "type": "access",
                "jti": str(uuid.uuid4()),
                "iat": issued_at,
                "exp": issued_at + self._access_lifetime,
            },
            self._secret,
            algorithm=self._algorithm,
        )
        return token, int(self._access_lifetime.total_seconds())

    @staticmethod
    def create_refresh_token() -> str:
        """An opaque bearer secret, not a JWT.

        Nothing is encoded in it: authority lives in the session row it hashes
        to, which is what makes revocation possible at all.
        """

        return secrets.token_urlsafe(32)

    def decode(
        self, token: str, expected_type: Literal["access"] = "access"
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
                        "sid",
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

        return await self._start_session(user.id, workspace.id)

    async def login(self, email: str, password: str) -> TokenPair:
        normalized_email = email.strip().lower()
        user = await self._repository.get_user_by_email(normalized_email)
        if user is None or not self._passwords.verify(password, user.password_hash):
            raise InvalidCredentialsError

        membership_context = await self._repository.get_default_membership(user.id)
        if membership_context is None:
            raise InvalidCredentialsError
        membership, workspace = membership_context
        return await self._start_session(membership.user_id, workspace.id)

    async def refresh(self, refresh_token: str) -> TokenPair:
        session = await self._repository.get_live_session(
            refresh_token_hash(refresh_token), datetime.now(UTC)
        )
        if session is None:
            # Unknown, revoked, or past its absolute expiry — all indistinguishable
            # to the caller on purpose.
            raise InvalidTokenError
        if not await self._repository.get_context(
            session.user_id, session.workspace_id
        ):
            raise InvalidCredentialsError
        access_token, expires_in = self._tokens.issue_access_token(
            session.user_id, session.workspace_id, session.id
        )
        # The same refresh token comes back and expires_at is untouched. Not
        # rotating keeps parallel dashboard refreshes from racing each other,
        # and refusing to extend is what stops continuous use outliving the
        # absolute window.
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_in=expires_in,
        )

    async def logout(self, refresh_token: str) -> None:
        """Revoke the session behind a refresh token. Idempotent by design.

        An unknown or already-revoked token is not an error: a client clearing
        its credentials must never be blocked from doing so.
        """

        session = await self._repository.get_session_by_hash(
            refresh_token_hash(refresh_token)
        )
        if session is None or session.revoked_at is not None:
            return
        session.revoked_at = datetime.now(UTC)
        await self._repository.flush()

    async def _start_session(
        self, user_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> TokenPair:
        """Open one revocable session, returning the only copy of its token."""

        raw_refresh_token = self._tokens.create_refresh_token()
        session = AuthSession(
            user_id=user_id,
            workspace_id=workspace_id,
            refresh_token_hash=refresh_token_hash(raw_refresh_token),
            expires_at=datetime.now(UTC) + self._tokens.session_lifetime,
        )
        self._repository.add(session)
        await self._repository.flush()
        access_token, expires_in = self._tokens.issue_access_token(
            user_id, workspace_id, session.id
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            access_expires_in=expires_in,
        )
