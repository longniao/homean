from app.email.provider import (
    ConsoleEmailProvider,
    EmailAttachment,
    EmailDeliveryError,
    EmailDeliveryOutcome,
    EmailProvider,
    FakeEmailProvider,
    OutboundEmail,
    ResendEmailProvider,
    SMTPEmailProvider,
    create_email_provider,
)

__all__ = [
    "ConsoleEmailProvider",
    "EmailAttachment",
    "EmailDeliveryError",
    "EmailDeliveryOutcome",
    "EmailProvider",
    "FakeEmailProvider",
    "OutboundEmail",
    "ResendEmailProvider",
    "SMTPEmailProvider",
    "create_email_provider",
]
