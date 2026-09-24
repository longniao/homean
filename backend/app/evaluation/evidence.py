"""Run a synthetic evidence-check experiment, with no production data access.

From backend/: uv run python -m app.evaluation.evidence --help
The default validates local fixtures only. Paid calls require --provider jev.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import statistics
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Annotated, Literal, Protocol

import httpx
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "evals/real_estate_evidence_v1.json"
DEFAULT_CONFIG = ROOT / "app/verticals/evaluations/real_estate_evidence_v1.yaml"
Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False, strict=True)]
Nonempty = Annotated[str, Field(min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Case(StrictModel):
    id: Nonempty
    scenario: Nonempty
    category: Nonempty
    split: Literal["development", "holdout"]
    evidence: Nonempty
    claim: Nonempty
    expected_supported: bool
    rationale: Nonempty

    def state(self) -> dict[str, str]:
        # Labels, rationales, IDs and category hints must never reach the model.
        return {"evidence": self.evidence, "claim": self.claim}


class Dataset(StrictModel):
    version: Nonempty
    provenance: Literal["agent_authored_synthetic"]
    human_reviewed: Literal[False]
    cases: list[Case] = Field(min_length=1)

    @model_validator(mode="after")
    def check_cases(self) -> Dataset:
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("duplicate case IDs")
        if len({(c.evidence, c.claim) for c in self.cases}) != len(self.cases):
            raise ValueError("duplicate evidence/claim pairs")
        splits: dict[str, str] = {}
        for case in self.cases:
            if splits.setdefault(case.scenario, case.split) != case.split:
                raise ValueError("a scenario cannot span development and holdout")
        return self


class Rubric(StrictModel):
    version: Nonempty
    output_language: Literal["en"]
    model: Nonempty
    support_threshold: Probability
    flag_threshold: Probability
    input_usd_per_million: float = Field(ge=0, allow_inf_nan=False)
    pricing_checked_on: Nonempty
    instructions: Nonempty
    criteria: dict[Literal["true", "false"], str]

    @model_validator(mode="after")
    def check_rubric(self) -> Rubric:
        if self.flag_threshold >= self.support_threshold:
            raise ValueError("flag threshold must be below support threshold")
        if set(self.criteria) != {"true", "false"}:
            raise ValueError("both boolean criteria are required")
        if "{output_language}" not in self.instructions:
            raise ValueError("instructions must parameterize output_language")
        return self


class NoulAnswer(BaseModel):
    type: Literal["noul"]
    noul: Probability


class Usage(BaseModel):
    input_tokens: int = Field(ge=0, strict=True)
    output_tokens: int = Field(ge=0, strict=True)


class JevResponse(BaseModel):
    model: Nonempty
    answers: dict[str, NoulAnswer]
    usage: Usage


class Decision(StrictModel):
    supported_probability: Probability
    model: Nonempty
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class EvaluationFailure(Exception):
    def __init__(self, code: str, *, fatal: bool = False):
        self.code = code
        self.fatal = fatal
        super().__init__(code)


class EvidenceEvaluator(Protocol):
    async def evaluate(self, state: dict[str, str]) -> Decision: ...


class CitationOnlyBaseline:
    """A control for valid references without semantic checks, not an LLM eval.

    All bundled cases contain a valid evidence excerpt. This deliberately
    accepts each claim to measure what a semantic check could add. It does not
    recreate or benchmark the production report generator.
    """

    async def evaluate(self, state: dict[str, str]) -> Decision:
        return Decision(
            supported_probability=float(bool(state["evidence"].strip())),
            model="citation-only-control-v1",
            input_tokens=0,
            output_tokens=0,
        )


class JevEvidenceEvaluator:
    def __init__(self, client: httpx.AsyncClient, api_key: str, rubric: Rubric):
        self.client = client
        self.api_key = api_key
        self.rubric = rubric

    async def evaluate(self, state: dict[str, str]) -> Decision:
        try:
            response = await self.client.post(
                "https://api.typesafe.ai/v1/systemone",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.rubric.model,
                    "state": state,
                    "questions": {
                        "supported": {
                            "type": "noul",
                            "instructions": self.rubric.instructions.format(
                                output_language=self.rubric.output_language
                            ),
                            "criteria": self.rubric.criteria,
                        }
                    },
                },
                timeout=15.0,
                follow_redirects=False,
            )
            if response.status_code != 200:
                # Do not print bodies: vendor error messages may echo input.
                raise EvaluationFailure(
                    f"http_{response.status_code}",
                    fatal=response.status_code in {401, 403, 429, 529},
                )
            parsed = JevResponse.model_validate(response.json())
            if set(parsed.answers) != {"supported"}:
                raise EvaluationFailure("invalid_answers")
            if parsed.model != self.rubric.model:
                raise EvaluationFailure("unexpected_model", fatal=True)
            return Decision(
                supported_probability=parsed.answers["supported"].noul,
                model=parsed.model,
                input_tokens=parsed.usage.input_tokens,
                output_tokens=parsed.usage.output_tokens,
            )
        except httpx.TimeoutException as exc:
            raise EvaluationFailure("timeout") from exc
        except httpx.RequestError as exc:
            raise EvaluationFailure("transport_error") from exc
        except (ValidationError, ValueError) as exc:
            raise EvaluationFailure("invalid_response") from exc


def outcome(probability: float, rubric: Rubric) -> str:
    if probability >= rubric.support_threshold:
        return "supported"
    if probability <= rubric.flag_threshold:
        return "flagged"
    return "uncertain"


async def evaluate_cases(
    cases: list[Case], evaluator: EvidenceEvaluator, rubric: Rubric
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    stopped = False
    for case in cases:
        row: dict[str, object] = {
            "id": case.id,
            "scenario": case.scenario,
            "category": case.category,
            "split": case.split,
            "expected_supported": case.expected_supported,
            "outcome": "error",
            "attempted": not stopped,
        }
        start = perf_counter()
        if stopped:
            row["error"] = "not_attempted_after_fatal_error"
        else:
            try:
                decision = await evaluator.evaluate(case.state())
                row.update(decision.model_dump())
                row["outcome"] = outcome(decision.supported_probability, rubric)
            except EvaluationFailure as exc:
                row["error"] = exc.code
                stopped = exc.fatal
            row["latency_ms"] = round((perf_counter() - start) * 1000, 3)
        rows.append(row)
    return rows


def summarize(rows: list[dict[str, object]], rate: float) -> dict[str, object]:
    def ratio(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 6) if denominator else None

    good = [r for r in rows if r["expected_supported"]]
    bad = [r for r in rows if not r["expected_supported"]]
    reviewed = {"flagged", "uncertain"}
    false_alarms = sum(r["outcome"] in reviewed for r in good)
    misses = sum(r["outcome"] == "supported" for r in bad)
    errors = sum(r["outcome"] == "error" for r in rows)
    successful = len(rows) - errors
    caught = sum(r["outcome"] in reviewed for r in bad)
    bad_errors = sum(r["outcome"] == "error" for r in bad)
    good_assessed = sum(r["outcome"] != "error" for r in good)
    bad_assessed = len(bad) - bad_errors
    latencies = sorted(float(r["latency_ms"]) for r in rows if r["attempted"])
    tokens = sum(int(r.get("input_tokens", 0)) for r in rows)
    return {
        "cases": len(rows),
        "assessed": successful,
        "outcomes": dict(Counter(str(r["outcome"]) for r in rows)),
        "coverage": ratio(successful, len(rows)),
        "review_rate_assessed": ratio(caught + false_alarms, successful),
        "false_positive_rate_assessed": ratio(false_alarms, good_assessed),
        "false_negative_rate_assessed": ratio(misses, bad_assessed),
        "unsupported_review_recall_assessed": ratio(caught, bad_assessed),
        "review_precision_assessed": ratio(caught, caught + false_alarms),
        "unsupported_missed_or_unassessed": misses + bad_errors,
        "unsupported_total": len(bad),
        "errors_or_unattempted": errors,
        "latency_ms_p50": statistics.median(latencies) if latencies else None,
        "latency_ms_p95": (
            latencies[math.ceil(len(latencies) * 0.95) - 1] if latencies else None
        ),
        "recorded_input_tokens": tokens,
        "recorded_output_tokens": sum(int(r.get("output_tokens", 0)) for r in rows),
        "estimated_recorded_cost_usd": round(tokens / 1_000_000 * rate, 8),
        "cost_may_exclude_failed_calls": bool(errors),
    }


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider", choices=["validate", "baseline", "jev"], default="validate"
    )
    parser.add_argument(
        "--split", choices=["all", "development", "holdout"], default="all"
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    if args.output and args.output.exists():
        parser.error("output already exists; choose a new path")

    dataset = Dataset.model_validate_json(DEFAULT_DATASET.read_text(encoding="utf-8"))
    rubric = Rubric.model_validate(yaml.safe_load(DEFAULT_CONFIG.read_text("utf-8")))
    cases = [c for c in dataset.cases if args.split == "all" or c.split == args.split]
    cases = cases[: args.limit]
    payload: dict[str, object] = {
        "created_at": datetime.now(UTC).isoformat(),
        "provider": args.provider,
        "dataset_version": dataset.version,
        "dataset_sha256": fingerprint(DEFAULT_DATASET),
        "provenance": dataset.provenance,
        "human_reviewed": dataset.human_reviewed,
        "rubric_version": rubric.version,
        "rubric_sha256": fingerprint(DEFAULT_CONFIG),
        "requested_model": rubric.model if args.provider == "jev" else None,
        "thresholds": {
            "support": rubric.support_threshold,
            "flag": rubric.flag_threshold,
        },
        "pricing": {
            "input_usd_per_million": rubric.input_usd_per_million,
            "checked_on": rubric.pricing_checked_on,
        },
        "selected_cases": len(cases),
        "selected_split": args.split,
        "case_counts": dict(Counter(c.category for c in cases)),
        "expected_support_counts": dict(
            Counter(str(c.expected_supported) for c in cases)
        ),
        "production_ready": False,
    }
    rows: list[dict[str, object]] = []
    if args.provider == "baseline":
        rows = asyncio.run(evaluate_cases(cases, CitationOnlyBaseline(), rubric))
    elif args.provider == "jev":
        key = os.environ.get("TYPESAFE_API_KEY", "").strip()
        if not key:
            parser.error("TYPESAFE_API_KEY must be set in the process environment")

        async def run() -> list[dict[str, object]]:
            async with httpx.AsyncClient() as client:
                evaluator = JevEvidenceEvaluator(client, key, rubric)
                return await evaluate_cases(cases, evaluator, rubric)

        rows = asyncio.run(run())
    if rows:
        payload["summary"] = summarize(rows, rubric.input_usd_per_million)
        payload["by_category"] = {
            category: summarize(
                [r for r in rows if r["category"] == category],
                rubric.input_usd_per_million,
            )
            for category in sorted({c.category for c in cases})
        }
        payload["results"] = rows
    result = json.dumps(payload, indent=2, allow_nan=False) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as destination:
            destination.write(result)
        print(f"Wrote {args.output}")
    else:
        print(result, end="")
    return 1 if any(row["outcome"] == "error" for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
