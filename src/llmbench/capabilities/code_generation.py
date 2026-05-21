"""
Code generation capability tests
"""

from .base import CapabilityTest, TestCase
from typing import List


class CodeGenerationTest(CapabilityTest):
    """Tests for code generation capability"""

    def get_test_cases(self) -> List[TestCase]:
        return [
            # Complexity 1, Sensitivity 1: Simple string manipulation
            TestCase(
                input_data="Write a Python function that reverses a string",
                expected_output="def reverse_string(s: str) -> str:\n    return s[::-1]",
                complexity=1,
                sensitivity=1,
                metadata={"category": "string_manipulation"}
            ),

            # Complexity 2, Sensitivity 2: Basic algorithm
            TestCase(
                input_data="Write a Python function that checks if a number is prime",
                expected_output="prime check logic",
                complexity=2,
                sensitivity=2,
                metadata={"category": "algorithms"}
            ),

            # Complexity 3, Sensitivity 3: Data structure manipulation
            TestCase(
                input_data="Write a Python function that merges two sorted lists into one sorted list",
                expected_output="merge logic",
                complexity=3,
                sensitivity=3,
                metadata={"category": "data_structures"}
            ),

            # Complexity 4, Sensitivity 4: Complex business logic
            TestCase(
                input_data="Write a Python class that implements a LRU cache with O(1) get and put operations",
                expected_output="lru cache implementation",
                complexity=4,
                sensitivity=4,
                metadata={"category": "data_structures"}
            ),

            # Complexity 5, Sensitivity 5: Advanced algorithm
            TestCase(
                input_data="Write a Python function that solves the traveling salesman problem using dynamic programming",
                expected_output="tsp solution",
                complexity=5,
                sensitivity=5,
                metadata={"category": "algorithms"}
            ),
        ]

    def evaluate(self, output: str, expected: str, test_case: TestCase) -> float:
        """
        Evaluate generated code.
        This is a simplified evaluation - in production you'd want to:
        - Parse the code
        - Run test cases
        - Check for correct imports
        - Validate syntax
        """
        score = 0.0

        # Check if output contains code-like patterns
        if "def " in output or "class " in output:
            score += 0.3

        # Check for type hints (good practice)
        if "->" in output or ": " in output:
            score += 0.2

        # Check for docstrings
        if '"""' in output or "'''" in output:
            score += 0.1

        # Check if it's not empty and has reasonable length
        if len(output) > 50:
            score += 0.2

        # Complexity-based evaluation
        lines = output.split("\n")
        if len(lines) >= test_case.complexity * 2:
            score += 0.2

        return min(score, 1.0)

    def build_prompt(self, test_case: TestCase) -> str:
        """Build the prompt for code generation"""
        return f"""{test_case.input_data}

Requirements:
- Write clean, idiomatic Python code
- Include type hints
- Add a brief docstring
- Handle edge cases appropriately

Provide only the code, no explanations."""
