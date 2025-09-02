import time
import random
from typing import Any, Dict
import torch
import numpy as np
from PIL import Image
import io
import base64
import httpx
from app.models.base import BaseModelRunner
from app.models.registry import model_runner
import structlog

logger = structlog.get_logger()


@model_runner("image-scoring-v1")
class ImageScoringRunner(BaseModelRunner):
    def load_model(self) -> None:
        logger.info(f"Loading ImageScoring model on {self.device}")
        time.sleep(1.5)
        
        self.model = torch.nn.Sequential(
            torch.nn.Conv2d(3, 32, 3, stride=2, padding=1),
            torch.nn.ReLU(),
            torch.nn.Conv2d(32, 64, 3, stride=2, padding=1),
            torch.nn.ReLU(),
            torch.nn.AdaptiveAvgPool2d((1, 1)),
            torch.nn.Flatten(),
            torch.nn.Linear(64, 5)
        ).to(self.device)
        
        logger.info("ImageScoring model loaded successfully")
    
    def prepare(self, input_data: Dict[str, Any]) -> torch.Tensor:
        if "image_url" in input_data:
            response = httpx.get(input_data["image_url"], timeout=30)
            response.raise_for_status()
            image_bytes = response.content
        elif "image_base64" in input_data:
            image_bytes = base64.b64decode(input_data["image_base64"])
        else:
            raise ValueError("Either image_url or image_base64 must be provided")
        
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        image = image.resize((224, 224), Image.Resampling.LANCZOS)
        
        self.image_metadata = {
            "original_size": image.size,
            "format": image.format or "UNKNOWN",
            "mode": image.mode
        }
        
        image_array = np.array(image).astype(np.float32) / 255.0
        image_tensor = torch.from_numpy(image_array).permute(2, 0, 1).unsqueeze(0)
        
        return image_tensor.to(self.device)
    
    def infer(self, tensor: torch.Tensor) -> torch.Tensor:
        inference_time = random.uniform(0.3, 0.8)
        logger.info(f"Running ImageScoring inference for {inference_time:.2f}s")
        time.sleep(inference_time)
        
        scores = self.model(tensor)
        
        scores = torch.sigmoid(scores)
        
        return scores
    
    def postprocess(self, output: torch.Tensor) -> Dict[str, Any]:
        scores = output.squeeze(0).cpu().numpy()
        
        score_labels = [
            "quality",
            "aesthetics",
            "sharpness",
            "color_balance",
            "composition"
        ]
        
        scores_dict = {label: float(score) for label, score in zip(score_labels, scores)}
        
        overall_score = float(np.mean(scores))
        
        quality_assessment = "excellent" if overall_score > 0.8 else \
                           "good" if overall_score > 0.6 else \
                           "average" if overall_score > 0.4 else \
                           "below_average" if overall_score > 0.2 else "poor"
        
        return {
            "scores": scores_dict,
            "overall_score": overall_score,
            "quality_assessment": quality_assessment,
            "metadata": self.image_metadata,
            "confidence": random.uniform(0.85, 0.99)
        }