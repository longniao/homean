import json

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.pipeline_config import PipelineConfig
from app.models import Observation, PipelineRun, Report, TranscriptSegment, Visit
from app.pipeline import llm as llm_module
from app.pipeline.llm import OpenAILLMClient
from app.pipeline.transcription import FakeTranscriptionProvider
from app.services.pipeline import RealEstatePipelineService
from app.verticals import VerticalConfigService
from scripts.ai_cost_report import collect
from tests.test_openai_providers import response_body, sdk_factory
from tests.test_pipeline import (
    create_finished_showing,
    observation_fixture,
    report_fixture,
    zone_fixture,
)


async def test_openai_report_pipeline_keeps_evidence_and_review_gate(
    client, session, storage, monkeypatch
):  # type: ignore[no-untyped-def]
    headers, workspace_id, visit_id = await create_finished_showing(
        client, storage, "openai-pipeline@example.com"
    )
    factories = iter([zone_fixture, observation_fixture, report_fixture])
    requests = []

    def handler(request):  # type: ignore[no-untyped-def]
        payload = json.loads(request.content)
        requests.append(payload)
        fixture = next(factories)(
            payload["input"][0]["content"], object, payload["model"]
        )
        result = response_body()
        result["output"][0]["content"][0]["text"] = json.dumps(fixture)
        return httpx.Response(200, json=result)

    monkeypatch.setattr(llm_module, "AsyncOpenAI", sdk_factory(handler))
    transcription = FakeTranscriptionProvider(model="gpt-4o-transcribe-diarize")
    for piece in transcription.fixture:
        piece.confidence = None
        piece.speaker = 0
    service = RealEstatePipelineService(
        session,
        storage,
        transcription,
        OpenAILLMClient("sk-test"),
        PipelineConfig(_env_file=None, llm_provider="openai"),
        VerticalConfigService(),
    )
    assert await service.run_all(workspace_id, visit_id) is True
    session.expire_all()
    visit = await session.get(Visit, visit_id)
    assert visit.status == "draft" and visit.processing_status == "ready"
    segments = list(
        await session.scalars(
            select(TranscriptSegment).where(TranscriptSegment.visit_id == visit_id)
        )
    )
    observations = list(
        await session.scalars(
            select(Observation).where(Observation.visit_id == visit_id)
        )
    )
    assert len(segments) == 2
    assert all(segment.confidence is None for segment in segments)
    assert all(segment.speaker == 0 for segment in segments)
    assert len(observations) == 2  # invalid evidence is still filtered
    assert all(
        item.source_transcript_segment_id and item.source_media_id
        for item in observations
    )
    assert all(item.ai_model == "gpt-5.4-mini-2026-03-17" for item in observations)
    assert all(item.review_status == "pending" for item in observations)
    report = await session.scalar(select(Report).where(Report.visit_id == visit_id))
    assert report.status == "pending_review"
    runs = list(
        await session.scalars(
            select(PipelineRun).where(PipelineRun.visit_id == visit_id)
        )
    )
    assert len(runs) == 4 and all(run.status == "success" for run in runs)
    assert all(request["model"] == "gpt-5.4-mini" for request in requests)
    assert all(request["store"] is False for request in requests)
    detail = await client.get(f"/showings/{visit_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["transcript"][0]["confidence"] is None

    # Claude rates must never be applied to a new GPT visit.
    monkeypatch.setenv("ANTHROPIC_INPUT_COST_PER_MILLION", "3")
    monkeypatch.setenv("ANTHROPIC_OUTPUT_COST_PER_MILLION", "15")
    get_settings.cache_clear()
    try:
        costs = await collect(visit_id)
        assert len(costs) == 1 and costs[0].tokens_in == 369
        assert costs[0].estimated_cost_usd is None
    finally:
        get_settings.cache_clear()
