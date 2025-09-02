from typing import List, Optional
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    app_name: str = "Inference Server"
    debug: bool = False
    environment: str = "development"
    
    api_keys: List[str] = ["test-key-123"]
    rate_limit_per_minute: int = 60
    
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    celery_result_backend: str = "redis://localhost:6379/1"
    
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "inference-results"
    s3_use_ssl: bool = False
    use_local_storage: bool = True
    local_storage_path: str = "./data"
    
    gpu_ids: Optional[str] = None
    max_retries: int = 3
    retry_backoff: int = 60
    
    prometheus_enabled: bool = True
    
    callback_timeout: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        
    @property
    def gpu_list(self) -> List[int]:
        if self.gpu_ids:
            return [int(x) for x in self.gpu_ids.split(",")]
        return []


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()