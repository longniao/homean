import io
import json
import shutil
import wave
from pathlib import Path

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import SecretStr, ValidationError

from app.core.pipeline_config import PipelineConfig, PipelineStep
from app.pipeline import llm as llm_module
from app.pipeline import openai_transcription as audio_module
from app.pipeline.llm import AnthropicLLMClient, OpenAILLMClient, create_llm_client
from app.pipeline.openai_transcription import (
    AudioChunk,
    OpenAITranscriptionProvider,
    audio_chunks,
    normalize_audio,
)
from app.pipeline.schemas import ZoneDetectionResult
from app.pipeline.transcription import DeepgramProvider, create_transcription_provider
from tests.test_resend_provider import settings


def sdk_factory(handler):  # type: ignore[no-untyped-def]
    def create(**kwargs):  # type: ignore[no-untyped-def]
        kwargs["max_retries"] = 0
        return AsyncOpenAI(
            **kwargs,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

    return create


def response_body(**changes):  # type: ignore[no-untyped-def]
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 1,
        "status": "completed",
        "model": "gpt-5.4-mini-2026-03-17",
        "output": [
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {"type": "output_text", "text": '{"zones":[]}', "annotations": []}
                ],
            }
        ],
        "usage": {"input_tokens": 123, "output_tokens": 45, "total_tokens": 168},
        **changes,
    }


async def test_responses_uses_strict_schema_and_preserves_model_and_usage(monkeypatch):  # type: ignore[no-untyped-def]
    requests = []

    def handler(request):  # type: ignore[no-untyped-def]
        requests.append(request)
        return httpx.Response(200, json=response_body())

    monkeypatch.setattr(llm_module, "AsyncOpenAI", sdk_factory(handler))
    result = await OpenAILLMClient("sk-test").parse(
        prompt="test evidence",
        model="gpt-5.4-mini",
        max_tokens=16000,
        output_format=ZoneDetectionResult,
    )
    payload = json.loads(requests[0].content)
    assert requests[0].url.path == "/v1/responses"
    assert payload["store"] is False
    assert payload["max_output_tokens"] == 16000
    assert "thinking" not in payload
    schema = payload["text"]["format"]
    assert schema["strict"] is True
    assert schema["schema"]["additionalProperties"] is False
    assert schema["schema"]["required"] == ["zones"]
    assert result.parsed.zones == []
    assert result.model == "gpt-5.4-mini-2026-03-17"
    assert (result.tokens_in, result.tokens_out) == (123, 45)


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}},
        {"output": []},
        {
            "output": [
                {
                    "type": "message",
                    "id": "msg",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "refusal", "refusal": "private text"}],
                }
            ]
        },
        {
            "output": [
                {
                    "type": "message",
                    "id": "msg",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"zones":"private text"}',
                            "annotations": [],
                        }
                    ],
                }
            ]
        },
    ],
)
async def test_incomplete_refused_or_invalid_output_cannot_become_a_report(
    monkeypatch, changes
):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        llm_module,
        "AsyncOpenAI",
        sdk_factory(lambda _: httpx.Response(200, json=response_body(**changes))),
    )
    with pytest.raises(ValueError) as error:
        await OpenAILLMClient("sk-test").parse(
            prompt="private evidence",
            model="gpt-5.4-mini",
            max_tokens=100,
            output_format=ZoneDetectionResult,
        )
    assert "private" not in str(error.value)


async def test_llm_provider_errors_do_not_echo_private_data(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        llm_module,
        "AsyncOpenAI",
        sdk_factory(
            lambda _: httpx.Response(
                401, json={"error": {"message": "private sk-test"}}
            )
        ),
    )
    with pytest.raises(ValueError, match="check provider access") as error:
        await OpenAILLMClient("sk-test").parse(
            prompt="test",
            model="gpt-5.4-mini",
            max_tokens=100,
            output_format=ZoneDetectionResult,
        )
    assert "private" not in str(error.value)


@pytest.mark.parametrize("stt", ["deepgram", "openai"])
@pytest.mark.parametrize("llm", ["anthropic", "openai"])
def test_independent_provider_switches(stt, llm):  # type: ignore[no-untyped-def]
    config = PipelineConfig(_env_file=None, llm_provider=llm)
    values = settings()
    values.transcription_provider = stt
    values.openai_api_key = SecretStr("sk-test")
    values.anthropic_api_key = SecretStr("ant-test")
    values.deepgram_api_key = SecretStr("dg-test")
    assert isinstance(
        create_llm_client(values, config),
        OpenAILLMClient if llm == "openai" else AnthropicLLMClient,
    )
    assert isinstance(
        create_transcription_provider(values, config),
        OpenAITranscriptionProvider if stt == "openai" else DeepgramProvider,
    )
    for step in list(PipelineStep)[1:]:
        assert config.model_for(step) == (
            "gpt-5.4-mini" if llm == "openai" else "claude-opus-4-8"
        )


def test_provider_typo_is_not_a_fallback():
    with pytest.raises(ValidationError):
        PipelineConfig(_env_file=None, llm_provider="opeani")
    values = settings()
    values.transcription_provider = "opeani"
    with pytest.raises(ValueError, match="unsupported"):
        create_transcription_provider(values, PipelineConfig(_env_file=None))


async def test_missing_openai_key_fails_before_network():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        await OpenAITranscriptionProvider("").transcribe("https://unused.test", "en")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        await OpenAILLMClient("").parse(
            prompt="test",
            model="gpt-5.4-mini",
            max_tokens=100,
            output_format=ZoneDetectionResult,
        )


def wav_bytes(seconds=1):  # type: ignore[no-untyped-def]
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(b"\x00\x00" * int(seconds * 16000))
    return output.getvalue()


def test_audio_split_keeps_every_sample_and_exact_offsets(tmp_path):  # type: ignore[no-untyped-def]
    path = tmp_path / "audio.wav"
    path.write_bytes(wav_bytes(2.5))
    chunks = list(audio_chunks(path, chunk_seconds=1))
    assert len(chunks) == 3
    offset = 0
    for chunk in chunks:
        assert chunk.offset_seconds == pytest.approx(offset)
        assert len(chunk.content) < 25_000_000
        offset += chunk.duration_seconds
    assert offset == pytest.approx(2.5)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not installed")
async def test_real_audio_normalization_and_duration_guard(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    source, target = tmp_path / "input.wav", tmp_path / "output.wav"
    source.write_bytes(wav_bytes(3))
    monkeypatch.setattr(audio_module, "MAX_DURATION_SECONDS", 2)
    await normalize_audio(source, target)
    with pytest.raises(ValueError, match="120 minutes"):
        list(audio_chunks(target))


async def test_transcription_offsets_speakers_and_cleanup(monkeypatch):  # type: ignore[no-untyped-def]
    paths: list[Path] = []
    requests = []

    async def download(url, path):  # type: ignore[no-untyped-def]
        paths.append(path)
        path.write_bytes(wav_bytes())

    async def normalize(source, target):  # type: ignore[no-untyped-def]
        target.write_bytes(source.read_bytes())

    def handler(request):  # type: ignore[no-untyped-def]
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "task": "transcribe",
                "duration": 1,
                "text": "Kitchen.",
                "segments": [
                    {
                        "id": "s1",
                        "text": "Kitchen.",
                        "speaker": "A",
                        "start": 0.1,
                        "end": 0.9,
                    }
                ],
            },
        )

    monkeypatch.setattr(audio_module, "download_audio", download)
    monkeypatch.setattr(audio_module, "normalize_audio", normalize)
    monkeypatch.setattr(
        audio_module,
        "audio_chunks",
        lambda _: iter(
            [AudioChunk(wav_bytes(), 0, 1), AudioChunk(wav_bytes(), 600, 1)]
        ),
    )
    monkeypatch.setattr(audio_module, "AsyncOpenAI", sdk_factory(handler))
    pieces = await OpenAITranscriptionProvider("sk-test").transcribe(
        "https://private.test/signed", "en"
    )
    assert [p.start_ms for p in pieces] == [100, 600100]
    assert [p.end_ms for p in pieces] == [900, 600900]
    assert [p.speaker for p in pieces] == [0, 1]
    assert all(p.confidence is None for p in pieces)
    assert all(not path.parent.exists() for path in paths)
    assert b"diarized_json" in requests[0].content
    assert b"chunking_strategy" in requests[0].content
    assert b"private.test" not in requests[0].content
