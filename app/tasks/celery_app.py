from celery import Celery
from kombu import Queue, Exchange
from app.config import settings
import structlog

logger = structlog.get_logger()

celery_app = Celery(
    "inference_server",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.gpu_worker"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    task_default_retry_delay=settings.retry_backoff,
    task_max_retries=settings.max_retries,
    
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    
    task_queues=(
        Queue("gpu-high", Exchange("gpu", type="direct"), routing_key="gpu.high", priority=9),
        Queue("gpu-normal", Exchange("gpu", type="direct"), routing_key="gpu.normal", priority=5),
        Queue("gpu-low", Exchange("gpu", type="direct"), routing_key="gpu.low", priority=1),
    ),
    
    task_routes={
        "app.tasks.gpu_worker.process_inference": {"queue": "gpu-normal"},
    },
    
    beat_schedule={},
)