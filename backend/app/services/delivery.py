import hashlib
import html
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.email import (
    EmailAttachment,
    EmailDeliveryError,
    EmailDeliveryOutcome,
    EmailProvider,
    OutboundEmail,
)
from app.models import (
    Report,
    ReportSend,
    ReportShareLink,
    ReportShareView,
    Visit,
)
from app.repositories import DeliveryRepository, ReviewRepository
from app.repositories.delivery import share_token_lookup_hash
from app.services.billing import BillingService
from app.services.context import CurrentContext
from app.services.exceptions import (
    DeliveryUnavailableError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from app.services.renderer import ReportRenderer


@dataclass(frozen=True)
class ShareLinkResult:
    link: ReportShareLink
    url: str


@dataclass(frozen=True)
class PublicReport:
    link: ReportShareLink
    report: Report


@dataclass(frozen=True)
class SendResult:
    send: ReportSend
    visit: Visit
    share_url: str


@dataclass(frozen=True)
class DeliveryShareLink:
    link: ReportShareLink
    url: str
    open_count: int


@dataclass(frozen=True)
class DeliverySummary:
    share_links: list[DeliveryShareLink]
    sends: list[ReportSend]


class EmailDeliveryRetryBlockedError(ResourceConflictError):
    """An email row is not safe for an automatic second provider call."""

    code = "email_delivery_retry_blocked"


class EmailDeliveryOutcomeUnknownError(EmailDeliveryRetryBlockedError):
    code = "email_delivery_outcome_unknown"

    def __init__(self) -> None:
        super().__init__(
            "email delivery outcome is unknown; do not retry automatically; "
            "use the existing private link"
        )


class EmailDeliveryInProgressError(EmailDeliveryRetryBlockedError):
    code = "email_delivery_in_progress"

    def __init__(self) -> None:
        super().__init__("email delivery is already in progress; do not retry")


class EmailDeliveryRecipientMismatchError(EmailDeliveryRetryBlockedError):
    code = "email_delivery_recipient_mismatch"

    def __init__(self) -> None:
        super().__init__("a retry must use the original email recipient")


class RealEstateDeliveryService:
    _STALE_PENDING_ERROR = (
        "The email delivery attempt lease expired before its outcome was recorded. "
        "The delivery outcome is unknown; do not retry automatically; use the "
        "existing private link."
    )

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        renderer: ReportRenderer,
        email_provider: EmailProvider,
        billing: BillingService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = DeliveryRepository(session)
        self._review_repository = ReviewRepository(session)
        self._settings = settings
        self._renderer = renderer
        self._email = email_provider
        self._billing = billing
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create_share_link(
        self,
        context: CurrentContext,
        visit_id: uuid.UUID,
        expires_at: datetime | None,
    ) -> ShareLinkResult:
        await self._billing.require_active(context)
        visit, report = await self._require_confirmed_report(
            context.workspace.id, visit_id, allow_sent=True
        )
        del visit
        return await self._new_share_link(context, report, expires_at)

    async def get_delivery(
        self, context: CurrentContext, visit_id: uuid.UUID
    ) -> DeliverySummary:
        if (
            await self._repository.get_visit_for_update(context.workspace.id, visit_id)
            is None
        ):
            raise ResourceNotFoundError
        email_send = await self._repository.get_email_send_for_update(
            context.workspace.id, visit_id
        )
        await self._recover_stale_pending(email_send)
        links = await self._repository.list_share_links_with_open_counts(
            context.workspace.id, visit_id
        )
        sends = await self._repository.list_sends(context.workspace.id, visit_id)
        return DeliverySummary(
            share_links=[
                DeliveryShareLink(
                    link=link,
                    url=self._share_url(link.token),
                    open_count=open_count,
                )
                for link, open_count in links
            ],
            sends=sends,
        )

    async def revoke_share_link(
        self,
        context: CurrentContext,
        visit_id: uuid.UUID,
        link_id: uuid.UUID,
    ) -> ShareLinkResult:
        link = await self._repository.get_link(context.workspace.id, visit_id, link_id)
        if link is None:
            raise ResourceNotFoundError
        if link.revoked_at is None:
            link.revoked_at = self._now()
            await self._repository.flush()
        return ShareLinkResult(link=link, url=self._share_url(link.token))

    async def get_public_report(
        self, token: str, user_agent: str | None, view_type: str
    ) -> PublicReport:
        row = await self._repository.get_public_link(token)
        if row is None:
            raise ResourceNotFoundError
        link, report = row
        now = self._now()
        if link.revoked_at is not None or (
            link.expires_at is not None and link.expires_at <= now
        ):
            raise ResourceNotFoundError
        if report.status != "confirmed" or not report.rendered_html:
            raise ResourceNotFoundError
        self._repository.add(
            ReportShareView(
                share_link_id=link.id,
                user_agent_hash=hashlib.sha256(
                    (user_agent or "").encode("utf-8")
                ).hexdigest(),
                view_type=view_type,
            )
        )
        await self._repository.flush()
        return PublicReport(link=link, report=report)

    async def render_public_pdf(self, report: Report) -> bytes:
        return await self._renderer.render_pdf(report.rendered_html or "")

    async def send_report(
        self,
        context: CurrentContext,
        visit_id: uuid.UUID,
        channel: str,
        to_email: str | None,
    ) -> SendResult:
        await self._billing.require_active(context)
        if channel == "link_only":
            return await self._send_link_only(context, visit_id)
        return await self._send_email(context, visit_id, to_email)

    async def _send_link_only(
        self, context: CurrentContext, visit_id: uuid.UUID
    ) -> SendResult:
        visit, report = await self._require_confirmed_report(
            context.workspace.id, visit_id
        )
        share = await self._new_share_link(context, report, None)
        report_send = ReportSend(
            workspace_id=context.workspace.id,
            visit_id=visit.id,
            report_id=report.id,
            share_link_id=share.link.id,
            sent_by=context.user.id,
            channel="link_only",
            to_email=None,
            status="sent",
        )
        self._repository.add(report_send)
        visit.status = "sent_to_client"
        await self._repository.flush()
        return SendResult(send=report_send, visit=visit, share_url=share.url)

    async def _send_email(
        self,
        context: CurrentContext,
        visit_id: uuid.UUID,
        to_email: str | None,
    ) -> SendResult:
        if not to_email:
            raise ValueError("to_email is required for email delivery")
        visit, report = await self._require_confirmed_report(
            context.workspace.id, visit_id
        )
        report_send = await self._repository.get_email_send_for_update(
            context.workspace.id, visit_id
        )
        now = self._now()

        if report_send is None:
            share = await self._new_share_link(context, report, None)
            send_id = uuid.uuid4()
            report_send = ReportSend(
                id=send_id,
                workspace_id=context.workspace.id,
                visit_id=visit.id,
                report_id=report.id,
                share_link_id=share.link.id,
                sent_by=context.user.id,
                channel="email",
                to_email=to_email,
                status="pending",
                message_id=self._message_id(send_id),
                attempt_count=0,
            )
            self._repository.add(report_send)
            share_link = share.link
        else:
            if report_send.status == "outcome_unknown":
                raise EmailDeliveryOutcomeUnknownError
            if report_send.status == "pending":
                if await self._recover_stale_pending(report_send, now=now):
                    raise EmailDeliveryOutcomeUnknownError
                raise EmailDeliveryInProgressError
            if report_send.status == "sent":
                raise ResourceConflictError("report has already been delivered")
            if (report_send.to_email or "").casefold() != to_email.casefold():
                raise EmailDeliveryRecipientMismatchError
            if report_send.message_id is None:
                report_send.message_id = self._message_id(report_send.id)
            share_link = await self._repository.get_link(
                context.workspace.id, visit_id, report_send.share_link_id
            )
            if share_link is None:
                raise ResourceConflictError(
                    "the original private report link is missing"
                )
            if share_link.revoked_at is not None or (
                share_link.expires_at is not None and share_link.expires_at <= now
            ):
                raise ResourceConflictError(
                    "the original private report link is no longer active"
                )
            report_send.status = "pending"

        report_send.attempt_count = (report_send.attempt_count or 0) + 1
        report_send.last_attempt_at = now
        report_send.error = None
        await self._repository.flush()
        # This durable boundary is essential.  If the process dies after the
        # SMTP call, the next request sees the same pending attempt/link and
        # cannot create a second email or link.
        await self._repository.session.commit()

        try:
            pdf = await self._renderer.render_pdf(report.rendered_html or "")
        except Exception as exc:
            await self._finish_email(
                context.workspace.id,
                visit_id,
                report_send.id,
                status="failed",
                error=f"{type(exc).__name__}: {exc}"[:4000],
            )
            raise DeliveryUnavailableError from exc

        share_url = self._share_url(share_link.token)
        try:
            provider_message_id = await self._email.send(
                OutboundEmail(
                    message_id=report_send.message_id or "",
                    to_email=report_send.to_email or "",
                    subject="Your property showing report",
                    html_body=(
                        "<p>Your property showing report is ready.</p>"
                        f'<p><a href="{html.escape(share_url, quote=True)}">'
                        "Open the report</a></p>"
                    ),
                    attachment=EmailAttachment(
                        filename="showing-report.pdf",
                        content=pdf,
                        content_type="application/pdf",
                    ),
                )
            )
        except Exception as exc:
            outcome = (
                exc.outcome
                if isinstance(exc, EmailDeliveryError)
                else EmailDeliveryOutcome.OUTCOME_UNKNOWN
            )
            await self._finish_email(
                context.workspace.id,
                visit_id,
                report_send.id,
                status=outcome.value,
                error=f"{type(exc).__name__}: {exc}"[:4000],
            )
            if outcome == EmailDeliveryOutcome.OUTCOME_UNKNOWN:
                raise EmailDeliveryOutcomeUnknownError from exc
            raise DeliveryUnavailableError from exc

        final_send, final_visit = await self._finish_email(
            context.workspace.id,
            visit_id,
            report_send.id,
            status="sent",
            provider_message_id=provider_message_id,
        )
        return SendResult(
            send=final_send,
            visit=final_visit,
            share_url=self._share_url(share_link.token),
        )

    async def _finish_email(
        self,
        workspace_id: uuid.UUID,
        visit_id: uuid.UUID,
        send_id: uuid.UUID,
        *,
        status: str,
        provider_message_id: str | None = None,
        error: str | None = None,
    ) -> tuple[ReportSend, Visit]:
        visit = await self._repository.get_visit_for_update(workspace_id, visit_id)
        report_send = await self._repository.get_send_for_update(
            workspace_id, visit_id, send_id
        )
        if visit is None or report_send is None:
            raise ResourceNotFoundError
        report_send.status = status
        report_send.provider_message_id = provider_message_id
        report_send.error = error
        if status == "sent":
            visit.status = "sent_to_client"
        await self._repository.flush()
        await self._repository.session.commit()
        return report_send, visit

    def _message_id(self, send_id: uuid.UUID) -> str:
        domain = self._settings.smtp_from_email.rpartition("@")[2] or "homean.com"
        if domain.casefold() == "kawu.local":
            domain = "homean.com"
        return f"<homean-report-{send_id}@{domain}>"

    def _now(self) -> datetime:
        return self._clock()

    def _is_stale_pending(self, report_send: ReportSend, now: datetime) -> bool:
        lease_started_at = report_send.last_attempt_at or report_send.created_at
        return (
            lease_started_at
            + timedelta(seconds=self._settings.email_pending_lease_seconds)
            <= now
        )

    async def _recover_stale_pending(
        self, report_send: ReportSend | None, *, now: datetime | None = None
    ) -> bool:
        if report_send is None or report_send.status != "pending":
            return False
        if not self._is_stale_pending(
            report_send, now if now is not None else self._now()
        ):
            return False
        report_send.status = "outcome_unknown"
        report_send.error = self._STALE_PENDING_ERROR
        await self._repository.flush()
        await self._repository.session.commit()
        return True

    async def _new_share_link(
        self,
        context: CurrentContext,
        report: Report,
        expires_at: datetime | None,
    ) -> ShareLinkResult:
        link = ReportShareLink(
            workspace_id=context.workspace.id,
            report_id=report.id,
            created_by=context.user.id,
            token=secrets.token_urlsafe(16),
            expires_at=expires_at,
        )
        link.token_lookup_hash = share_token_lookup_hash(link.token)
        self._repository.add(link)
        await self._repository.flush()
        return ShareLinkResult(link=link, url=self._share_url(link.token))

    async def _require_confirmed_report(
        self,
        workspace_id: uuid.UUID,
        visit_id: uuid.UUID,
        *,
        allow_sent: bool = False,
    ) -> tuple[Visit, Report]:
        # Delivery and report editing share one lock order: visit first,
        # report second.  The report is looked up once to identify the row,
        # then reloaded under its row lock so rendering/sending always uses
        # the latest committed content.
        visit = await self._repository.get_visit_for_update(workspace_id, visit_id)
        if visit is None:
            raise ResourceNotFoundError
        row = await self._repository.get_visit_report(workspace_id, visit_id)
        if row is None:
            raise ResourceNotFoundError
        _, report = row
        report = await self._repository.get_report_for_update(workspace_id, report.id)
        if report is None:
            raise ResourceNotFoundError
        allowed_statuses = (
            {"confirmed", "sent_to_client"} if allow_sent else {"confirmed"}
        )
        if visit.status not in allowed_statuses or report.status != "confirmed":
            raise ResourceConflictError("showing must be confirmed before delivery")
        if not report.rendered_html:
            branding = await self._review_repository.get_branding(workspace_id)
            subject = await self._review_repository.get_subject(
                workspace_id, visit.subject_id
            )
            report.rendered_html = await self._renderer.render_html(
                report.content,
                branding,
                consent_ack=visit.consent_ack,
                subject=subject,
                toured_on=visit.started_at,
                timezone=visit.capture_timezone,
            )
            await self._repository.flush()
        return visit, report

    def _share_url(self, token: str) -> str:
        return f"{self._settings.public_base_url.rstrip('/')}/r/{token}"
