from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "kawu",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.pipeline.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)
