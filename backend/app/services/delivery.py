import hashlib
import html
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.email import EmailAttachment, EmailProvider, OutboundEmail
from app.models import (
    Report,
    ReportSend,
    ReportShareLink,
    ReportShareView,
    Visit,
)
from app.repositories import DeliveryRepository, ReviewRepository
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


class RealEstateDeliveryService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        renderer: ReportRenderer,
        email_provider: EmailProvider,
    ) -> None:
        self._repository = DeliveryRepository(session)
        self._review_repository = ReviewRepository(session)
        self._settings = settings
        self._renderer = renderer
        self._email = email_provider

    async def create_share_link(
        self,
        context: CurrentContext,
        visit_id: uuid.UUID,
        expires_at: datetime | None,
    ) -> ShareLinkResult:
        visit, report = await self._require_confirmed_report(
            context.workspace.id, visit_id, allow_sent=True
        )
        del visit
        return await self._new_share_link(context, report, expires_at)

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
            link.revoked_at = datetime.now(UTC)
            await self._repository.flush()
        return ShareLinkResult(link=link, url=self._share_url(link.token))

    async def get_public_report(
        self, token: str, user_agent: str | None, view_type: str
    ) -> PublicReport:
        row = await self._repository.get_public_link(token)
        if row is None:
            raise ResourceNotFoundError
        link, report = row
        now = datetime.now(UTC)
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
            channel=channel,
            to_email=to_email,
            status="pending" if channel == "email" else "sent",
        )
        self._repository.add(report_send)
        await self._repository.flush()

        if channel == "email":
            await self._repository.session.commit()
            try:
                pdf = await self._renderer.render_pdf(report.rendered_html or "")
                provider_message_id = await self._email.send(
                    OutboundEmail(
                        to_email=to_email or "",
                        subject="Your property showing report",
                        html_body=(
                            "<p>Your property showing report is ready.</p>"
                            f'<p><a href="{html.escape(share.url, quote=True)}">'
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
                report_send.status = "failed"
                report_send.error = f"{type(exc).__name__}: {exc}"[:4000]
                await self._repository.flush()
                await self._repository.session.commit()
                raise DeliveryUnavailableError from exc
            report_send.status = "sent"
            report_send.provider_message_id = provider_message_id

        visit.status = "sent_to_client"
        await self._repository.flush()
        return SendResult(send=report_send, visit=visit, share_url=share.url)

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
        row = await self._repository.get_visit_report(workspace_id, visit_id)
        if row is None:
            raise ResourceNotFoundError
        visit, report = row
        allowed_statuses = (
            {"confirmed", "sent_to_client"} if allow_sent else {"confirmed"}
        )
        if visit.status not in allowed_statuses or report.status != "confirmed":
            raise ResourceConflictError("showing must be confirmed before delivery")
        if not report.rendered_html:
            branding = await self._review_repository.get_branding(workspace_id)
            report.rendered_html = await self._renderer.render_html(
                report.content, branding
            )
            await self._repository.flush()
        return visit, report

    def _share_url(self, token: str) -> str:
        return f"{self._settings.public_base_url.rstrip('/')}/r/{token}"
