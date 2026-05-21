"""
Base interface for LLM models
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class ModelConfig:
    """Configuration for a model"""
    name: str
    provider: str  # ollama, openai, anthropic, etc
    model_id: str
    temperature: float = 0.7
    max_tokens: int = 2048
    additional_params: Dict[str, Any] | None = None


class BaseModel(ABC):
    """Base class for all model implementations"""

    def __init__(self, config: ModelConfig):
        self.config = config

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate a response from the model"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the model is available and responding"""
        pass

    @property
    def name(self) -> str:
        return self.config.name
