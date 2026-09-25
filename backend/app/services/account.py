"""Whole-account deletion, as App Store and Play policies require.

Immediate and irreversible: object storage is emptied first so a failure
there leaves the database intact and the request retryable, then the
workspace cascade removes every row and the user record goes last.
"""

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Membership,
    RawMedia,
    User,
    Visit,
    Workspace,
    WorkspaceBranding,
    WorkspaceSubscription,
)
from app.services.billing import BillingProvider, BillingService
from app.services.context import CurrentContext
from app.services.exceptions import InvalidCredentialsError
from app.storage.provider import StorageProvider

logger = logging.getLogger(__name__)


class AccountDeletionService:
    def __init__(
        self,
        session: AsyncSession,
        storage: StorageProvider,
        billing_provider: BillingProvider,
    ) -> None:
        self._session = session
        self._storage = storage
        self._billing_provider = billing_provider
        self._passwords = PasswordHash.recommended()

    async def delete(self, context: CurrentContext, password: str) -> None:
        if not self._passwords.verify(password, context.user.password_hash):
            raise InvalidCredentialsError

        user_id = context.user.id
        workspace_ids = list(
            await self._session.scalars(
                select(Membership.workspace_id).where(Membership.user_id == user_id)
            )
        )

        for workspace_id in workspace_ids:
            await self._cancel_billing(workspace_id)
            await self._purge_objects(workspace_id)

        # Workspace rows cascade to visits, media, reports, sessions and the
        # rest; the RESTRICT created_by links to the user are gone by the time
        # the user row itself is removed.
        for workspace_id in workspace_ids:
            await self._session.execute(
                delete(Workspace).where(Workspace.id == workspace_id)
            )
        await self._session.execute(delete(User).where(User.id == user_id))
        await self._session.flush()

        logger.info(
            "account deleted",
            extra={
                "account_ref": hashlib.sha256(user_id.bytes).hexdigest()[:16],
                "workspaces": len(workspace_ids),
                "deleted_at": datetime.now(UTC).isoformat(),
            },
        )

    async def _cancel_billing(self, workspace_id: uuid.UUID) -> None:
        subscription = await self._session.scalar(
            select(WorkspaceSubscription).where(
                WorkspaceSubscription.workspace_id == workspace_id
            )
        )
        if subscription is None or subscription.stripe_subscription_id is None:
            return
        if not BillingService.has_non_terminal_subscription(subscription):
            return
        await self._billing_provider.cancel_subscription(
            subscription.stripe_subscription_id
        )

    async def _purge_objects(self, workspace_id: uuid.UUID) -> None:
        media_keys = await self._session.scalars(
            select(RawMedia.object_key)
            .join(Visit, Visit.id == RawMedia.visit_id)
            .where(Visit.workspace_id == workspace_id)
        )
        logo_keys = await self._session.scalars(
            select(WorkspaceBranding.logo_key).where(
                WorkspaceBranding.workspace_id == workspace_id,
                WorkspaceBranding.logo_key.is_not(None),
            )
        )
        for object_key in {*media_keys, *logo_keys}:
            if object_key:
                await self._storage.delete_object(object_key)
