"""
Invoice extraction capability.

Supports two input modes depending on what is stored in TestCase.input_data:
  - Text mode:  input_data is the raw invoice text. The model must return the
                total amount exactly as it appears (e.g. "150$").
  - Image mode: input_data is an absolute path to a JPEG/PNG invoice image.
                The model must return the total amount from the image.

Scoring extracts a dollar/euro amount from both expected and actual output
and compares them, so minor formatting differences don't cause false negatives.
"""

import re
from pathlib import Path
from typing import Any
from .base import GroundTruthCapabilityTest, TestCase


_AMOUNT_RE = re.compile(r'[\$€£]?\s*\d[\d,]*\.?\d*\s*[\$€£]?')


def _extract_amount(text: str) -> str | None:
    """Return the first currency amount found in text, normalised."""
    m = _AMOUNT_RE.search(text)
    if not m:
        return None
    return re.sub(r'[\s,]', '', m.group()).strip()


def _is_image_path(value: str) -> bool:
    return Path(value).suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


class InvoiceExtractorTest(GroundTruthCapabilityTest):
    capability_name = "invoice_extractor"

    def evaluate(self, output: str, expected: Any, test_case: TestCase) -> float:
        expected_str = str(expected).strip()
        output_str = output.strip()

        # Fast path: exact match
        if output_str == expected_str:
            return 1.0

        # Try amount-level match (handles whitespace, comma formatting, currency symbol position)
        expected_amount = _extract_amount(expected_str)
        output_amount = _extract_amount(output_str)
        if expected_amount and output_amount and expected_amount == output_amount:
            return 1.0

        return 0.0

    def build_prompt(self, test_case: TestCase) -> str:
        if _is_image_path(test_case.input_data):
            return (
                "Look at this invoice image.\n"
                "Extract the total amount due.\n"
                "Reply with the amount only — no explanation, no extra words."
            )
        return (
            "Extract the total amount from the following invoice text.\n"
            "Reply with the amount only — no explanation, no extra words.\n\n"
            f"{test_case.input_data}"
        )

    async def run(self, model: Any, test_case: TestCase) -> str:
        """Override to use vision API when input is an image."""
        if _is_image_path(test_case.input_data):
            return await model.generate_with_image(
                self.build_prompt(test_case),
                test_case.input_data,
            )
        return await model.generate(self.build_prompt(test_case))
