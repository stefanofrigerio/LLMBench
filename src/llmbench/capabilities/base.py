"""
Base capability test interface
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TestCase:
    """A single test case for a capability"""
    input_data: str
    expected_output: Any
    complexity: int          # 1-5: intrinsic difficulty of the task
    metadata: Optional[Dict[str, Any]] = field(default=None)


class CapabilityTest(ABC):
    """Base class for capability-specific tests"""

    @abstractmethod
    def get_test_cases(self) -> List[TestCase]:
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
