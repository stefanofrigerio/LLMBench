"""
Ollama model implementation
"""

import aiohttp
from typing import Optional
from .base import BaseModel, ModelConfig


class OllamaModel(BaseModel):
    """Ollama local model implementation"""

    def __init__(self, config: ModelConfig, base_url: str = "http://localhost:11434"):
        super().__init__(config)
        self.base_url = base_url

    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate response using Ollama API"""
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.config.model_id,
            "prompt": prompt,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": False,
        }

        if self.config.additional_params:
            payload.update(self.config.additional_params)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    raise RuntimeError(f"Ollama API error: {response.status}")

                result = await response.json()
                return result.get("response", "")

    async def health_check(self) -> bool:
        """Check if Ollama is running and model is available"""
        try:
            url = f"{self.base_url}/api/tags"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [m["name"] for m in data.get("models", [])]
                        return self.config.model_id in models
            return False
        except Exception:
            return False
