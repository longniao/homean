from celery import Celery
from celery.signals import after_setup_logger, after_setup_task_logger

from app.core.config import get_settings
from app.core.security import configure_json_logger, configure_observability

settings = get_settings()
configure_observability(settings)


@after_setup_logger.connect
def _configure_celery_logger(logger, **kwargs: object) -> None:  # type: ignore[no-untyped-def]
    del kwargs
    configure_json_logger(logger)


@after_setup_task_logger.connect
def _configure_celery_task_logger(logger, **kwargs: object) -> None:  # type: ignore[no-untyped-def]
    del kwargs
    configure_json_logger(logger)


celery_app = Celery(
    "homean",
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
    worker_hijack_root_logger=False,
)
