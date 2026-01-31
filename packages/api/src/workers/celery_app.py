"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from src.config import settings

celery = Celery(
    "copio",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.workers.tasks"],
)

# Celery configuration
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,  # Fair distribution
)

# Beat schedule for periodic tasks
celery.conf.beat_schedule = {
    "calculate-velocities-hourly": {
        "task": "src.workers.tasks.calculate_velocities_task",
        "schedule": crontab(minute=0),  # Every hour at :00
    },
}
