from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import torch
from pydantic import BaseModel


class ModelConfig(BaseModel):
    model_name: str
    device: str = "cuda"
    gpu_id: Optional[int] = None
    batch_size: int = 1
    extra_config: Dict[str, Any] = {}


class BaseModelRunner(ABC):
    def __init__(self, config: ModelConfig):
        self.config = config
        self.device = self._setup_device()
        self.model = None
        self.is_loaded = False
    
    def _setup_device(self) -> torch.device:
        if self.config.gpu_id is not None:
            return torch.device(f"cuda:{self.config.gpu_id}")
        elif self.config.device == "cuda" and torch.cuda.is_available():
            return torch.device("cuda")
        else:
            return torch.device("cpu")
    
    @abstractmethod
    def load_model(self) -> None:
        pass
    
    @abstractmethod
    def prepare(self, input_data: Dict[str, Any]) -> torch.Tensor:
        pass
    
    @abstractmethod
    def infer(self, tensor: torch.Tensor) -> torch.Tensor:
        pass
    
    @abstractmethod
    def postprocess(self, output: torch.Tensor) -> Dict[str, Any]:
        pass
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_loaded:
            self.load_model()
            self.is_loaded = True
        
        input_tensor = self.prepare(input_data)
        
        with torch.no_grad():
            output_tensor = self.infer(input_tensor)
        
        result = self.postprocess(output_tensor)
        
        return result
    
    def cleanup(self) -> None:
        if self.model is not None:
            del self.model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        self.is_loaded = False