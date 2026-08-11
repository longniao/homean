import smtplib
import uuid

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.email import (
    EmailDeliveryError,
    EmailDeliveryOutcome,
    OutboundEmail,
    SMTPEmailProvider,
)
from app.services.delivery import RealEstateDeliveryService


def _settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://user:pass@localhost/kawu",
        redis_url="redis://localhost/0",
        s3_endpoint_url="http://localhost:9000",
        s3_access_key="access",
        s3_secret_key=SecretStr("secret"),
        s3_bucket="bucket",
        jwt_secret=SecretStr("a-sufficiently-long-test-secret"),
        smtp_host="smtp.example.com",
        smtp_from_email="reports@example.com",
    )


def test_new_delivery_message_ids_use_the_homean_namespace() -> None:
    service = RealEstateDeliveryService(
        None,  # type: ignore[arg-type]
        _settings(),
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
    )
    send_id = uuid.uuid4()

    assert service._message_id(send_id) == f"<homean-report-{send_id}@example.com>"

    legacy_settings = _settings()
    legacy_settings.smtp_from_email = "reports@kawu.local"
    legacy_service = RealEstateDeliveryService(
        None,  # type: ignore[arg-type]
        legacy_settings,
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
    )
    assert legacy_service._message_id(send_id) == (
        f"<homean-report-{send_id}@homean.com>"
    )


class _RecordingSMTP:
    last_message = None

    def __init__(self, host: str, port: int, timeout: int) -> None:
        assert (host, port, timeout) == ("smtp.example.com", 587, 30)

    def starttls(self) -> None:
        return None

    def send_message(self, message) -> None:  # type: ignore[no-untyped-def]
        _RecordingSMTP.last_message = message

    def quit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_smtp_reuses_application_message_id(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.email import provider as provider_module

    async def run_in_thread(function):  # type: ignore[no-untyped-def]
        return function()

    monkeypatch.setattr(provider_module.smtplib, "SMTP", _RecordingSMTP)
    monkeypatch.setattr(provider_module.asyncio, "to_thread", run_in_thread)
    provider = SMTPEmailProvider(_settings())
    message = OutboundEmail(
        message_id="<kawu-stable@example.com>",
        to_email="buyer@example.com",
        subject="Showing report",
        html_body="<p>Ready</p>",
    )

    assert await provider.send(message) == message.message_id
    assert _RecordingSMTP.last_message["Message-ID"] == message.message_id


@pytest.mark.asyncio
async def test_smtp_timeout_is_outcome_unknown(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.email import provider as provider_module

    class TimeoutSMTP(_RecordingSMTP):
        def send_message(self, message) -> None:  # type: ignore[no-untyped-def]
            del message
            raise TimeoutError("connection timed out")

    async def run_in_thread(function):  # type: ignore[no-untyped-def]
        return function()

    monkeypatch.setattr(provider_module.smtplib, "SMTP", TimeoutSMTP)
    monkeypatch.setattr(provider_module.asyncio, "to_thread", run_in_thread)
    provider = SMTPEmailProvider(_settings())

    with pytest.raises(EmailDeliveryError) as raised:
        await provider.send(
            OutboundEmail(
                message_id="<kawu-timeout@example.com>",
                to_email="buyer@example.com",
                subject="Showing report",
                html_body="<p>Ready</p>",
            )
        )
    assert raised.value.outcome == EmailDeliveryOutcome.OUTCOME_UNKNOWN


@pytest.mark.asyncio
async def test_smtp_recipient_rejection_is_definitive(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.email import provider as provider_module

    class RejectedSMTP(_RecordingSMTP):
        def send_message(self, message) -> None:  # type: ignore[no-untyped-def]
            del message
            raise smtplib.SMTPRecipientsRefused(
                {"buyer@example.com": (550, b"rejected")}
            )

    async def run_in_thread(function):  # type: ignore[no-untyped-def]
        return function()

    monkeypatch.setattr(provider_module.smtplib, "SMTP", RejectedSMTP)
    monkeypatch.setattr(provider_module.asyncio, "to_thread", run_in_thread)
    provider = SMTPEmailProvider(_settings())

    with pytest.raises(EmailDeliveryError) as raised:
        await provider.send(
            OutboundEmail(
                message_id="<kawu-rejected@example.com>",
                to_email="buyer@example.com",
                subject="Showing report",
                html_body="<p>Ready</p>",
            )
        )
    assert raised.value.outcome == EmailDeliveryOutcome.DEFINITIVE_FAILURE
