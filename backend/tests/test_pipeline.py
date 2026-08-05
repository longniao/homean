import json
import re
import uuid
from collections.abc import Callable

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pipeline_config import PipelineConfig, PipelineStep
from app.models import Observation, PipelineRun, Report, TranscriptSegment, Visit, Zone
from app.pipeline import (
    FakeLLMClient,
    FakePipelineEnqueuer,
    FakeTranscriptionProvider,
)
from app.services import RealEstatePipelineService
from app.storage import FakeStorageProvider
from app.verticals import VerticalConfigService

PASSWORD = "correct-horse-battery-staple"
UUID_PATTERN = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
FixtureFactory = Callable[[str, type[object], str], dict[str, object]]


async def create_finished_showing(
    client: AsyncClient,
    storage: FakeStorageProvider,
    email: str,
    address: str | None = "42 Pipeline Avenue",
) -> tuple[dict[str, str], uuid.UUID, uuid.UUID]:
    signup = await client.post(
        "/auth/signup", json={"email": email, "password": PASSWORD}
    )
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    workspace_id = uuid.UUID(
        (await client.get("/me", headers=headers)).json()["workspace"]["id"]
    )
    showing = await client.post(
        "/showings",
        headers=headers,
        json={"address": address} if address is not None else {},
    )
    assert showing.status_code == 201, showing.text
    assert (showing.json()["property"] is None) is (address is None)
    visit_id = uuid.UUID(showing.json()["id"])
    presign = await client.post(
        f"/showings/{visit_id}/media/presign",
        headers=headers,
        json={"type": "audio", "content_type": "audio/mp4"},
    )
    media_id = presign.json()["media_id"]
    storage.put_object(storage.presigned_puts[-1], "audio/mp4", 1024 * 1024)
    complete = await client.post(
        f"/showings/{visit_id}/media/{media_id}/complete", headers=headers
    )
    assert complete.status_code == 200
    finish = await client.post(f"/showings/{visit_id}/finish", headers=headers)
    assert finish.status_code == 200
    assert finish.json()["processing_status"] == "queued"
    return headers, workspace_id, visit_id


def zone_fixture(
    prompt: str, output_format: type[object], model: str
) -> dict[str, object]:
    del output_format, model
    segment_ids = re.findall(rf'"id": "({UUID_PATTERN})"', prompt)
    assert len(segment_ids) >= 2
    return {
        "zones": [
            {
                "zone_type": "kitchen",
                "start_segment_id": segment_ids[0],
                "end_segment_id": segment_ids[-1],
            }
        ]
    }


def observation_fixture(
    prompt: str, output_format: type[object], model: str
) -> dict[str, object]:
    del output_format, model
    zone_id = re.search(rf'"zone_id": "({UUID_PATTERN})"', prompt)
    segment_ids = re.findall(rf'"id": "({UUID_PATTERN})"', prompt)
    assert zone_id is not None
    assert len(segment_ids) >= 2
    return {
        "observations": [
            {
                "zone_id": zone_id.group(1),
                "category": "pro",
                "content": "The kitchen has strong natural light.",
                "source_transcript_segment_id": segment_ids[0],
                "start_ms": 0,
                "end_ms": 2500,
                "confidence": 0.94,
                "flags": {"sensitive": False},
            },
            {
                "zone_id": zone_id.group(1),
                "category": "con",
                "content": "This invalid evidence must be dropped.",
                "source_transcript_segment_id": str(uuid.uuid4()),
                "start_ms": 0,
                "end_ms": 1,
                "confidence": 0.5,
                "flags": {"sensitive": False},
            },
            {
                "zone_id": zone_id.group(1),
                "category": "concern",
                "content": "The seller is hiding damage near the sink.",
                "source_transcript_segment_id": segment_ids[1],
                "start_ms": 2600,
                "end_ms": 5100,
                "confidence": 0.86,
                "flags": {
                    "sensitive": True,
                    "reason": "Speculates about the seller's intent.",
                    "suggested_rewrite": "Wear is visible near the sink.",
                },
            },
        ]
    }


def report_fixture(
    prompt: str, output_format: type[object], model: str
) -> dict[str, object]:
    del output_format, model
    observations_text = prompt.split("Available observations:\n", maxsplit=1)[1]
    observation_ids = re.findall(rf'"id": "({UUID_PATTERN})"', observations_text)
    zone_match = re.search(rf'"id": "({UUID_PATTERN})"', prompt)
    assert zone_match is not None
    assert len(observation_ids) >= 2
    pro_id, concern_id = observation_ids[:2]
    return {
        "executive_summary": "Bright kitchen with visible cabinet wear to review.",
        "room_by_room": [
            {
                "zone_id": zone_match.group(1),
                "zone_type": "kitchen",
                "bullets": [
                    {
                        "text": "Strong natural light.",
                        "observation_ids": [pro_id],
                    },
                    {
                        "text": "Visible wear near the sink.",
                        "observation_ids": [concern_id],
                    },
                ],
            }
        ],
        "highlights": [{"text": "Strong natural light.", "observation_ids": [pro_id]}],
        "concerns": [{"text": "Cabinet wear.", "observation_ids": [concern_id]}],
        "follow_ups": [],
    }


def dangling_report_fixture(
    prompt: str, output_format: type[object], model: str
) -> dict[str, object]:
    del output_format, model
    observations = json.loads(prompt.split("Available observations:\n", maxsplit=1)[1])
    valid_id = observations[0]["id"]
    invalid_id = str(uuid.uuid4())
    zone_match = re.search(rf'"id": "({UUID_PATTERN})"', prompt)
    assert zone_match is not None
    return {
        "executive_summary": "A report with filtered evidence references.",
        "room_by_room": [
            {
                "zone_id": zone_match.group(1),
                "zone_type": "kitchen",
                "bullets": [
                    {
                        "text": "Keep the supported portion.",
                        "observation_ids": [valid_id, invalid_id],
                    }
                ],
            },
            {
                "zone_id": None,
                "zone_type": None,
                "bullets": [
                    {
                        "text": "Drop this unsupported no-zone bullet.",
                        "observation_ids": [invalid_id],
                    }
                ],
            },
        ],
        "highlights": [{"text": "Supported highlight.", "observation_ids": [valid_id]}],
        "concerns": [{"text": "Unsupported concern.", "observation_ids": [invalid_id]}],
        "follow_ups": [],
    }


def descriptive_observation_fixture(
    prompt: str, output_format: type[object], model: str
) -> dict[str, object]:
    del output_format, model
    batches = json.loads(
        prompt.split(
            "Zone batches and their ordered transcript evidence:\n", maxsplit=1
        )[1]
    )
    zoned = next(batch for batch in batches if batch["zone_id"] is not None)
    light_source, noise_source = zoned["segments"][:2]
    return {
        "observations": [
            {
                "zone_id": zoned["zone_id"],
                "category": "light",
                "content": "The kitchen has strong natural light.",
                "source_transcript_segment_id": light_source["id"],
                "start_ms": light_source["start_ms"],
                "end_ms": light_source["end_ms"],
                "confidence": 0.94,
                "flags": {"sensitive": False},
            },
            {
                "zone_id": zoned["zone_id"],
                "category": "noise",
                "content": "Road noise is clearly audible in the kitchen.",
                "source_transcript_segment_id": noise_source["id"],
                "start_ms": noise_source["start_ms"],
                "end_ms": noise_source["end_ms"],
                "confidence": 0.91,
                "flags": {"sensitive": False},
            },
        ]
    }


def descriptive_report_fixture(
    prompt: str, output_format: type[object], model: str
) -> dict[str, object]:
    del output_format, model
    assert "genuinely favorable descriptive observations" in prompt
    assert "genuinely unfavorable descriptive" in prompt
    observations = json.loads(prompt.split("Available observations:\n", maxsplit=1)[1])
    light = next(item for item in observations if item["category"] == "light")
    noise = next(item for item in observations if item["category"] == "noise")
    return {
        "executive_summary": "Strong daylight with noticeable road noise.",
        "room_by_room": [
            {
                "zone_id": light["zone_id"],
                "zone_type": "kitchen",
                "bullets": [
                    {
                        "text": "Strong natural light.",
                        "observation_ids": [light["id"]],
                    },
                    {
                        "text": "Road noise is clearly audible.",
                        "observation_ids": [noise["id"]],
                    },
                ],
            }
        ],
        "highlights": [
            {
                "text": "Strong natural light.",
                "observation_ids": [light["id"]],
            }
        ],
        "concerns": [
            {
                "text": "Noticeable road noise.",
                "observation_ids": [noise["id"]],
            }
        ],
        "follow_ups": [],
    }


def partial_zone_fixture(
    prompt: str, output_format: type[object], model: str
) -> dict[str, object]:
    del output_format, model
    segments = json.loads(prompt.split("Ordered transcript segments:\n", maxsplit=1)[1])
    assert len(segments) == 3
    return {
        "zones": [
            {
                "zone_type": "kitchen",
                "start_segment_id": segments[1]["id"],
                "end_segment_id": segments[1]["id"],
            }
        ]
    }


def no_zone_observation_fixture(
    prompt: str, output_format: type[object], model: str
) -> dict[str, object]:
    del output_format, model
    batches = json.loads(
        prompt.split(
            "Zone batches and their ordered transcript evidence:\n", maxsplit=1
        )[1]
    )
    assert len(batches) == 2
    no_zone = next(batch for batch in batches if batch["zone_id"] is None)
    assert [segment["text"] for segment in no_zone["segments"]] == [
        "Traffic is loud at the front entrance.",
        "That concludes the showing.",
    ]
    source = no_zone["segments"][0]
    return {
        "observations": [
            {
                "zone_id": None,
                "category": "noise",
                "content": "Traffic noise is loud at the front entrance.",
                "source_transcript_segment_id": source["id"],
                "start_ms": source["start_ms"],
                "end_ms": source["end_ms"],
                "confidence": 0.93,
                "flags": {"sensitive": False},
            }
        ]
    }


def no_zone_report_fixture(
    prompt: str, output_format: type[object], model: str
) -> dict[str, object]:
    del output_format, model
    observations = json.loads(prompt.split("Available observations:\n", maxsplit=1)[1])
    no_zone = next(item for item in observations if item["zone_id"] is None)
    return {
        "executive_summary": "Traffic noise was noted at the entrance.",
        "room_by_room": [
            {
                "zone_id": None,
                "zone_type": None,
                "bullets": [
                    {
                        "text": "Traffic noise is loud at the front entrance.",
                        "observation_ids": [no_zone["id"]],
                    }
                ],
            }
        ],
        "highlights": [],
        "concerns": [
            {
                "text": "Loud traffic noise at the entrance.",
                "observation_ids": [no_zone["id"]],
            }
        ],
        "follow_ups": [],
    }


def pipeline_service(
    session: AsyncSession,
    storage: FakeStorageProvider,
    transcription: FakeTranscriptionProvider,
    llm: FakeLLMClient,
) -> RealEstatePipelineService:
    return RealEstatePipelineService(
        session=session,
        storage=storage,
        transcription=transcription,
        llm=llm,
        config=PipelineConfig(),
        verticals=VerticalConfigService(),
    )


async def test_fake_pipeline_builds_full_evidence_chain_and_is_idempotent(
    client: AsyncClient,
    session: AsyncSession,
    storage: FakeStorageProvider,
    pipeline: FakePipelineEnqueuer,
) -> None:
    headers, workspace_id, visit_id = await create_finished_showing(
        client, storage, "pipeline-e2e@example.com"
    )
    transcription = FakeTranscriptionProvider()
    llm = FakeLLMClient([zone_fixture, observation_fixture, report_fixture])
    service = pipeline_service(session, storage, transcription, llm)

    await service.transcribe(workspace_id, visit_id)
    session.expire_all()
    progress = await session.get(Visit, visit_id)
    assert progress is not None and progress.processing_status == "transcribing"
    await service.detect_zones(workspace_id, visit_id)
    session.expire_all()
    progress = await session.get(Visit, visit_id)
    assert progress is not None and progress.processing_status == "structuring"
    await service.extract_observations(workspace_id, visit_id)
    session.expire_all()
    progress = await session.get(Visit, visit_id)
    assert progress is not None and progress.processing_status == "generating"
    await service.generate_report(workspace_id, visit_id)
    session.expire_all()

    visit = await session.get(Visit, visit_id)
    assert visit is not None
    assert visit.processing_status == "ready"
    assert visit.status == "draft"
    segments = list(
        await session.scalars(
            select(TranscriptSegment).where(TranscriptSegment.visit_id == visit_id)
        )
    )
    zones = list(await session.scalars(select(Zone).where(Zone.visit_id == visit_id)))
    observations = list(
        await session.scalars(
            select(Observation).where(Observation.visit_id == visit_id)
        )
    )
    report = await session.scalar(select(Report).where(Report.visit_id == visit_id))
    runs = list(
        await session.scalars(
            select(PipelineRun).where(PipelineRun.visit_id == visit_id)
        )
    )

    assert len(segments) == 2
    assert len(zones) == 1
    assert len(observations) == 2
    assert all(item.source_transcript_segment_id for item in observations)
    assert all(item.source_media_id for item in observations)
    assert all(item.ai_model == "claude-opus-4-8" for item in observations)
    assert all(item.prompt_version == "re_v1" for item in observations)
    assert all(item.review_status == "pending" for item in observations)
    sensitive = next(item for item in observations if item.flags.get("sensitive"))
    assert sensitive.flags["suggested_rewrite"] == "Wear is visible near the sink."
    assert report is not None
    assert report.status == "pending_review"
    assert report.content["highlights"][0]["observation_ids"]
    assert len(runs) == 4
    assert {run.status for run in runs} == {"success"}
    assert len(pipeline.jobs) == 1

    detail = await client.get(f"/showings/{visit_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["processing_status"] == "ready"
    assert len(detail.json()["observations"]) == 2
    assert detail.json()["report"]["status"] == "pending_review"

    counts_before = (len(segments), len(zones), len(observations), len(runs))
    llm_call_count = len(llm.calls)
    transcription_call_count = len(transcription.calls)
    assert await service.run_all(workspace_id, visit_id) is True
    counts_after = tuple(
        [
            await session.scalar(
                select(func.count())
                .select_from(model)
                .where(model.visit_id == visit_id)
            )
            for model in (TranscriptSegment, Zone, Observation, PipelineRun)
        ]
    )
    assert counts_after == counts_before
    assert len(llm.calls) == llm_call_count
    assert len(transcription.calls) == transcription_call_count


async def test_subjectless_showing_processes_to_a_ready_draft(
    client: AsyncClient,
    session: AsyncSession,
    storage: FakeStorageProvider,
) -> None:
    headers, workspace_id, visit_id = await create_finished_showing(
        client,
        storage,
        "pipeline-subjectless@example.com",
        address=None,
    )
    service = pipeline_service(
        session,
        storage,
        FakeTranscriptionProvider(),
        FakeLLMClient([zone_fixture, observation_fixture, report_fixture]),
    )

    assert await service.run_all(workspace_id, visit_id) is True
    detail = await client.get(f"/showings/{visit_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["property"] is None
    assert detail.json()["status"] == "draft"
    assert detail.json()["processing_status"] == "ready"
    assert detail.json()["report"]["status"] == "pending_review"


async def test_report_drops_dangling_observation_references_and_logs_counts(
    client: AsyncClient,
    session: AsyncSession,
    storage: FakeStorageProvider,
) -> None:
    _, workspace_id, visit_id = await create_finished_showing(
        client, storage, "pipeline-report-integrity@example.com"
    )
    llm = FakeLLMClient([zone_fixture, observation_fixture, dangling_report_fixture])
    service = pipeline_service(session, storage, FakeTranscriptionProvider(), llm)

    assert await service.run_all(workspace_id, visit_id) is True
    report = await session.scalar(select(Report).where(Report.visit_id == visit_id))
    report_run = await session.scalar(
        select(PipelineRun).where(
            PipelineRun.visit_id == visit_id,
            PipelineRun.step == PipelineStep.REPORT_GENERATION,
        )
    )

    assert report is not None
    assert len(report.content["room_by_room"]) == 1
    assert len(report.content["room_by_room"][0]["bullets"]) == 1
    real_id = report.content["highlights"][0]["observation_ids"][0]
    assert report.content["room_by_room"][0]["bullets"][0]["observation_ids"] == [
        real_id
    ]
    assert report.content["concerns"] == []
    assert report_run is not None
    assert report_run.status == "success"
    assert report_run.error == ("report_integrity:dropped_bullets=2,dropped_refs=3")


async def test_salient_descriptive_observations_are_promoted_with_real_references(
    client: AsyncClient,
    session: AsyncSession,
    storage: FakeStorageProvider,
) -> None:
    _, workspace_id, visit_id = await create_finished_showing(
        client, storage, "pipeline-descriptive-report@example.com"
    )
    llm = FakeLLMClient(
        [zone_fixture, descriptive_observation_fixture, descriptive_report_fixture]
    )
    service = pipeline_service(session, storage, FakeTranscriptionProvider(), llm)

    assert await service.run_all(workspace_id, visit_id) is True
    observations = list(
        await session.scalars(
            select(Observation).where(Observation.visit_id == visit_id)
        )
    )
    report = await session.scalar(select(Report).where(Report.visit_id == visit_id))

    assert report is not None
    assert {item.category for item in observations} == {"light", "noise"}
    assert report.content["highlights"][0]["text"] == "Strong natural light."
    assert report.content["concerns"][0]["text"] == "Noticeable road noise."
    real_ids = {str(item.id) for item in observations}
    promoted = report.content["highlights"] + report.content["concerns"]
    assert all(set(bullet["observation_ids"]) <= real_ids for bullet in promoted)


async def test_segments_outside_zones_persist_and_reach_the_report(
    client: AsyncClient,
    session: AsyncSession,
    storage: FakeStorageProvider,
) -> None:
    _, workspace_id, visit_id = await create_finished_showing(
        client, storage, "pipeline-no-zone@example.com"
    )
    transcription = FakeTranscriptionProvider(
        [
            {
                "text": "Traffic is loud at the front entrance.",
                "start_ms": 0,
                "end_ms": 1500,
                "confidence": 0.98,
            },
            {
                "text": "The kitchen counters are quartz.",
                "start_ms": 1600,
                "end_ms": 3200,
                "confidence": 0.97,
            },
            {
                "text": "That concludes the showing.",
                "start_ms": 3300,
                "end_ms": 4300,
                "confidence": 0.99,
            },
        ]
    )
    llm = FakeLLMClient(
        [partial_zone_fixture, no_zone_observation_fixture, no_zone_report_fixture]
    )
    service = pipeline_service(session, storage, transcription, llm)

    assert await service.run_all(workspace_id, visit_id) is True
    observations = list(
        await session.scalars(
            select(Observation).where(Observation.visit_id == visit_id)
        )
    )
    report = await session.scalar(select(Report).where(Report.visit_id == visit_id))

    assert len(observations) == 1
    assert observations[0].zone_id is None
    assert report is not None
    assert report.content["room_by_room"][0]["zone_id"] is None
    assert report.content["room_by_room"][0]["bullets"][0]["observation_ids"] == [
        str(observations[0].id)
    ]
    assert report.content["concerns"][0]["observation_ids"] == [str(observations[0].id)]


async def test_failure_marks_visit_and_reprocess_recovers_from_failed_step(
    client: AsyncClient,
    session: AsyncSession,
    storage: FakeStorageProvider,
    pipeline: FakePipelineEnqueuer,
) -> None:
    headers, workspace_id, visit_id = await create_finished_showing(
        client, storage, "pipeline-recovery@example.com"
    )
    transcription = FakeTranscriptionProvider()
    llm = FakeLLMClient([zone_fixture, RuntimeError("temporary model outage")])
    service = pipeline_service(session, storage, transcription, llm)

    assert await service.run_all(workspace_id, visit_id) is False
    session.expire_all()
    visit = await session.get(Visit, visit_id)
    assert visit is not None
    assert visit.processing_status == "failed"
    assert visit.processing_failed_step == "observation_extraction"
    assert "temporary model outage" in (visit.processing_error or "")

    source = await session.scalar(
        select(TranscriptSegment).where(TranscriptSegment.visit_id == visit_id).limit(1)
    )
    zone = await session.scalar(select(Zone).where(Zone.visit_id == visit_id).limit(1))
    assert source is not None
    assert zone is not None
    professional = Observation(
        visit_id=visit_id,
        zone_id=zone.id,
        category="general",
        content="Agent-confirmed note.",
        source_type="professional_edited",
        source_transcript_segment_id=source.id,
        source_media_id=source.raw_media_id,
        timestamp_start=source.timestamp_start,
        timestamp_end=source.timestamp_end,
        review_status="edited",
    )
    session.add(professional)
    await session.commit()

    reprocess = await client.post(f"/showings/{visit_id}/reprocess", headers=headers)
    assert reprocess.status_code == 200, reprocess.text
    assert reprocess.json()["processing_status"] == "queued"
    duplicate = await client.post(f"/showings/{visit_id}/reprocess", headers=headers)
    assert duplicate.status_code == 200
    assert len(pipeline.jobs) == 2
    assert pipeline.jobs[-1][2] == PipelineStep.OBSERVATION_EXTRACTION

    llm.queue(observation_fixture)
    llm.queue(report_fixture)
    assert (
        await service.run_all(
            workspace_id,
            visit_id,
            start_step=PipelineStep.OBSERVATION_EXTRACTION,
        )
        is True
    )
    session.expire_all()
    recovered_visit = await session.get(Visit, visit_id)
    assert recovered_visit is not None
    assert recovered_visit.processing_status == "ready"
    assert recovered_visit.processing_error is None
    assert (
        await session.scalar(
            select(func.count())
            .select_from(Observation)
            .where(
                Observation.visit_id == visit_id,
                Observation.source_type == "professional_edited",
            )
        )
        == 1
    )
    assert (
        await session.scalar(
            select(func.count()).select_from(Zone).where(Zone.visit_id == visit_id)
        )
        == 1
    )
