from types import SimpleNamespace

from app.pipeline.transcription import DeepgramProvider, TranscriptionPiece


class _Recorder:
    """Captures the options sent to Deepgram and replays canned utterances."""

    def __init__(self, utterances: list[object]) -> None:
        self.options: dict[str, object] = {}
        self._utterances = utterances
        self.listen = SimpleNamespace(
            v1=SimpleNamespace(media=SimpleNamespace(transcribe_url=self._call))
        )

    async def _call(self, **options: object) -> object:
        self.options = options
        return SimpleNamespace(results=SimpleNamespace(utterances=self._utterances))


def _utterance(text: str, speaker: object) -> object:
    return SimpleNamespace(
        transcript=text, start=1.0, end=2.0, confidence=0.9, speaker=speaker
    )


def _provider(utterances: list[object]) -> tuple[DeepgramProvider, _Recorder]:
    provider = DeepgramProvider.__new__(DeepgramProvider)
    provider.model = "nova-3"
    recorder = _Recorder(utterances)
    provider._client = recorder
    return provider, recorder


async def test_transcription_requests_diarization() -> None:
    provider, recorder = _provider([_utterance("The kitchen is bright.", 0)])

    await provider.transcribe("https://example.test/audio", "en")

    # Attribution cannot be recovered from a recording already transcribed
    # without it, so it has to be asked for on the original call.
    assert recorder.options["diarize"] is True


async def test_each_segment_keeps_the_voice_that_spoke_it() -> None:
    provider, _ = _provider(
        [_utterance("There is a damp smell.", 1), _utterance("I will ask.", 0)]
    )

    pieces = await provider.transcribe("https://example.test/audio", "en")

    assert [piece.speaker for piece in pieces] == [1, 0]


async def test_a_provider_that_omits_the_speaker_yields_unknown() -> None:
    provider, _ = _provider([_utterance("The kitchen is bright.", None)])

    pieces = await provider.transcribe("https://example.test/audio", "en")

    # Unknown, never collapsed to a default voice: on an evidence record an
    # invented attribution is worse than an absent one.
    assert pieces[0].speaker is None


async def test_an_unparsable_speaker_is_treated_as_unknown() -> None:
    provider, _ = _provider([_utterance("The kitchen is bright.", "not-an-index")])

    pieces = await provider.transcribe("https://example.test/audio", "en")

    assert pieces[0].speaker is None


def test_speaker_is_optional_on_the_transcription_contract() -> None:
    piece = TranscriptionPiece(
        text="The kitchen is bright.", start_ms=0, end_ms=1000, confidence=0.9
    )

    assert piece.speaker is None
