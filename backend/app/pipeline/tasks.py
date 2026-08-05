import asyncio
import uuid

from celery import chain
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.pipeline_config import PipelineStep, get_pipeline_config
from app.pipeline.celery_app import celery_app
from app.pipeline.llm import AnthropicLLMClient
from app.pipeline.transcription import create_transcription_provider
from app.services.pipeline import RealEstatePipelineService
from app.storage import S3Client
from app.verticals import get_vertical_config_service


async def _execute_step(
    workspace_id: uuid.UUID, visit_id: uuid.UUID, step: PipelineStep
) -> None:
    settings = get_settings()
    pipeline_config = get_pipeline_config()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    anthropic_key = (
        settings.anthropic_api_key.get_secret_value()
        if settings.anthropic_api_key is not None
        else ""
    )
    try:
        async with session_factory() as session:
            service = RealEstatePipelineService(
                session=session,
                storage=S3Client(settings),
                transcription=create_transcription_provider(settings, pipeline_config),
                llm=AnthropicLLMClient(anthropic_key),
                config=pipeline_config,
                verticals=get_vertical_config_service(),
            )
            await service.run_step(workspace_id, visit_id, step)
    finally:
        await engine.dispose()


def _run(workspace_id: str, visit_id: str, step: PipelineStep) -> None:
    asyncio.run(_execute_step(uuid.UUID(workspace_id), uuid.UUID(visit_id), step))


@celery_app.task(name="kawu.pipeline.transcribe")
def transcribe_visit(workspace_id: str, visit_id: str) -> None:
    _run(workspace_id, visit_id, PipelineStep.TRANSCRIBE)


@celery_app.task(name="kawu.pipeline.detect_zones")
def detect_visit_zones(workspace_id: str, visit_id: str) -> None:
    _run(workspace_id, visit_id, PipelineStep.ZONE_DETECTION)


@celery_app.task(name="kawu.pipeline.extract_observations")
def extract_visit_observations(workspace_id: str, visit_id: str) -> None:
    _run(workspace_id, visit_id, PipelineStep.OBSERVATION_EXTRACTION)


@celery_app.task(name="kawu.pipeline.generate_report")
def generate_visit_report(workspace_id: str, visit_id: str) -> None:
    _run(workspace_id, visit_id, PipelineStep.REPORT_GENERATION)


def enqueue_visit_pipeline(
    visit_id: uuid.UUID,
    workspace_id: uuid.UUID,
    start_step: PipelineStep = PipelineStep.TRANSCRIBE,
) -> None:
    workspace = str(workspace_id)
    visit = str(visit_id)
    signatures = {
        PipelineStep.TRANSCRIBE: transcribe_visit.si(workspace, visit),
        PipelineStep.ZONE_DETECTION: detect_visit_zones.si(workspace, visit),
        PipelineStep.OBSERVATION_EXTRACTION: extract_visit_observations.si(
            workspace, visit
        ),
        PipelineStep.REPORT_GENERATION: generate_visit_report.si(workspace, visit),
    }
    start_index = list(PipelineStep).index(start_step)
    chain(
        *(signatures[step] for step in list(PipelineStep)[start_index:])
    ).apply_async()
