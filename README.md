# Inference Server

A production-ready FastAPI + Celery based GPU inference server for long-running batch processing tasks.

## Features

- **Model Abstraction Layer**: Pluggable model runners following Open/Closed Principle
- **GPU Worker Management**: One process per GPU with model reuse
- **Task Queue**: Priority-based queues (high/normal/low) with Celery + RabbitMQ
- **Storage**: S3/MinIO compatible storage with local fallback
- **Observability**: Prometheus metrics, structured JSON logging
- **Reliability**: Retry with exponential backoff, idempotency, graceful shutdown
- **Security**: API key authentication, rate limiting
- **Monitoring**: Flower for Celery, Grafana dashboards

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI     │────▶│  RabbitMQ   │
└─────────────┘     │   Gateway    │     └─────────────┘
                    └──────────────┘              │
                           │                      ▼
                    ┌──────────────┐     ┌─────────────┐
                    │  Prometheus  │◀────│   Celery    │
                    └──────────────┘     │   Workers   │
                           │             └─────────────┘
                    ┌──────────────┐              │
                    │   Grafana    │              ▼
                    └──────────────┘     ┌─────────────┐
                                        │  S3/MinIO   │
                                        └─────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- NVIDIA GPU drivers (optional, for GPU workers)
- uv (Python package manager)

### Installation

1. Clone the repository and install dependencies:

```bash
# Install uv if not already installed
pip install uv

# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # On Linux/macOS
# Or on Windows:
# .venv\Scripts\activate

# Install project dependencies with dev extras
uv pip install -e ".[dev]"

# Alternatively, install to system Python (not recommended)
# uv pip install --system -e ".[dev]"
```

2. Set up environment:

```bash
make init-env
# Edit .env file with your configuration
```

3. Start all services:

```bash
make up
```

## Usage

### Submit a Task

```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "x-api-key: test-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "superres-x4",
    "input": {"image_url": "https://example.com/image.jpg"},
    "priority": "high",
    "client_request_id": "unique-123"
  }'
```

Response:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING"
}
```

### Check Task Status

```bash
curl -X GET http://localhost:8000/v1/tasks/550e8400-e29b-41d4-a716-446655440000 \
  -H "x-api-key: test-key-123"
```

Response:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SUCCESS",
  "timing": {
    "prepare_ms": 120,
    "infer_ms": 850,
    "upload_ms": 60
  },
  "result": {
    "s3_key": "results/550e8400-e29b-41d4-a716-446655440000.png",
    "size": [2048, 2048]
  }
}
```

## Available Models

- `superres-x4`: Image super-resolution (4x upscaling)
- `image-scoring-v1`: Image quality scoring

## Adding New Models

1. Create a new runner in `app/models/runners/`:

```python
from app.models.base import BaseModelRunner
from app.models.registry import model_runner

@model_runner("your-model-name")
class YourModelRunner(BaseModelRunner):
    def load_model(self):
        # Load your model here
        pass
    
    def prepare(self, input_data):
        # Prepare input tensor
        pass
    
    def infer(self, tensor):
        # Run inference
        pass
    
    def postprocess(self, output):
        # Process output
        pass
```

2. Import the runner in `app/models/runners/__init__.py`

3. The model will be automatically registered and available via the API

## Development

### Run Tests

```bash
make test
```

### Lint & Format

```bash
make lint    # Check code style
make format  # Auto-format code
```

### Local Development

```bash
# Run API server
make dev

# Run worker
make worker

# Run Flower (Celery monitoring)
make flower
```

## Monitoring

- **API Documentation**: http://localhost:8000/docs
- **Metrics**: http://localhost:8000/metrics
- **Flower (Celery)**: http://localhost:5555
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)
- **RabbitMQ Management**: http://localhost:15672 (admin/admin123)
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

## Configuration

See `.env.example` for all available configuration options:

- `API_KEYS`: Comma-separated API keys for authentication
- `RATE_LIMIT_PER_MINUTE`: Rate limit per API key
- `GPU_IDS`: Comma-separated GPU IDs for workers
- `MAX_RETRIES`: Maximum retry count for failed tasks
- `USE_LOCAL_STORAGE`: Use local filesystem instead of S3

## Docker Commands

```bash
make up       # Start all services
make down     # Stop all services
make logs     # View logs
make restart  # Restart services
make status   # Check service status
```

## Project Structure

```
.
├── app/
│   ├── main.py                # FastAPI application
│   ├── config.py              # Configuration
│   ├── models/
│   │   ├── base.py           # Base model runner
│   │   ├── registry.py       # Model registry
│   │   └── runners/          # Model implementations
│   ├── services/
│   │   ├── storage.py        # S3/MinIO storage
│   │   └── metrics.py        # Prometheus metrics
│   ├── tasks/
│   │   ├── celery_app.py     # Celery configuration
│   │   └── gpu_worker.py     # Worker tasks
│   ├── deps/
│   │   ├── auth.py           # API authentication
│   │   └── ratelimit.py      # Rate limiting
│   └── utils/
│       ├── idempotency.py    # Idempotency handling
│       └── timing.py          # Performance timing
├── tests/                     # Test files
├── docker-compose.yml         # Docker services
├── Dockerfile.api            # API container
├── Dockerfile.worker         # Worker container
├── pyproject.toml            # Python dependencies
└── Makefile                  # Development commands
```

## License

MIT
