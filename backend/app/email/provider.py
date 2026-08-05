import asyncio
import logging
import smtplib
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.message import EmailMessage

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    content: bytes
    content_type: str


@dataclass(frozen=True)
class OutboundEmail:
    to_email: str
    subject: str
    html_body: str
    attachment: EmailAttachment | None = None


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
            raise ValueError("SMTP_HOST is required when EMAIL_PROVIDER=smtp")
        email = EmailMessage()
        email["To"] = message.to_email
        email["From"] = f"{self._from_name} <{self._from_email}>"
        email["Subject"] = message.subject
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

        def send_message() -> str:
            with smtplib.SMTP(self._host, self._port, timeout=30) as client:
                if self._use_tls:
                    client.starttls()
                if self._username:
                    client.login(self._username, self._password or "")
                client.send_message(email)
            return email["Message-ID"] or f"smtp-{uuid.uuid4()}"

        return await asyncio.to_thread(send_message)


class FakeEmailProvider(EmailProvider):
    def __init__(self) -> None:
        self.messages: list[OutboundEmail] = []
        self.error: Exception | None = None

    async def send(self, message: OutboundEmail) -> str:
        if self.error is not None:
            raise self.error
        self.messages.append(message)
        return f"fake-{len(self.messages)}"


def create_email_provider(settings: Settings) -> EmailProvider:
    provider = settings.email_provider.lower()
    if provider == "console":
        return ConsoleEmailProvider()
    if provider == "smtp":
        return SMTPEmailProvider(settings)
    raise ValueError(f"unsupported email provider: {settings.email_provider}")
