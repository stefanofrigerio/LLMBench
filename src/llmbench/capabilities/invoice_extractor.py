"""
Invoice extraction capability.

The model receives an invoice (image or text) and must return a JSON object
with the following fields:

  invoice_number, date, due_date, payment_terms,
  emitter   { name, address, city, state, zip },
  recipient { name, address, city, state, zip },
  items     [ { description, quantity, unit_price, amount } ],
  subtotal, tax, total, currency

Scoring: field-level comparison. Each top-level field that matches contributes
to the final score. Numeric fields allow ±1% tolerance. String fields are
compared case-insensitively after normalising whitespace.
"""

import json
import re
from pathlib import Path
from typing import Any
from .base import GroundTruthCapabilityTest, TestCase

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

# Fields and their weights (must sum to 1.0)
_FIELD_WEIGHTS: dict[str, float] = {
    "invoice_number": 0.05,
    "date":           0.05,
    "due_date":       0.05,
    "payment_terms":  0.05,
    "emitter":        0.15,
    "recipient":      0.15,
    "items":          0.25,
    "subtotal":       0.05,
    "tax":            0.05,
    "total":          0.10,
    "currency":       0.05,
}

_PROMPT = """\
Extract all information from this invoice and return ONLY a JSON object with this exact structure:
{
  "invoice_number": "...",
  "date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD",
  "payment_terms": "...",
  "emitter": { "name": "...", "address": "...", "city": "...", "state": "...", "zip": "..." },
  "recipient": { "name": "...", "address": "...", "city": "...", "state": "...", "zip": "..." },
  "items": [
    { "description": "...", "quantity": <number>, "unit_price": <number>, "amount": <number> }
  ],
  "subtotal": <number>,
  "tax": <number>,
  "total": <number>,
  "currency": "USD"
}
Return only valid JSON. No markdown, no explanation."""


def _norm_str(v: Any) -> str:
    return re.sub(r'\s+', ' ', str(v).strip()).lower()


def _norm_num(v: Any) -> float | None:
    try:
        return float(str(v).replace(',', '').replace('$', '').strip())
    except (ValueError, TypeError):
        return None


def _score_strings(got: Any, exp: Any) -> float:
    return 1.0 if _norm_str(got) == _norm_str(exp) else 0.0


def _score_number(got: Any, exp: Any) -> float:
    g, e = _norm_num(got), _norm_num(exp)
    if g is None or e is None:
        return 0.0
    if e == 0:
        return 1.0 if g == 0 else 0.0
    return 1.0 if abs(g - e) / abs(e) <= 0.01 else 0.0


def _score_dict(got: Any, exp: dict) -> float:
    if not isinstance(got, dict):
        return 0.0
    scores = [_score_strings(got.get(k), v) for k, v in exp.items()]
    return sum(scores) / len(scores) if scores else 0.0


def _score_items(got: Any, exp: list) -> float:
    if not isinstance(got, list) or not exp:
        return 0.0
    # Match by index; extra/missing items reduce score proportionally
    n = max(len(got), len(exp))
    total = 0.0
    for i in range(min(len(got), len(exp))):
        g_item, e_item = got[i], exp[i]
        if not isinstance(g_item, dict):
            continue
        field_scores = [
            _score_strings(g_item.get("description"), e_item.get("description")),
            _score_number(g_item.get("quantity"), e_item.get("quantity")),
            _score_number(g_item.get("unit_price"), e_item.get("unit_price")),
            _score_number(g_item.get("amount"), e_item.get("amount")),
        ]
        total += sum(field_scores) / len(field_scores)
    return total / n


def _extract_json(text: str) -> dict | None:
    """Extract first JSON object from model output (handles markdown fences)."""
    # Strip markdown code fences if present
    text = re.sub(r'```(?:json)?\s*', '', text).strip().rstrip('`')
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON object substring
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return None


class InvoiceExtractorTest(GroundTruthCapabilityTest):
    capability_name = "invoice_extractor"

    def evaluate(self, output: str, expected: Any, test_case: TestCase) -> float:
        if not isinstance(expected, dict):
            # Fallback for legacy text expected files
            return 1.0 if output.strip() == str(expected).strip() else 0.0

        got = _extract_json(output)
        if got is None:
            return 0.0

        weighted_score = 0.0
        total_weight = 0.0
        for field, weight in _FIELD_WEIGHTS.items():
            exp_val = expected.get(field)
            got_val = got.get(field)
            if exp_val is None:
                continue  # field absent from ground truth — skip entirely

            total_weight += weight

            if field in ("subtotal", "tax", "total"):
                field_score = _score_number(got_val, exp_val)
            elif field in ("emitter", "recipient"):
                field_score = _score_dict(got_val, exp_val)
            elif field == "items":
                field_score = _score_items(got_val, exp_val)
            else:
                field_score = _score_strings(got_val, exp_val)

            weighted_score += weight * field_score

        if total_weight == 0.0:
            return 0.0
        return round(weighted_score / total_weight, 4)

    def build_prompt(self, test_case: TestCase) -> str:
        if Path(test_case.input_data).suffix.lower() in IMAGE_SUFFIXES:
            return _PROMPT
        return f"{_PROMPT}\n\nInvoice text:\n{test_case.input_data}"

    async def run(self, model: Any, test_case: TestCase) -> str:
        if Path(test_case.input_data).suffix.lower() in IMAGE_SUFFIXES:
            return await model.generate_with_image(
                self.build_prompt(test_case),
                test_case.input_data,
            )
        return await model.generate(self.build_prompt(test_case))
