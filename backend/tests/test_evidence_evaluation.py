import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
import yaml
from pydantic import ValidationError

from app.evaluation.evidence import (
    DEFAULT_CONFIG,
    DEFAULT_DATASET,
    ROOT,
    CitationOnlyBaseline,
    Dataset,
    Decision,
    EvaluationFailure,
    JevEvidenceEvaluator,
    Rubric,
    evaluate_cases,
    outcome,
    summarize,
)


@pytest.fixture
def rubric() -> Rubric:
    return Rubric.model_validate(yaml.safe_load(DEFAULT_CONFIG.read_text()))


@pytest.fixture
def dataset() -> Dataset:
    return Dataset.model_validate_json(DEFAULT_DATASET.read_text())


def response_body(probability: float = 0.91) -> dict:
    return {
        "model": "jev-1.13.0",
        "answers": {"supported": {"type": "noul", "noul": probability}},
        "usage": {"input_tokens": 321, "output_tokens": 8},
    }


def test_fixture_provenance_balance_and_scenario_split(dataset: Dataset):
    assert not dataset.human_reviewed
    assert dataset.provenance == "agent_authored_synthetic"
    assert len(dataset.cases) == 100
    assert len({c.scenario for c in dataset.cases}) == 25
    assert sum(c.expected_supported for c in dataset.cases) == 50
    assert sum(c.split == "development" for c in dataset.cases) == 60
    assert sum(c.split == "holdout" for c in dataset.cases) == 40
    assert {c.scenario for c in dataset.cases if c.split == "development"}.isdisjoint(
        c.scenario for c in dataset.cases if c.split == "holdout"
    )


def test_duplicate_and_leaking_scenarios_rejected(dataset: Dataset):
    raw = dataset.model_dump()
    raw["cases"].append(raw["cases"][0])
    with pytest.raises(ValidationError, match="duplicate case"):
        Dataset.model_validate(raw)
    raw = dataset.model_dump()
    raw["cases"][0]["split"] = "holdout"
    with pytest.raises(ValidationError, match="span development"):
        Dataset.model_validate(raw)


async def test_request_contract_does_not_send_labels_or_rationale(
    rubric: Rubric, dataset: Dataset
):
    case = dataset.cases[0]
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert str(request.url) == "https://api.typesafe.ai/v1/systemone"
        assert request.headers["Authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["state"] == {"evidence": case.evidence, "claim": case.claim}
        assert set(body) == {"model", "state", "questions"}
        assert body["model"] == "jev-1.13.0"
        question = body["questions"]["supported"]
        assert question["type"] == "noul"
        assert question["criteria"] == rubric.criteria
        assert "{output_language}" not in question["instructions"]
        return httpx.Response(200, json=response_body())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await JevEvidenceEvaluator(client, "test-key", rubric).evaluate(
            case.state()
        )
    assert len(calls) == 1
    assert result.supported_probability == 0.91
    assert result.input_tokens == 321


@pytest.mark.parametrize("probability", [-0.01, 1.01, "0.9", True, None])
async def test_invalid_probability_is_not_a_valid_result(rubric, probability):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=response_body(probability))
        )
    ) as client:
        with pytest.raises(EvaluationFailure, match="invalid_response"):
            await JevEvidenceEvaluator(client, "test-key", rubric).evaluate(
                {"evidence": "example", "claim": "example"}
            )


@pytest.mark.parametrize("probability", [float("nan"), float("inf")])
def test_nonfinite_probability_rejected(probability):
    with pytest.raises(ValidationError):
        Decision(
            supported_probability=probability,
            model="fake",
            input_tokens=0,
            output_tokens=0,
        )


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("missing_answer", "invalid_answers"),
        ("negative_usage", "invalid_response"),
        ("missing_usage", "invalid_response"),
        ("wrong_model", "unexpected_model"),
        ("wrong_type", "invalid_response"),
    ],
)
async def test_invalid_response_shapes_are_errors(rubric, mutation, code):
    body = response_body()
    if mutation == "missing_answer":
        body["answers"] = {}
    elif mutation == "negative_usage":
        body["usage"]["input_tokens"] = -1
    elif mutation == "missing_usage":
        del body["usage"]
    elif mutation == "wrong_type":
        body["answers"]["supported"]["type"] = "choice"
    else:
        body["model"] = "unvalidated-new-version"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
    ) as client:
        with pytest.raises(EvaluationFailure, match=code):
            await JevEvidenceEvaluator(client, "test-key", rubric).evaluate({})


@pytest.mark.parametrize("status", [401, 403, 429, 529])
async def test_fatal_response_stops_run_and_keeps_failures_visible(
    rubric, dataset, status
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="PRIVATE ECHO MUST NOT BE RECORDED")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rows = await evaluate_cases(
            dataset.cases[:4], JevEvidenceEvaluator(client, "test-key", rubric), rubric
        )
    assert len(calls) == 1
    assert rows[0]["error"] == f"http_{status}"
    assert all(row["outcome"] == "error" for row in rows)
    assert not rows[1]["attempted"]
    assert "PRIVATE ECHO" not in json.dumps(rows)
    summary = summarize(rows, 0.042)
    assert summary["coverage"] == 0
    assert summary["false_negative_rate_assessed"] is None
    assert summary["unsupported_missed_or_unassessed"] == 2
    assert summary["cost_may_exclude_failed_calls"] is True


async def test_timeout_is_unassessed_and_next_case_can_run(rubric, dataset):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout("private input", request=request)
        return httpx.Response(200, json=response_body())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rows = await evaluate_cases(
            dataset.cases[:2], JevEvidenceEvaluator(client, "test-key", rubric), rubric
        )
    assert rows[0]["error"] == "timeout"
    assert rows[1]["outcome"] == "supported"
    assert len(calls) == 2  # No hidden retries or surprise paid requests.


async def test_redirect_does_not_forward_credentials(rubric):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(307, headers={"Location": "https://other.example"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EvaluationFailure, match="http_307"):
            await JevEvidenceEvaluator(client, "test-key", rubric).evaluate({})
    assert len(calls) == 1


def test_threshold_boundaries_and_invalid_configuration(rubric):
    assert outcome(0.85, rubric) == "supported"
    assert outcome(0.15, rubric) == "flagged"
    assert outcome(0.50, rubric) == "uncertain"
    with pytest.raises(ValidationError, match="flag threshold"):
        Rubric.model_validate({**rubric.model_dump(), "flag_threshold": 0.90})


def test_metrics_distinguish_misses_uncertainty_and_missing_answers():
    rows = [
        {
            "expected_supported": expected,
            "outcome": result,
            "attempted": True,
            "latency_ms": 100.0,
            "input_tokens": 1000,
            "output_tokens": 10,
        }
        for expected, result in [
            (False, "supported"),
            (False, "flagged"),
            (False, "uncertain"),
            (False, "error"),
            (True, "supported"),
            (True, "uncertain"),
        ]
    ]
    rows[3].pop("input_tokens")
    rows[3].pop("output_tokens")
    summary = summarize(rows, 0.042)
    assert summary["false_negative_rate_assessed"] == pytest.approx(1 / 3, abs=1e-6)
    assert summary["false_positive_rate_assessed"] == 0.5
    assert summary["review_rate_assessed"] == 0.6
    assert summary["unsupported_missed_or_unassessed"] == 2
    assert summary["estimated_recorded_cost_usd"] == 0.00021
    assert summary["latency_ms_p95"] == 100


async def test_baseline_is_label_blind_and_not_a_model_benchmark(rubric, dataset):
    rows = await evaluate_cases(dataset.cases, CitationOnlyBaseline(), rubric)
    summary = summarize(rows, rubric.input_usd_per_million)
    assert summary["false_negative_rate_assessed"] == 1
    assert summary["false_positive_rate_assessed"] == 0
    assert summary["estimated_recorded_cost_usd"] == 0
    assert all("evidence" not in row and "claim" not in row for row in rows)
    assert all(row["model"] == "citation-only-control-v1" for row in rows)


def cli(*args: str) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment.pop("TYPESAFE_API_KEY", None)
    return subprocess.run(
        [sys.executable, "-m", "app.evaluation.evidence", *args],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_defaults_to_offline_validation_and_bounds_paid_calls():
    result = cli()
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["provider"] == "validate"
    assert payload["selected_cases"] == 100
    assert "results" not in payload
    assert payload["production_ready"] is False
    result = cli("--provider", "jev", "--limit", "1")
    assert result.returncode == 2
    assert "TYPESAFE_API_KEY must be set" in result.stderr
    assert cli("--limit", "101").returncode == 2


def test_cli_output_and_overwrite_protection(tmp_path: Path):
    output = tmp_path / "results.json"
    result = cli(
        "--provider", "baseline", "--split", "holdout", "--output", str(output)
    )
    assert result.returncode == 0
    assert json.loads(output.read_text())["selected_cases"] == 40
    previous = output.read_bytes()
    assert cli("--output", str(output)).returncode == 2
    assert output.read_bytes() == previous
