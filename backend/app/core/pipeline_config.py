from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PipelineStep(StrEnum):
    TRANSCRIBE = "transcribe"
    ZONE_DETECTION = "zone_detection"
    OBSERVATION_EXTRACTION = "observation_extraction"
    REPORT_GENERATION = "report_generation"


class PipelineConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        env_prefix="PIPELINE_",
        extra="ignore",
        case_sensitive=False,
    )

    zone_detection_model: str = "claude-opus-4-8"
    observation_extraction_model: str = "claude-opus-4-8"
    report_generation_model: str = "claude-opus-4-8"
    deepgram_model: str = "nova-3"
    output_language: Literal["en"] = "en"
    max_tokens: int = Field(default=16000, ge=1, le=64000)
    # A tag is normally tapped just before the agent starts a short thought.
    # Five seconds covers that handoff while preventing a later, unrelated
    # utterance from becoming evidence.  This is configurable because it is a
    # product policy, not an invariant of transcript timestamps.
    voice_tag_max_forward_gap_ms: int = Field(default=5_000, ge=0)

    def model_for(self, step: PipelineStep) -> str:
        models = {
            PipelineStep.ZONE_DETECTION: self.zone_detection_model,
            PipelineStep.OBSERVATION_EXTRACTION: self.observation_extraction_model,
            PipelineStep.REPORT_GENERATION: self.report_generation_model,
        }
        try:
            return models[step]
        except KeyError as exc:
            raise ValueError(f"step does not use an LLM model: {step}") from exc


@lru_cache
def get_pipeline_config() -> PipelineConfig:
    return PipelineConfig()
