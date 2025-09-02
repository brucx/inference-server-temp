import os
import time
from typing import Dict, Any, Optional
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
import httpx
import structlog
from app.tasks.celery_app import celery_app
from app.models.registry import ModelRegistry
from app.models.base import ModelConfig
from app.services.storage import StorageService
from app.services.metrics import (
    task_completed, task_failed, inference_duration,
    storage_duration, total_duration
)
from app.utils.timing import Timer
import app.models.runners

logger = structlog.get_logger()


class InferenceTask(Task):
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 300
    retry_jitter = True
    
    def __init__(self):
        super().__init__()
        self.storage_service = None
        self.gpu_id = None
    
    def before_start(self, task_id, args, kwargs):
        gpu_id = int(os.environ.get("CUDA_VISIBLE_DEVICES", "0"))
        self.gpu_id = gpu_id
        
        if self.storage_service is None:
            self.storage_service = StorageService()
        
        logger.info(f"Starting task on GPU {gpu_id}", task_id=task_id)
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task failed", task_id=task_id, error=str(exc))
        task_failed.inc()
    
    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"Task completed successfully", task_id=task_id)


@celery_app.task(
    base=InferenceTask,
    bind=True,
    name="app.tasks.gpu_worker.process_inference",
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_inference(
    self,
    task_id: str,
    model_name: str,
    input_data: Dict[str, Any],
    callback_url: Optional[str] = None
) -> Dict[str, Any]:
    timer = Timer()
    timer.start("total")
    
    try:
        gpu_id = int(os.environ.get("CUDA_VISIBLE_DEVICES", "0"))
        
        logger.info(
            f"Processing inference task",
            task_id=task_id,
            model=model_name,
            gpu_id=gpu_id
        )
        
        config = ModelConfig(
            model_name=model_name,
            gpu_id=gpu_id,
            device="cuda" if gpu_id >= 0 else "cpu"
        )
        
        timer.start("model_loading")
        runner = ModelRegistry.get_or_create_runner(config)
        timer.stop("model_loading")
        
        timer.start("inference")
        result = runner.run(input_data)
        timer.stop("inference")
        
        timer.start("storage")
        if "image_bytes" in result:
            s3_key = f"results/{task_id}.png"
            s3_url = self.storage_service.upload_bytes(
                result["image_bytes"],
                s3_key,
                content_type="image/png"
            )
            result["s3_key"] = s3_key
            result["s3_url"] = s3_url
            del result["image_bytes"]
        timer.stop("storage")
        
        timer.stop("total")
        
        timing = timer.get_all_timings()
        
        inference_duration.labels(model=model_name).observe(timing["inference"] / 1000)
        storage_duration.observe(timing.get("storage", 0) / 1000)
        total_duration.labels(model=model_name).observe(timing["total"] / 1000)
        
        task_completed.labels(model=model_name).inc()
        
        response = {
            "task_id": task_id,
            "status": "SUCCESS",
            "timing": timing,
            "result": result
        }
        
        if callback_url:
            try:
                timer.start("callback")
                httpx.post(callback_url, json=response, timeout=30)
                timer.stop("callback")
                logger.info(f"Callback sent to {callback_url}")
            except Exception as e:
                logger.error(f"Failed to send callback", error=str(e))
        
        return response
        
    except SoftTimeLimitExceeded:
        logger.error(f"Task timeout", task_id=task_id)
        task_failed.inc()
        raise
    
    except Exception as e:
        logger.error(f"Task error", task_id=task_id, error=str(e))
        task_failed.inc()
        raise