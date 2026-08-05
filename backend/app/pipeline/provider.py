import asyncio
import uuid
from abc import ABC, abstractmethod

from app.core.pipeline_config import PipelineStep


class PipelineEnqueuer(ABC):
    @abstractmethod
    async def enqueue(
        self,
        visit_id: uuid.UUID,
        workspace_id: uuid.UUID,
        start_step: PipelineStep = PipelineStep.TRANSCRIBE,
    ) -> None:
        """Schedule the AI pipeline for a completed showing."""


class CeleryPipelineEnqueuer(PipelineEnqueuer):
    async def enqueue(
        self,
        visit_id: uuid.UUID,
        workspace_id: uuid.UUID,
        start_step: PipelineStep = PipelineStep.TRANSCRIBE,
    ) -> None:
        from app.pipeline.tasks import enqueue_visit_pipeline

        await asyncio.to_thread(
            enqueue_visit_pipeline, visit_id, workspace_id, start_step
        )


class FakePipelineEnqueuer(PipelineEnqueuer):
    def __init__(self) -> None:
        self.jobs: list[tuple[uuid.UUID, uuid.UUID, PipelineStep]] = []

    async def enqueue(
        self,
        visit_id: uuid.UUID,
        workspace_id: uuid.UUID,
        start_step: PipelineStep = PipelineStep.TRANSCRIBE,
    ) -> None:
        self.jobs.append((visit_id, workspace_id, start_step))
