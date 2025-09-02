import structlog
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

logger = structlog.get_logger()

registry = CollectorRegistry()

task_submitted = Counter(
    "inference_task_submitted_total",
    "Total number of tasks submitted",
    ["model", "priority"],
    registry=registry,
)

task_completed = Counter(
    "inference_task_completed_total",
    "Total number of tasks completed successfully",
    ["model"],
    registry=registry,
)

task_failed = Counter(
    "inference_task_failed_total", "Total number of tasks failed", registry=registry
)

task_status_checked = Counter(
    "inference_task_status_checked_total",
    "Total number of task status checks",
    ["status"],
    registry=registry,
)

inference_duration = Histogram(
    "inference_duration_seconds",
    "Time spent in model inference",
    ["model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    registry=registry,
)

storage_duration = Histogram(
    "storage_duration_seconds",
    "Time spent uploading results to storage",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=registry,
)

total_duration = Histogram(
    "task_total_duration_seconds",
    "Total time to process a task",
    ["model"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
    registry=registry,
)

active_workers = Gauge(
    "inference_active_workers", "Number of active GPU workers", ["gpu_id"], registry=registry
)

model_load_duration = Histogram(
    "model_load_duration_seconds",
    "Time to load a model",
    ["model"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=registry,
)

queue_size = Gauge(
    "inference_queue_size", "Number of tasks in queue", ["priority"], registry=registry
)

api_request_duration = Histogram(
    "api_request_duration_seconds",
    "API request duration",
    ["endpoint", "method", "status"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    registry=registry,
)

rate_limit_exceeded = Counter(
    "rate_limit_exceeded_total",
    "Number of rate limit exceeded errors",
    ["api_key"],
    registry=registry,
)

auth_failures = Counter(
    "auth_failures_total", "Number of authentication failures", registry=registry
)


def setup_metrics():
    logger.info("Prometheus metrics initialized")
