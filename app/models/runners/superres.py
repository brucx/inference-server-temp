import base64
import io
import random
import time
from typing import Any

import httpx
import numpy as np
import structlog
import torch
from PIL import Image

from app.models.base import BaseModelRunner
from app.models.registry import model_runner

logger = structlog.get_logger()


@model_runner("superres-x4")
class SuperResolutionRunner(BaseModelRunner):
    def load_model(self) -> None:
        logger.info(f"Loading SuperResolution model on {self.device}")
        time.sleep(2)

        self.model = torch.nn.Sequential(
            torch.nn.Conv2d(3, 64, 3, padding=1),
            torch.nn.ReLU(),
            torch.nn.Conv2d(64, 3, 3, padding=1),
            torch.nn.Upsample(scale_factor=4, mode="bilinear", align_corners=False),
        ).to(self.device)

        logger.info("SuperResolution model loaded successfully")

    def prepare(self, input_data: dict[str, Any]) -> torch.Tensor:
        if "image_url" in input_data:
            response = httpx.get(input_data["image_url"], timeout=30)
            response.raise_for_status()
            image_bytes = response.content
        elif "image_base64" in input_data:
            image_bytes = base64.b64decode(input_data["image_base64"])
        else:
            raise ValueError("Either image_url or image_base64 must be provided")

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        self.original_size = image.size

        image_array = np.array(image).astype(np.float32) / 255.0
        image_tensor = torch.from_numpy(image_array).permute(2, 0, 1).unsqueeze(0)

        return image_tensor.to(self.device)

    def infer(self, tensor: torch.Tensor) -> torch.Tensor:
        inference_time = random.uniform(0.5, 1.5)
        logger.info(f"Running SuperResolution inference for {inference_time:.2f}s")
        time.sleep(inference_time)

        output = self.model(tensor)

        return output

    def postprocess(self, output: torch.Tensor) -> dict[str, Any]:
        output_numpy = output.squeeze(0).permute(1, 2, 0).cpu().numpy()
        output_numpy = np.clip(output_numpy * 255, 0, 255).astype(np.uint8)

        output_image = Image.fromarray(output_numpy)

        output_buffer = io.BytesIO()
        output_image.save(output_buffer, format="PNG")
        output_bytes = output_buffer.getvalue()

        new_width = self.original_size[0] * 4
        new_height = self.original_size[1] * 4

        return {
            "image_bytes": output_bytes,
            "size": [new_width, new_height],
            "format": "PNG",
            "scale_factor": 4,
            "original_size": list(self.original_size),
        }
