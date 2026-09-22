from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from anthropic import AsyncAnthropic
from openai import APIError, AsyncOpenAI
from pydantic import BaseModel

from app.core.config import Settings
from app.core.pipeline_config import PipelineConfig

SchemaT = TypeVar("SchemaT", bound=BaseModel)
Fixture = BaseModel | dict[str, object]
FixtureFactory = Callable[[str, type[BaseModel], str], Fixture]


@dataclass(frozen=True)
class LLMResponse[ResponseT: BaseModel]:
    parsed: ResponseT
    model: str
    tokens_in: int
    tokens_out: int


class LLMClient(ABC):
    @abstractmethod
    async def parse(
        self,
        *,
        prompt: str,
        model: str,
        max_tokens: int,
        output_format: type[SchemaT],
    ) -> LLMResponse[SchemaT]:
        """Return a response validated against the requested Pydantic schema."""


class AnthropicLLMClient(LLMClient):
    def __init__(self, api_key: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key, max_retries=4)

    async def parse(
        self,
        *,
        prompt: str,
        model: str,
        max_tokens: int,
        output_format: type[SchemaT],
    ) -> LLMResponse[SchemaT]:
        message = await self._client.messages.parse(
            model=model,
            thinking={"type": "adaptive"},
            max_tokens=max_tokens,
            output_format=output_format,
            messages=[{"role": "user", "content": prompt}],
        )
        parsed = message.parsed_output
        if parsed is None:
            raise ValueError("Anthropic returned no parsed structured output")
        return LLMResponse(
            parsed=parsed,
            model=str(message.model),
            tokens_in=message.usage.input_tokens,
            tokens_out=message.usage.output_tokens,
        )


class OpenAILLMClient(LLMClient):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def parse(
        self,
        *,
        prompt: str,
        model: str,
        max_tokens: int,
        output_format: type[SchemaT],
    ) -> LLMResponse[SchemaT]:
        if not self._api_key.strip():
            raise ValueError("OPENAI_API_KEY is required for OpenAI report generation")
        try:
            async with AsyncOpenAI(
                api_key=self._api_key, max_retries=2, timeout=300
            ) as client:
                response = await client.responses.parse(
                    model=model,
                    input=[{"role": "user", "content": prompt}],
                    text_format=output_format,
                    max_output_tokens=max_tokens,
                    store=False,
                )
        except APIError:
            # Pipeline failures are saved and visible in the dashboard. Provider
            # bodies may echo private prompts; never persist them in an error.
            raise ValueError(
                "OpenAI report request failed; check provider access and limits"
            ) from None
        except ValueError:
            raise ValueError("OpenAI returned invalid structured report data") from None
        if response.status != "completed" or response.output_parsed is None:
            raise ValueError("OpenAI did not return a complete structured report")
        if response.usage is None:
            raise ValueError("OpenAI response is missing usage information")
        return LLMResponse(
            parsed=response.output_parsed,
            model=response.model,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
        )


def create_llm_client(settings: Settings, config: PipelineConfig) -> LLMClient:
    if config.llm_provider == "openai":
        return OpenAILLMClient(
            settings.openai_api_key.get_secret_value()
            if settings.openai_api_key
            else ""
        )
    return AnthropicLLMClient(
        settings.anthropic_api_key.get_secret_value()
        if settings.anthropic_api_key
        else ""
    )


class FakeLLMClient(LLMClient):
    def __init__(
        self, fixtures: list[Fixture | FixtureFactory | Exception] | None = None
    ):
        self.fixtures = list(fixtures or [])
        self.calls: list[tuple[str, str, type[BaseModel]]] = []

    def queue(self, fixture: Fixture | FixtureFactory | Exception) -> None:
        self.fixtures.append(fixture)

    async def parse(
        self,
        *,
        prompt: str,
        model: str,
        max_tokens: int,
        output_format: type[SchemaT],
    ) -> LLMResponse[SchemaT]:
        del max_tokens
        self.calls.append((prompt, model, output_format))
        if not self.fixtures:
            raise AssertionError(
                f"no fake LLM fixture queued for {output_format.__name__}"
            )
        fixture = self.fixtures.pop(0)
        if isinstance(fixture, Exception):
            raise fixture
        if callable(fixture):
            fixture = fixture(prompt, output_format, model)
        return LLMResponse(
            parsed=output_format.model_validate(fixture),
            model=model,
            tokens_in=100,
            tokens_out=50,
        )
