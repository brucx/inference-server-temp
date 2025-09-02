from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
import uuid
import structlog
from prometheus_client import make_asgi_app
from app.config import settings
from app.deps.auth import verify_api_key
from app.deps.ratelimit import RateLimiter
from app.services.metrics import setup_metrics, task_submitted, task_status_checked
from app.utils.idempotency import IdempotencyCache
from app.tasks.celery_app import celery_app
from app.models.registry import ModelRegistry
import app.models.runners

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class TaskRequest(BaseModel):
    model: str = Field(..., description="Model name to use for inference")
    input: Dict[str, Any] = Field(..., description="Input parameters for the model")
    priority: Literal["high", "normal", "low"] = Field(default="normal")
    client_request_id: Optional[str] = Field(None, description="Client request ID for idempotency")
    callback_url: Optional[str] = Field(None, description="URL to call when task completes")


class TaskResponse(BaseModel):
    task_id: str
    status: str


class TaskStatus(BaseModel):
    task_id: str
    status: str
    timing: Optional[Dict[str, float]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_metrics()
    logger.info("Starting Inference Server", environment=settings.environment)
    
    available_models = ModelRegistry.list_models()
    logger.info(f"Available models: {available_models}")
    
    yield
    
    ModelRegistry.cleanup()
    logger.info("Shutting down Inference Server")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_per_minute)
idempotency_cache = IdempotencyCache()


@app.get("/health")
async def health_check():
    return {"status": "healthy", "environment": settings.environment}


@app.post("/v1/tasks", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_task(
    request: TaskRequest,
    api_key: str = Depends(verify_api_key)
):
    await rate_limiter.check_rate_limit(api_key)
    
    if request.client_request_id:
        existing_task_id = await idempotency_cache.get_task_id(request.client_request_id)
        if existing_task_id:
            logger.info(f"Returning existing task for client_request_id: {request.client_request_id}")
            return TaskResponse(task_id=existing_task_id, status="PENDING")
    
    if request.model not in ModelRegistry.list_models():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model {request.model} not supported. Available models: {ModelRegistry.list_models()}"
        )
    
    task_id = str(uuid.uuid4())
    
    queue_name = f"gpu-{request.priority}"
    
    task = celery_app.send_task(
        "app.tasks.gpu_worker.process_inference",
        args=[task_id, request.model, request.input, request.callback_url],
        queue=queue_name,
        task_id=task_id,
        priority={"high": 9, "normal": 5, "low": 1}[request.priority]
    )
    
    if request.client_request_id:
        await idempotency_cache.set_task_id(request.client_request_id, task_id)
    
    task_submitted.labels(model=request.model, priority=request.priority).inc()
    
    logger.info(f"Task submitted", task_id=task_id, model=request.model, priority=request.priority)
    
    return TaskResponse(task_id=task_id, status="PENDING")


@app.get("/v1/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    task = celery_app.AsyncResult(task_id)
    
    if task.state == "PENDING":
        status_data = {
            "task_id": task_id,
            "status": "PENDING"
        }
    elif task.state == "STARTED":
        status_data = {
            "task_id": task_id,
            "status": "STARTED"
        }
    elif task.state == "SUCCESS":
        result = task.result
        status_data = {
            "task_id": task_id,
            "status": "SUCCESS",
            "timing": result.get("timing"),
            "result": result.get("result")
        }
    elif task.state == "FAILURE":
        status_data = {
            "task_id": task_id,
            "status": "FAILURE",
            "error": str(task.info)
        }
    elif task.state == "RETRY":
        status_data = {
            "task_id": task_id,
            "status": "RETRY",
            "error": str(task.info)
        }
    else:
        status_data = {
            "task_id": task_id,
            "status": task.state
        }
    
    task_status_checked.labels(status=status_data["status"]).inc()
    
    return TaskStatus(**status_data)


if settings.prometheus_enabled:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)