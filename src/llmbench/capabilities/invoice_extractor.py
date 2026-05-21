"""
Invoice extraction capability.

Given invoice text, the model must extract the total amount exactly as it
appears (e.g. "150$"). Scoring is exact-match with whitespace normalization.
"""

from typing import Any
from .base import GroundTruthCapabilityTest, TestCase


class InvoiceExtractorTest(GroundTruthCapabilityTest):
    capability_name = "invoice_extractor"

    def evaluate(self, output: str, expected: Any, test_case: TestCase) -> float:
        return 1.0 if output.strip() == str(expected).strip() else 0.0

    def build_prompt(self, test_case: TestCase) -> str:
        return (
            f"Extract the total amount from the following invoice text.\n"
            f"Reply with the amount only — no explanation, no extra words.\n\n"
            f"{test_case.input_data}"
        )
