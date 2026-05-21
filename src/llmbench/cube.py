"""
Core cube model representing the 2D benchmark space:
- Capability (what the model needs to do)
- Complexity (how hard the task is, 1-5)

Sensitivity is a query-time parameter supplied by the caller,
not a property of the benchmark itself. It maps to a minimum
score threshold for model recommendation.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional


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
    INVOICE_EXTRACTOR = "invoice_extractor"


# Linear mapping: sensitivity 1-5 → minimum acceptable score 0.60-0.95
SENSITIVITY_THRESHOLDS: Dict[int, float] = {
    1: 0.60,  # Low: minimal impact if wrong
    2: 0.70,  # Minor: noticeable but not critical
    3: 0.80,  # Medium: affects functionality
    4: 0.90,  # High: could cause significant issues
    5: 0.95,  # Critical: severe consequences if wrong
}


def sensitivity_to_threshold(sensitivity: int) -> float:
    """Convert a sensitivity level (1-5) to a minimum score threshold."""
    if not 1 <= sensitivity <= 5:
        raise ValueError(f"Sensitivity must be between 1 and 5, got {sensitivity}")
    return SENSITIVITY_THRESHOLDS[sensitivity]


@dataclass
class BenchmarkPoint:
    """
    A single point in the capability × complexity benchmark space.

    Sensitivity is intentionally absent: it is a business context parameter
    provided at query time, not a property measurable during benchmarking.
    """
    capability: Capability
    complexity: int  # 1-5 scale

    def __post_init__(self):
        if not 1 <= self.complexity <= 5:
            raise ValueError(f"Complexity must be between 1 and 5, got {self.complexity}")

    def to_key(self) -> str:
        """Generate a unique key for this point"""
        return f"{self.capability.value}_{self.complexity}"


@dataclass
class BenchmarkResult:
    """Result of a benchmark test at a specific (capability, complexity) point"""
    point: BenchmarkPoint
    model_name: str
    score: float        # 0-1 performance score
    latency_ms: float
    cost_estimate: float
    error: Optional[str] = None
    raw_output: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
