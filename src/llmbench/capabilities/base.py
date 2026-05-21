"""
Base capability test interface
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict
from ..cube import BenchmarkPoint


@dataclass
class TestCase:
    """A single test case for a capability"""
    input_data: str
    expected_output: Any
    complexity: int
    sensitivity: int
    metadata: Dict[str, Any] | None = None


class CapabilityTest(ABC):
    """Base class for capability-specific tests"""

    @abstractmethod
    def get_test_cases(self) -> list[TestCase]:
        """Return all test cases for this capability"""
        pass

    @abstractmethod
    def evaluate(self, output: str, expected: Any, test_case: TestCase) -> float:
        """
        Evaluate model output against expected result.
        Returns a score between 0 and 1.
        """
        pass

    @abstractmethod
    def build_prompt(self, test_case: TestCase) -> str:
        """Build the prompt to send to the model"""
        pass
