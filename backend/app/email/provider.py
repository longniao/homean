import asyncio
import logging
import smtplib
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.message import EmailMessage
from enum import StrEnum

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    content: bytes
    content_type: str


@dataclass(frozen=True)
class OutboundEmail:
    message_id: str
    to_email: str
    subject: str
    html_body: str
    attachment: EmailAttachment | None = None


class EmailDeliveryOutcome(StrEnum):
    """The provider's knowledge about whether SMTP accepted the message."""

    DEFINITIVE_FAILURE = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"


class EmailDeliveryError(RuntimeError):
    """An email provider error with an explicit acceptance outcome."""

    def __init__(self, detail: str, *, outcome: EmailDeliveryOutcome) -> None:
        super().__init__(detail)
        self.outcome = outcome


class EmailProvider(ABC):
    @abstractmethod
    async def send(self, message: OutboundEmail) -> str:
        """Send an email and return a provider message identifier."""


class ConsoleEmailProvider(EmailProvider):
    async def send(self, message: OutboundEmail) -> str:
        message_id = f"console-{uuid.uuid4()}"
        logger.info(
            "development email",
            extra={
                "message_id": message_id,
                "to_email": message.to_email,
                "subject": message.subject,
                "has_attachment": message.attachment is not None,
            },
        )
        return message_id


class SMTPEmailProvider(EmailProvider):
    def __init__(self, settings: Settings) -> None:
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._username = settings.smtp_username
        self._password = (
            settings.smtp_password.get_secret_value()
            if settings.smtp_password is not None
            else None
        )
        self._from_email = settings.smtp_from_email
        self._from_name = settings.smtp_from_name
        self._use_tls = settings.smtp_use_tls

    async def send(self, message: OutboundEmail) -> str:
        if not self._host:
            raise EmailDeliveryError(
                "SMTP_HOST is required when EMAIL_PROVIDER=smtp",
                outcome=EmailDeliveryOutcome.DEFINITIVE_FAILURE,
            )
        try:
            email = self._build_message(message)
        except Exception as exc:
            raise EmailDeliveryError(
                f"could not build email: {exc}",
                outcome=EmailDeliveryOutcome.DEFINITIVE_FAILURE,
            ) from exc

        def send_message() -> str:
            try:
                client = smtplib.SMTP(self._host, self._port, timeout=30)
            except Exception as exc:
                raise EmailDeliveryError(
                    f"could not connect to SMTP provider: {exc}",
                    outcome=EmailDeliveryOutcome.DEFINITIVE_FAILURE,
                ) from exc

            try:
                if self._use_tls:
                    try:
                        client.starttls()
                    except Exception as exc:
                        raise EmailDeliveryError(
                            f"SMTP TLS setup failed: {exc}",
                            outcome=EmailDeliveryOutcome.DEFINITIVE_FAILURE,
                        ) from exc
                if self._username:
                    try:
                        client.login(self._username, self._password or "")
                    except Exception as exc:
                        raise EmailDeliveryError(
                            f"SMTP authentication failed: {exc}",
                            outcome=EmailDeliveryOutcome.DEFINITIVE_FAILURE,
                        ) from exc
                try:
                    client.send_message(email)
                except (
                    smtplib.SMTPRecipientsRefused,
                    smtplib.SMTPSenderRefused,
                    smtplib.SMTPDataError,
                ) as exc:
                    # These responses mean the server rejected the envelope or
                    # message.  No accepted message should be retried as an
                    # unknown delivery.
                    raise EmailDeliveryError(
                        f"SMTP rejected the message: {exc}",
                        outcome=EmailDeliveryOutcome.DEFINITIVE_FAILURE,
                    ) from exc
                except Exception as exc:
                    # A disconnect/timeout can happen after DATA was accepted.
                    # SMTP has no portable idempotency key, so retrying here
                    # could deliver a duplicate.
                    raise EmailDeliveryError(
                        f"SMTP send outcome is unknown: {exc}",
                        outcome=EmailDeliveryOutcome.OUTCOME_UNKNOWN,
                    ) from exc
            finally:
                # A successful DATA response is already a successful send;
                # QUIT may itself time out and must not turn it into a retry.
                try:
                    client.quit()
                except Exception:
                    pass
            return message.message_id

        return await asyncio.to_thread(send_message)

    def _build_message(self, message: OutboundEmail) -> EmailMessage:
        email = EmailMessage()
        email["To"] = message.to_email
        email["From"] = f"{self._from_name} <{self._from_email}>"
        email["Subject"] = message.subject
        email["Message-ID"] = message.message_id
        email.set_content("Your Kawu showing report is available in the attached link.")
        email.add_alternative(message.html_body, subtype="html")
        if message.attachment is not None:
            main_type, sub_type = message.attachment.content_type.split("/", 1)
            email.add_attachment(
                message.attachment.content,
                maintype=main_type,
                subtype=sub_type,
                filename=message.attachment.filename,
            )
        return email


class FakeEmailProvider(EmailProvider):
    def __init__(self) -> None:
        self.messages: list[OutboundEmail] = []
        self.attempts: list[OutboundEmail] = []
        self.error: Exception | None = None
        self.error_after_accept: Exception | None = None

    async def send(self, message: OutboundEmail) -> str:
        self.attempts.append(message)
        if self.error is not None:
            raise self.error
        self.messages.append(message)
        if self.error_after_accept is not None:
            raise self.error_after_accept
        return f"fake-{len(self.messages)}"


def create_email_provider(settings: Settings) -> EmailProvider:
    provider = settings.email_provider.lower()
    if provider == "console":
        return ConsoleEmailProvider()
    if provider == "smtp":
        return SMTPEmailProvider(settings)
    raise ValueError(f"unsupported email provider: {settings.email_provider}")
