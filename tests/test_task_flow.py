from unittest.mock import Mock, patch

import pytest
import torch
from fastapi.testclient import TestClient

from app.deps.ratelimit import RateLimiter
from app.main import app
from app.models.base import BaseModelRunner, ModelConfig
from app.models.registry import ModelRegistry
from app.utils.idempotency import IdempotencyCache


class MockModelRunner(BaseModelRunner):
    def load_model(self):
        self.model = Mock()

    def prepare(self, input_data):
        return torch.randn(1, 3, 224, 224)

    def infer(self, tensor):
        return torch.randn(1, 3, 896, 896)

    def postprocess(self, output):
        return {"image_bytes": b"fake_image_data", "size": [896, 896], "format": "PNG"}


@pytest.fixture
def client(monkeypatch):
    # Override settings for testing
    monkeypatch.setattr("app.config.settings.api_keys", ["test-key-123"])
    monkeypatch.setattr("app.deps.auth.settings.api_keys", ["test-key-123"])
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_celery_app():
    with patch("app.main.celery_app") as mock:
        mock_task = Mock()
        mock_task.id = "test-task-123"
        mock.send_task.return_value = mock_task

        mock_result = Mock()
        mock_result.state = "SUCCESS"
        mock_result.result = {
            "timing": {"prepare_ms": 100, "infer_ms": 500, "upload_ms": 50},
            "result": {"s3_key": "results/test.png", "size": [2048, 2048]},
        }
        mock.AsyncResult.return_value = mock_result

        yield mock


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_submit_task_without_auth(client):
    response = client.post(
        "/v1/tasks",
        json={"model": "superres-x4", "input": {"image_url": "https://example.com/test.jpg"}},
    )
    assert response.status_code == 401


def test_submit_task_with_auth(client, mock_celery_app):
    ModelRegistry.register("superres-x4", MockModelRunner)

    response = client.post(
        "/v1/tasks",
        json={
            "model": "superres-x4",
            "input": {"image_url": "https://example.com/test.jpg"},
            "priority": "high",
        },
        headers={"x-api-key": "test-key-123"},
    )

    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "PENDING"

    mock_celery_app.send_task.assert_called_once()
    call_args = mock_celery_app.send_task.call_args
    assert call_args[1]["queue"] == "gpu-high"
    assert call_args[1]["priority"] == 9


def test_submit_task_invalid_model(client, mock_celery_app):
    response = client.post(
        "/v1/tasks",
        json={"model": "invalid-model", "input": {"image_url": "https://example.com/test.jpg"}},
        headers={"x-api-key": "test-key-123"},
    )

    assert response.status_code == 400
    assert "not supported" in response.json()["detail"]


def test_get_task_status(client, mock_celery_app):
    response = client.get("/v1/tasks/test-task-123", headers={"x-api-key": "test-key-123"})

    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "test-task-123"
    assert data["status"] == "SUCCESS"
    assert "timing" in data
    assert "result" in data


@pytest.mark.asyncio
async def test_idempotency_cache():
    cache = IdempotencyCache(ttl_seconds=60)

    await cache.set_task_id("client-123", "task-456")

    task_id = await cache.get_task_id("client-123")
    assert task_id == "task-456"

    task_id = await cache.get_task_id("nonexistent")
    assert task_id is None

    await cache.clear()
    task_id = await cache.get_task_id("client-123")
    assert task_id is None


@pytest.mark.asyncio
async def test_idempotency_by_content():
    cache = IdempotencyCache()

    request_data = {"model": "test", "input": {"key": "value"}}
    await cache.set_by_content(request_data, "task-789")

    task_id = await cache.get_by_content(request_data)
    assert task_id == "task-789"

    different_data = {"model": "test2", "input": {"key": "value2"}}
    task_id = await cache.get_by_content(different_data)
    assert task_id is None


@pytest.mark.asyncio
async def test_rate_limiter():
    limiter = RateLimiter(requests_per_minute=2)

    await limiter.check_rate_limit("test-key")
    await limiter.check_rate_limit("test-key")

    with pytest.raises(Exception) as exc_info:
        await limiter.check_rate_limit("test-key")
    assert "429" in str(exc_info.value)

    await limiter.reset("test-key")

    await limiter.check_rate_limit("test-key")


def test_model_registry():
    ModelRegistry.register("test-model", MockModelRunner)

    assert "test-model" in ModelRegistry.list_models()

    runner_class = ModelRegistry.get_runner_class("test-model")
    assert runner_class == MockModelRunner

    config = ModelConfig(model_name="test-model", device="cpu")
    runner = ModelRegistry.create_runner(config)
    assert isinstance(runner, MockModelRunner)

    cached_runner = ModelRegistry.get_or_create_runner(config)
    assert cached_runner is not None

    ModelRegistry.cleanup()


def test_submit_task_with_idempotency(client, mock_celery_app):
    ModelRegistry.register("superres-x4", MockModelRunner)

    request_data = {
        "model": "superres-x4",
        "input": {"image_url": "https://example.com/test.jpg"},
        "client_request_id": "unique-request-123",
    }

    response1 = client.post("/v1/tasks", json=request_data, headers={"x-api-key": "test-key-123"})
    assert response1.status_code == 202
    task_id1 = response1.json()["task_id"]

    with patch("app.main.idempotency_cache.get_task_id", return_value=task_id1):
        response2 = client.post(
            "/v1/tasks", json=request_data, headers={"x-api-key": "test-key-123"}
        )
        assert response2.status_code == 202
        task_id2 = response2.json()["task_id"]

        assert task_id1 == task_id2
