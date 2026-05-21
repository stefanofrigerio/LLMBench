"""
Code generation capability tests.

Test cases are organized by complexity only. Sensitivity is a business
context parameter supplied at query time, not a benchmark property.
"""

from typing import List, Any
from .base import CapabilityTest, TestCase


class CodeGenerationTest(CapabilityTest):
    """Tests for code generation capability"""

    def get_test_cases(self) -> List[TestCase]:
        return [
            TestCase(
                input_data="Write a Python function that reverses a string",
                expected_output="def reverse_string(s: str) -> str:\n    return s[::-1]",
                complexity=1,
                metadata={"category": "string_manipulation"},
            ),
            TestCase(
                input_data="Write a Python function that checks if a number is prime",
                expected_output="prime check logic",
                complexity=2,
                metadata={"category": "algorithms"},
            ),
            TestCase(
                input_data="Write a Python function that merges two sorted lists into one sorted list",
                expected_output="merge logic",
                complexity=3,
                metadata={"category": "data_structures"},
            ),
            TestCase(
                input_data="Write a Python class that implements a LRU cache with O(1) get and put operations",
                expected_output="lru cache implementation",
                complexity=4,
                metadata={"category": "data_structures"},
            ),
            TestCase(
                input_data="Write a Python function that solves the traveling salesman problem using dynamic programming",
                expected_output="tsp solution",
                complexity=5,
                metadata={"category": "algorithms"},
            ),
        ]

    def evaluate(self, output: str, expected: Any, test_case: TestCase) -> float:
        score = 0.0

        if "def " in output or "class " in output:
            score += 0.3
        if "->" in output or ": " in output:
            score += 0.2
        if '"""' in output or "'''" in output:
            score += 0.1
        if len(output) > 50:
            score += 0.2

        lines = output.split("\n")
        if len(lines) >= test_case.complexity * 2:
            score += 0.2

        return min(score, 1.0)

    def build_prompt(self, test_case: TestCase) -> str:
        return f"""{test_case.input_data}

Requirements:
- Write clean, idiomatic Python code
- Include type hints
- Add a brief docstring
- Handle edge cases appropriately

Provide only the code, no explanations."""
