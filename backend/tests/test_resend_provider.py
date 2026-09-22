import base64
import json
import uuid

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.email import (
    EmailAttachment,
    EmailDeliveryError,
    EmailDeliveryOutcome,
    OutboundEmail,
    ResendEmailProvider,
    create_email_provider,
)
from app.services.delivery import RealEstateDeliveryService


def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost/0",
        s3_endpoint_url="http://localhost:9000",
        s3_access_key="test",
        s3_secret_key=SecretStr("test"),
        s3_bucket="test",
        jwt_secret=SecretStr("test-secret-that-is-long-enough"),
        email_provider="resend",
        resend_api_key=SecretStr("re_test_key"),
        resend_from_email="reports@example.com",
    )


def message() -> OutboundEmail:
    return OutboundEmail(
        message_id="<homean-report-stable@example.com>",
        to_email="buyer@example.com",
        subject="Showing report",
        html_body='<p><a href="https://example.com/private">Report</a></p>',
        attachment=EmailAttachment(
            "showing-report.pdf", b"%PDF-test", "application/pdf"
        ),
    )


async def test_resend_sends_attachment_and_reuses_idempotency_key() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "resend-message-1"})

    provider = ResendEmailProvider(settings(), transport=httpx.MockTransport(handler))
    assert await provider.send(message()) == "resend-message-1"
    assert await provider.send(message()) == "resend-message-1"
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.resend.com/emails"
    assert request.headers["Authorization"] == "Bearer re_test_key"
    assert request.headers["Idempotency-Key"] == requests[1].headers["Idempotency-Key"]
    payload = json.loads(request.content)
    assert payload["from"] == "Homean <reports@example.com>"
    assert payload["to"] == ["buyer@example.com"]
    assert payload["html"] == message().html_body
    assert payload["headers"]["Message-ID"] == message().message_id
    assert payload["attachments"][0]["filename"] == "showing-report.pdf"
    assert base64.b64decode(payload["attachments"][0]["content"]) == b"%PDF-test"


@pytest.mark.parametrize("status", [400, 401, 403, 422, 429])
async def test_resend_rejections_are_definitive_and_sanitized(status: int) -> None:
    provider = ResendEmailProvider(
        settings(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(status, text="private report re_test_key")
        ),
    )
    with pytest.raises(EmailDeliveryError) as raised:
        await provider.send(message())
    assert raised.value.outcome == EmailDeliveryOutcome.DEFINITIVE_FAILURE
    assert str(raised.value) == f"Resend returned HTTP {status}"


@pytest.mark.parametrize("status", [302, 408, 409, 500, 503])
async def test_resend_ambiguous_http_results_block_retries(status: int) -> None:
    provider = ResendEmailProvider(
        settings(),
        transport=httpx.MockTransport(lambda _: httpx.Response(status)),
    )
    with pytest.raises(EmailDeliveryError) as raised:
        await provider.send(message())
    assert raised.value.outcome == EmailDeliveryOutcome.OUTCOME_UNKNOWN


@pytest.mark.parametrize(
    "body", [b"not JSON", b"{}", b'{"id":null}', b"[]", b'{"id":""}']
)
async def test_resend_invalid_success_cannot_be_retried(body: bytes) -> None:
    provider = ResendEmailProvider(
        settings(),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body)),
    )
    with pytest.raises(EmailDeliveryError) as raised:
        await provider.send(message())
    assert raised.value.outcome == EmailDeliveryOutcome.OUTCOME_UNKNOWN


@pytest.mark.parametrize(
    ("error", "outcome"),
    [
        (httpx.ConnectError, EmailDeliveryOutcome.DEFINITIVE_FAILURE),
        (httpx.ConnectTimeout, EmailDeliveryOutcome.DEFINITIVE_FAILURE),
        (httpx.PoolTimeout, EmailDeliveryOutcome.DEFINITIVE_FAILURE),
        (httpx.ReadTimeout, EmailDeliveryOutcome.OUTCOME_UNKNOWN),
        (httpx.WriteError, EmailDeliveryOutcome.OUTCOME_UNKNOWN),
    ],
)
async def test_resend_transport_outcome(
    error: type[httpx.HTTPError], outcome: EmailDeliveryOutcome
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise error("private provider error")

    provider = ResendEmailProvider(settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(EmailDeliveryError) as raised:
        await provider.send(message())
    assert raised.value.outcome == outcome
    assert "private" not in str(raised.value)


@pytest.mark.parametrize("key", [None, SecretStr("")])
async def test_resend_missing_key_never_sends(key: SecretStr | None) -> None:
    config = settings()
    config.resend_api_key = key

    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("unconfigured provider must not send")

    provider = ResendEmailProvider(config, transport=httpx.MockTransport(handler))
    with pytest.raises(EmailDeliveryError) as raised:
        await provider.send(message())
    assert raised.value.outcome == EmailDeliveryOutcome.DEFINITIVE_FAILURE


def test_resend_factory_and_sender_namespace() -> None:
    config = settings()
    assert isinstance(create_email_provider(config), ResendEmailProvider)
    service = RealEstateDeliveryService(None, config, None, None, None)  # type: ignore[arg-type]
    send_id = uuid.uuid4()
    assert service._message_id(send_id) == f"<homean-report-{send_id}@example.com>"
