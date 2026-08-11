import hashlib
import hmac
import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Report, ReportSend, ReportShareLink, ReportShareView, Visit

_SHARE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_SHARE_TOKEN_HASH_PREFIX = b"homean-share-token-v1:\0"
_LEGACY_SHARE_TOKEN_HASH_PREFIX = b"kawu-share-token-v1:\0"


def share_token_lookup_hash(token: str) -> str:
    """Return the lookup hash used for newly issued Homean links."""

    return hashlib.sha256(_SHARE_TOKEN_HASH_PREFIX + token.encode("ascii")).hexdigest()


def legacy_share_token_lookup_hash(token: str) -> str:
    """Return the pre-rename hash for links already stored in production."""

    return hashlib.sha256(
        _LEGACY_SHARE_TOKEN_HASH_PREFIX + token.encode("ascii")
    ).hexdigest()


def share_token_lookup_hashes(token: str) -> tuple[str, str]:
    """Return both accepted namespaces without weakening token validation.

    ``token_lookup_hash`` is indexed and stores only one digest per link.  A
    lookup therefore checks the new namespace and the historical Kawu
    namespace in one indexed ``IN`` query, then still verifies the submitted
    token with ``compare_digest`` below.
    """

    return (share_token_lookup_hash(token), legacy_share_token_lookup_hash(token))


class DeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, *entities: object) -> None:
        self.session.add_all(entities)

    async def flush(self) -> None:
        await self.session.flush()

    async def get_visit_report(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> tuple[Visit, Report] | None:
        row = await self.session.execute(
            select(Visit, Report)
            .join(Report, Report.visit_id == Visit.id)
            .where(
                Visit.id == visit_id,
                Visit.workspace_id == workspace_id,
            )
            .order_by(Report.created_at.desc(), Report.id.desc())
            .limit(1)
        )
        return row.tuples().one_or_none()

    async def get_visit_for_update(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> Visit | None:
        """Acquire the visit lifecycle lock before any report lock."""

        return await self.session.scalar(
            select(Visit)
            .where(
                Visit.id == visit_id,
                Visit.workspace_id == workspace_id,
            )
            .with_for_update()
        )

    async def get_report_for_update(
        self, workspace_id: uuid.UUID, report_id: uuid.UUID
    ) -> Report | None:
        """Lock a report after its parent visit has been locked."""

        statement = (
            select(Report)
            .join(Visit, Visit.id == Report.visit_id)
            .where(Report.id == report_id, Visit.workspace_id == workspace_id)
            .execution_options(populate_existing=True)
            .with_for_update(of=Report)
        )
        return await self.session.scalar(statement)

    async def get_email_send_for_update(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> ReportSend | None:
        """Load the one logical email delivery for a visit under a lock.

        The caller must decide whether a pending row is still within its
        delivery lease. Taking this lock before that decision prevents two
        readers from both trying to recover the same stale attempt.
        """

        return await self.session.scalar(
            select(ReportSend)
            .where(
                ReportSend.workspace_id == workspace_id,
                ReportSend.visit_id == visit_id,
                ReportSend.channel == "email",
            )
            .order_by(ReportSend.created_at.desc(), ReportSend.id.desc())
            .limit(1)
            .with_for_update()
        )

    async def get_send_for_update(
        self,
        workspace_id: uuid.UUID,
        visit_id: uuid.UUID,
        send_id: uuid.UUID,
    ) -> ReportSend | None:
        return await self.session.scalar(
            select(ReportSend)
            .where(
                ReportSend.id == send_id,
                ReportSend.workspace_id == workspace_id,
                ReportSend.visit_id == visit_id,
            )
            .with_for_update()
        )

    async def get_link(
        self,
        workspace_id: uuid.UUID,
        visit_id: uuid.UUID,
        link_id: uuid.UUID,
    ) -> ReportShareLink | None:
        return await self.session.scalar(
            select(ReportShareLink)
            .join(Report, Report.id == ReportShareLink.report_id)
            .join(Visit, Visit.id == Report.visit_id)
            .where(
                ReportShareLink.id == link_id,
                ReportShareLink.workspace_id == workspace_id,
                Visit.id == visit_id,
                Visit.workspace_id == workspace_id,
            )
        )

    async def get_public_link(
        self, token: str
    ) -> tuple[ReportShareLink, Report] | None:
        if not isinstance(token, str) or not _SHARE_TOKEN_PATTERN.fullmatch(token):
            return None
        lookup_hashes = share_token_lookup_hashes(token)
        row = await self.session.execute(
            select(ReportShareLink, Report)
            .join(Report, Report.id == ReportShareLink.report_id)
            .where(ReportShareLink.token_lookup_hash.in_(lookup_hashes))
            .limit(1)
        )
        candidate = row.tuples().first()
        if candidate is None:
            return None
        link, report = candidate
        return (link, report) if hmac.compare_digest(link.token, token) else None

    async def get_visit(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> Visit | None:
        return await self.session.scalar(
            select(Visit).where(
                Visit.id == visit_id,
                Visit.workspace_id == workspace_id,
            )
        )

    async def list_share_links_with_open_counts(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> list[tuple[ReportShareLink, int]]:
        rows = await self.session.execute(
            select(ReportShareLink, func.count(ReportShareView.id))
            .join(Report, Report.id == ReportShareLink.report_id)
            .join(Visit, Visit.id == Report.visit_id)
            .outerjoin(
                ReportShareView,
                ReportShareView.share_link_id == ReportShareLink.id,
            )
            .where(
                ReportShareLink.workspace_id == workspace_id,
                Visit.id == visit_id,
                Visit.workspace_id == workspace_id,
            )
            .group_by(ReportShareLink.id)
            .order_by(ReportShareLink.created_at.desc(), ReportShareLink.id.desc())
        )
        return [(link, int(open_count)) for link, open_count in rows.tuples()]

    async def list_sends(
        self, workspace_id: uuid.UUID, visit_id: uuid.UUID
    ) -> list[ReportSend]:
        rows = await self.session.scalars(
            select(ReportSend)
            .where(
                ReportSend.workspace_id == workspace_id,
                ReportSend.visit_id == visit_id,
            )
            .order_by(ReportSend.created_at.desc(), ReportSend.id.desc())
        )
        return list(rows)
