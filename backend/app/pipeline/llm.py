from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from anthropic import AsyncAnthropic
from pydantic import BaseModel

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
