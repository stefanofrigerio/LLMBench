"""
Core cube model representing the 3D space of:
- Capability (what the model needs to do)
- Complexity (how hard the task is)
- Sensitivity (how critical correct execution is)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any


class Capability(str, Enum):
    """Types of tasks the model can perform"""
    CODE_GENERATION = "code_generation"
    UNIT_TEST_WRITING = "unit_test_writing"
    OCR = "ocr"
    TEXT_SUMMARIZATION = "text_summarization"
    DATA_TRANSFORMATION = "data_transformation"
    REASONING = "reasoning"
    STRUCTURED_OUTPUT = "structured_output"
    TRANSLATION = "translation"


@dataclass
class BenchmarkPoint:
    """
    A single point in the capability-complexity-sensitivity cube
    """
    capability: Capability
    complexity: int  # 1-5 scale
    sensitivity: int  # 1-5 scale

    def __post_init__(self):
        if not 1 <= self.complexity <= 5:
            raise ValueError("Complexity must be between 1 and 5")
        if not 1 <= self.sensitivity <= 5:
            raise ValueError("Sensitivity must be between 1 and 5")

    def to_key(self) -> str:
        """Generate a unique key for this point"""
        return f"{self.capability.value}_{self.complexity}_{self.sensitivity}"


@dataclass
class BenchmarkResult:
    """Result of a benchmark test"""
    point: BenchmarkPoint
    model_name: str
    score: float  # 0-1 performance score
    latency_ms: float
    cost_estimate: float  # relative cost
    error: str | None = None
    raw_output: str | None = None
    metadata: Dict[str, Any] | None = None
