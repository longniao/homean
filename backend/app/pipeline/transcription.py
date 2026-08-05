from abc import ABC, abstractmethod

from deepgram import AsyncDeepgramClient
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings
from app.core.pipeline_config import PipelineConfig


class TranscriptionPiece(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    start_ms: float = Field(ge=0)
    end_ms: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)


class TranscriptionProvider(ABC):
    model: str

    @abstractmethod
    async def transcribe(
        self, audio_url: str, language: str
    ) -> list[TranscriptionPiece]:
        """Transcribe a private, short-lived audio URL into timed utterances."""


class DeepgramProvider(TranscriptionProvider):
    def __init__(self, api_key: str, model: str = "nova-3") -> None:
        self.model = model
        self._client = AsyncDeepgramClient(api_key=api_key)

    async def transcribe(
        self, audio_url: str, language: str
    ) -> list[TranscriptionPiece]:
        response = await self._client.listen.v1.media.transcribe_url(
            url=audio_url,
            model=self.model,
            language=language,
            punctuate=True,
            utterances=True,
            smart_format=True,
            request_options={"max_retries": 4, "timeout_in_seconds": 300},
        )
        utterances = getattr(response.results, "utterances", None) or []
        pieces: list[TranscriptionPiece] = []
        for utterance in utterances:
            text = (utterance.transcript or "").strip()
            if not text:
                continue
            pieces.append(
                TranscriptionPiece(
                    text=text,
                    start_ms=float(utterance.start or 0) * 1000,
                    end_ms=float(utterance.end or utterance.start or 0) * 1000,
                    confidence=float(utterance.confidence or 0),
                )
            )
        return pieces


class FakeTranscriptionProvider(TranscriptionProvider):
    def __init__(
        self,
        fixture: list[TranscriptionPiece | dict[str, object]] | None = None,
        *,
        model: str = "fake-deepgram",
    ) -> None:
        self.model = model
        self.fixture = [
            TranscriptionPiece.model_validate(item)
            for item in (
                fixture
                or [
                    {
                        "text": "The kitchen has excellent natural light.",
                        "start_ms": 0,
                        "end_ms": 2500,
                        "confidence": 0.98,
                    },
                    {
                        "text": "The cabinets show some wear near the sink.",
                        "start_ms": 2600,
                        "end_ms": 5100,
                        "confidence": 0.96,
                    },
                ]
            )
        ]
        self.calls: list[tuple[str, str]] = []
        self.error: Exception | None = None

    async def transcribe(
        self, audio_url: str, language: str
    ) -> list[TranscriptionPiece]:
        self.calls.append((audio_url, language))
        if self.error is not None:
            raise self.error
        return [piece.model_copy(deep=True) for piece in self.fixture]


def create_transcription_provider(
    settings: Settings, pipeline_config: PipelineConfig
) -> TranscriptionProvider:
    if settings.transcription_provider.lower() != "deepgram":
        raise ValueError(
            f"unsupported transcription provider: {settings.transcription_provider}"
        )
    api_key = (
        settings.deepgram_api_key.get_secret_value()
        if settings.deepgram_api_key is not None
        else ""
    )
    return DeepgramProvider(api_key, pipeline_config.deepgram_model)
