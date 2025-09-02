from typing import Dict, Type, Optional
from app.models.base import BaseModelRunner, ModelConfig
import structlog

logger = structlog.get_logger()


class ModelRegistry:
    _runners: Dict[str, Type[BaseModelRunner]] = {}
    _instances: Dict[str, BaseModelRunner] = {}
    
    @classmethod
    def register(cls, model_name: str, runner_class: Type[BaseModelRunner]) -> None:
        if model_name in cls._runners:
            logger.warning(f"Model {model_name} already registered, overwriting")
        cls._runners[model_name] = runner_class
        logger.info(f"Registered model runner: {model_name}")
    
    @classmethod
    def get_runner_class(cls, model_name: str) -> Optional[Type[BaseModelRunner]]:
        return cls._runners.get(model_name)
    
    @classmethod
    def create_runner(cls, config: ModelConfig) -> BaseModelRunner:
        runner_class = cls.get_runner_class(config.model_name)
        if runner_class is None:
            raise ValueError(f"Model {config.model_name} not registered")
        
        runner = runner_class(config)
        return runner
    
    @classmethod
    def get_or_create_runner(cls, config: ModelConfig) -> BaseModelRunner:
        cache_key = f"{config.model_name}_{config.gpu_id}"
        
        if cache_key not in cls._instances:
            cls._instances[cache_key] = cls.create_runner(config)
            logger.info(f"Created new runner instance for {cache_key}")
        
        return cls._instances[cache_key]
    
    @classmethod
    def list_models(cls) -> list[str]:
        return list(cls._runners.keys())
    
    @classmethod
    def cleanup(cls, model_name: Optional[str] = None, gpu_id: Optional[int] = None) -> None:
        if model_name and gpu_id is not None:
            cache_key = f"{model_name}_{gpu_id}"
            if cache_key in cls._instances:
                cls._instances[cache_key].cleanup()
                del cls._instances[cache_key]
                logger.info(f"Cleaned up runner instance for {cache_key}")
        else:
            for key, runner in cls._instances.items():
                runner.cleanup()
            cls._instances.clear()
            logger.info("Cleaned up all runner instances")


def model_runner(model_name: str):
    def decorator(cls: Type[BaseModelRunner]):
        ModelRegistry.register(model_name, cls)
        return cls
    return decorator