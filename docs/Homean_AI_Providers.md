# AI provider switches

Updated 2026-09-22. These are deployment-level switches in the Mac mini's
`/Users/hepang/Git/homean/backend/.env`. They are not exposed to buyers or agents.
API keys stay on the server. Restart `homean_api` and `homean_worker` after changes;
wait for active jobs and the queue to finish before switching a running deployment.

## Choose a combination

| Transcription | Report pipeline | `TRANSCRIPTION_PROVIDER` | `PIPELINE_LLM_PROVIDER` | Required keys |
| --- | --- | --- | --- | --- |
| OpenAI | OpenAI | `openai` | `openai` | `OPENAI_API_KEY` |
| Deepgram | Anthropic | `deepgram` | `anthropic` | `DEEPGRAM_API_KEY`, `ANTHROPIC_API_KEY` |
| Deepgram | OpenAI | `deepgram` | `openai` | `DEEPGRAM_API_KEY`, `OPENAI_API_KEY` |
| OpenAI | Anthropic | `openai` | `anthropic` | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` |

OpenAI-only configuration:

```dotenv
TRANSCRIPTION_PROVIDER=openai
PIPELINE_LLM_PROVIDER=openai
OPENAI_API_KEY=
PIPELINE_OPENAI_MODEL=gpt-5.4-mini
PIPELINE_OPENAI_TRANSCRIPTION_MODEL=gpt-4o-transcribe-diarize
```

Fill the key securely in the server environment, never in source control or chat.
The OpenAI report model is configurable and applies to room detection, observation
extraction and report generation. The configured model must support Responses API
structured output. `gpt-5.4-mini` is an initial configuration, not a claim that it
has passed Homean's real-world quality evaluation.

The original `PIPELINE_ZONE_DETECTION_MODEL`,
`PIPELINE_OBSERVATION_EXTRACTION_MODEL` and `PIPELINE_REPORT_GENERATION_MODEL`
remain Anthropic-only settings. Switching to OpenAI does not send Claude model
names to OpenAI or discard the original model configuration. Repository defaults
remain Deepgram + Anthropic for backward compatibility. Production can select any
combination explicitly; errors never cause a silent cross-provider fallback.

## Evidence and audio

OpenAI uses `gpt-4o-transcribe-diarize` with `diarized_json` and automatic internal
chunking. Its segments preserve speaker labels and start/end times. Unsupported
transcription models are rejected because plain-text transcription would lose the
evidence timestamps.

The worker requires `ffmpeg` (included in its Docker image; install via Homebrew
for native macOS). It downloads the application-generated signed audio URL using
a separate HTTP client, normalizes to mono 16 kHz PCM and sends chunks of at most
10 minutes / approximately 19.2 MB, below OpenAI's 25 MB upload limit. Splits prefer
a quiet window in the final five seconds; continuous speech may still be split at
the time limit. All frame offsets are preserved and applied to returned timestamps.
Chunk-boundary transcription quality still requires real-audio evaluation.

Downloads are bounded to 256 MiB and decoded audio to two hours per media file.
Oversized input fails explicitly instead of silently truncating evidence. Temporary
audio is deleted after success or failure; original media remains in private storage.
No OpenAI key is sent to the storage host.

Speaker labels are anonymous and scoped to a recording/provider chunk. The same
speaker across chunks is **not** identity-matched; labels in different chunks use
separate indices. Transcription confidence is `null` when OpenAI does not supply
it. Observation confidence remains the model's estimate and is not a calibrated
transcription score.

Reports use the existing versioned vertical prompts and Pydantic schemas through
Responses structured output with `store=false`. Actual returned model names and
token usage are recorded. Refused, incomplete or invalid output fails the step.
Reports still require human review and confirmation before sharing or Resend delivery.
`store=false` does not itself change OpenAI's other data-retention policies.

The existing cost CLI retains accurate recorded token totals but reports unknown
cost for GPT/mixed-model visits instead of applying Anthropic rates. Audio charges
are not included in that text-token estimate.

## Verification and remaining acceptance

Automated checks use HTTP mock transports and synthetic audio, never paid APIs.
They cover all four provider combinations, strict schemas, refusals, incomplete
output, evidence links, timestamps, missing confidence, chunk offsets and review
state. Configure `OPENAI_API_KEY` and run an authorized synthetic English showing
before claiming real-world transcription/report quality or production acceptance.

Official references:
- [OpenAI file transcription](https://developers.openai.com/api/docs/guides/speech-to-text)
- [OpenAI structured output](https://developers.openai.com/api/docs/guides/structured-outputs)
- [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
