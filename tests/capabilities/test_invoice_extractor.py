"""Tests for invoice_extractor capability"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock

from src.llmbench.capabilities.invoice_extractor import (
    InvoiceExtractorTest,
    _score_number,
    _score_dict,
    _score_items,
    _extract_json,
)
from src.llmbench.capabilities.base import GroundTruthCapabilityTest, TestCase


EXPECTED_JSON = {
    "invoice_number": "1223113",
    "date": "2023-12-01",
    "due_date": "2024-01-15",
    "payment_terms": "Net 45",
    "emitter": {"name": "Slack", "address": "500 Howard Street", "city": "San Francisco", "state": "CA", "zip": "94105"},
    "recipient": {"name": "MineralTree", "address": "101 Arch Street", "city": "Boston", "state": "MA", "zip": "02110"},
    "items": [{"description": "Business+ Monthly User License - August 2023", "quantity": 115, "unit_price": 15.0, "amount": 1725.0}],
    "subtotal": 1725.0,
    "tax": 0.0,
    "total": 1725.0,
    "currency": "USD",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def text_ground_truth_dir(tmp_path: Path) -> Path:
    cap_dir = tmp_path / "invoice_extractor"
    case_dir = cap_dir / "example"
    case_dir.mkdir(parents=True)
    (case_dir / "test.txt").write_text("invoice total: 150$")
    (case_dir / "test_expected.json").write_text(json.dumps({
        "invoice_number": "001", "date": "2024-01-01", "due_date": "2024-02-01",
        "payment_terms": "Net 30",
        "emitter": {"name": "ACME", "address": "1 Main St", "city": "NYC", "state": "NY", "zip": "10001"},
        "recipient": {"name": "Client", "address": "2 Side St", "city": "LA", "state": "CA", "zip": "90001"},
        "items": [{"description": "Widget", "quantity": 1, "unit_price": 150.0, "amount": 150.0}],
        "subtotal": 150.0, "tax": 0.0, "total": 150.0, "currency": "USD",
    }))
    manifest = {"capability": "invoice_extractor", "test_cases": [{
        "id": "example", "input_file": "example/test.txt",
        "expected_file": "example/test_expected.json", "complexity": 1,
    }]}
    (cap_dir / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path


@pytest.fixture
def image_ground_truth_dir(tmp_path: Path) -> Path:
    cap_dir = tmp_path / "invoice_extractor"
    case_dir = cap_dir / "item1"
    case_dir.mkdir(parents=True)
    # Minimal 1x1 JPEG
    jpeg_bytes = bytes([
        0xff,0xd8,0xff,0xe0,0x00,0x10,0x4a,0x46,0x49,0x46,0x00,0x01,0x01,0x00,
        0x00,0x01,0x00,0x01,0x00,0x00,0xff,0xdb,0x00,0x43,0x00,0x08,0x06,0x06,
        0x07,0x06,0x05,0x08,0x07,0x07,0x07,0x09,0x09,0x08,0x0a,0x0c,0x14,0x0d,
        0x0c,0x0b,0x0b,0x0c,0x19,0x12,0x13,0x0f,0x14,0x1d,0x1a,0x1f,0x1e,0x1d,
        0x1a,0x1c,0x1c,0x20,0x24,0x2e,0x27,0x20,0x22,0x2c,0x23,0x1c,0x1c,0x28,
        0x37,0x29,0x2c,0x30,0x31,0x34,0x34,0x34,0x1f,0x27,0x39,0x3d,0x38,0x32,
        0x3c,0x2e,0x33,0x34,0x32,0xff,0xc0,0x00,0x0b,0x08,0x00,0x01,0x00,0x01,
        0x01,0x01,0x11,0x00,0xff,0xc4,0x00,0x1f,0x00,0x00,0x01,0x05,0x01,0x01,
        0x01,0x01,0x01,0x01,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x01,0x02,
        0x03,0x04,0x05,0x06,0x07,0x08,0x09,0x0a,0x0b,0xff,0xda,0x00,0x08,0x01,
        0x01,0x00,0x00,0x3f,0x00,0xfb,0xd3,0xff,0xd9,
    ])
    (case_dir / "invoice.jpg").write_bytes(jpeg_bytes)
    (case_dir / "expected.json").write_text(json.dumps(EXPECTED_JSON))
    manifest = {"capability": "invoice_extractor", "test_cases": [{
        "id": "item1", "input_file": "item1/invoice.jpg",
        "expected_file": "item1/expected.json", "complexity": 3,
    }]}
    (cap_dir / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path


@pytest.fixture
def extractor(text_ground_truth_dir: Path) -> InvoiceExtractorTest:
    return InvoiceExtractorTest(data_root=text_ground_truth_dir)


@pytest.fixture
def image_extractor(image_ground_truth_dir: Path) -> InvoiceExtractorTest:
    return InvoiceExtractorTest(data_root=image_ground_truth_dir)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class TestGroundTruthLoader:

    def test_loads_test_cases_from_manifest(self, extractor):
        cases = extractor.get_test_cases()
        assert len(cases) == 1
        assert cases[0].input_data == "invoice total: 150$"
        assert isinstance(cases[0].expected_output, dict)
        assert cases[0].expected_output["total"] == 150.0
        assert cases[0].complexity == 1
        assert cases[0].metadata["test_id"] == "example"

    def test_missing_manifest_raises(self, tmp_path):
        cap = InvoiceExtractorTest(data_root=tmp_path)
        with pytest.raises(FileNotFoundError, match="manifest.json"):
            cap.get_test_cases()

    def test_missing_input_file_raises(self, tmp_path):
        cap_dir = tmp_path / "invoice_extractor"
        cap_dir.mkdir()
        manifest = {"capability": "invoice_extractor", "test_cases": [{
            "id": "bad", "input_file": "missing/test.txt",
            "expected_file": "missing/expected.json", "complexity": 1,
        }]}
        (cap_dir / "manifest.json").write_text(json.dumps(manifest))
        cap = InvoiceExtractorTest(data_root=tmp_path)
        with pytest.raises(FileNotFoundError, match="Input file not found"):
            cap.get_test_cases()

    def test_test_cases_cached(self, extractor):
        assert extractor.get_test_cases() is extractor.get_test_cases()

    def test_image_input_stored_as_path(self, image_extractor):
        cases = image_extractor.get_test_cases()
        assert len(cases) == 1
        assert cases[0].input_data.endswith(".jpg")
        assert Path(cases[0].input_data).exists()

    def test_json_expected_parsed_as_dict(self, image_extractor):
        cases = image_extractor.get_test_cases()
        assert isinstance(cases[0].expected_output, dict)
        assert cases[0].expected_output["total"] == 1725.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestScoringHelpers:

    def test_score_number_exact(self):
        assert _score_number(1725.0, 1725.0) == 1.0

    def test_score_number_within_tolerance(self):
        assert _score_number(1724.99, 1725.0) == 1.0

    def test_score_number_wrong(self):
        assert _score_number(100.0, 1725.0) == 0.0

    def test_score_number_string_input(self):
        assert _score_number("$1,725.00", 1725.0) == 1.0

    def test_score_number_zero(self):
        assert _score_number(0.0, 0.0) == 1.0

    def test_score_dict_exact(self):
        d = {"name": "Slack", "city": "San Francisco", "state": "CA", "zip": "94105", "address": "500 Howard Street"}
        assert _score_dict(d, d) == 1.0

    def test_score_dict_partial(self):
        exp = {"name": "Slack", "city": "San Francisco"}
        got = {"name": "Slack", "city": "Wrong"}
        assert _score_dict(got, exp) == 0.5

    def test_score_items_exact(self):
        items = [{"description": "Widget", "quantity": 1, "unit_price": 10.0, "amount": 10.0}]
        assert _score_items(items, items) == 1.0

    def test_score_items_missing_item(self):
        exp = [{"description": "A", "quantity": 1, "unit_price": 10.0, "amount": 10.0},
               {"description": "B", "quantity": 2, "unit_price": 5.0, "amount": 10.0}]
        got = [{"description": "A", "quantity": 1, "unit_price": 10.0, "amount": 10.0}]
        # 1 correct out of 2 expected
        assert _score_items(got, exp) == 0.5

    def test_extract_json_clean(self):
        assert _extract_json('{"total": 100}') == {"total": 100}

    def test_extract_json_with_markdown_fence(self):
        assert _extract_json('```json\n{"total": 100}\n```') == {"total": 100}

    def test_extract_json_embedded_in_text(self):
        assert _extract_json('Here is the result: {"total": 100} done') == {"total": 100}

    def test_extract_json_invalid(self):
        assert _extract_json("not json at all") is None


# ---------------------------------------------------------------------------
# Evaluate
# ---------------------------------------------------------------------------

class TestInvoiceExtractorEvaluate:

    def test_perfect_output_scores_1(self, image_extractor):
        tc = image_extractor.get_test_cases()[0]
        output = json.dumps(EXPECTED_JSON)
        assert image_extractor.evaluate(output, tc.expected_output, tc) == 1.0

    def test_invalid_json_scores_0(self, image_extractor):
        tc = image_extractor.get_test_cases()[0]
        assert image_extractor.evaluate("not json", tc.expected_output, tc) == 0.0

    def test_wrong_total_reduces_score(self, image_extractor):
        tc = image_extractor.get_test_cases()[0]
        wrong = dict(EXPECTED_JSON, total=999.0)
        score = image_extractor.evaluate(json.dumps(wrong), tc.expected_output, tc)
        assert score < 1.0
        assert score > 0.0

    def test_markdown_fenced_json_accepted(self, image_extractor):
        tc = image_extractor.get_test_cases()[0]
        output = f"```json\n{json.dumps(EXPECTED_JSON)}\n```"
        assert image_extractor.evaluate(output, tc.expected_output, tc) == 1.0

    def test_total_weight_significant(self, image_extractor):
        # Only total correct → score equals total weight (0.10)
        tc = image_extractor.get_test_cases()[0]
        minimal = {"total": 1725.0}
        score = image_extractor.evaluate(json.dumps(minimal), tc.expected_output, tc)
        assert score == pytest.approx(0.10, abs=0.01)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

class TestInvoiceExtractorPrompt:

    def test_text_prompt_contains_invoice_text(self, extractor):
        tc = extractor.get_test_cases()[0]
        prompt = extractor.build_prompt(tc)
        assert "invoice total: 150$" in prompt

    def test_text_prompt_requests_json(self, extractor):
        tc = extractor.get_test_cases()[0]
        prompt = extractor.build_prompt(tc)
        assert "json" in prompt.lower()

    def test_image_prompt_does_not_contain_path(self, image_extractor):
        tc = image_extractor.get_test_cases()[0]
        prompt = image_extractor.build_prompt(tc)
        assert tc.input_data not in prompt
        assert "json" in prompt.lower()


# ---------------------------------------------------------------------------
# run() dispatch
# ---------------------------------------------------------------------------

class TestRunDispatch:

    @pytest.mark.asyncio
    async def test_run_uses_generate_for_text(self, extractor):
        tc = extractor.get_test_cases()[0]
        mock_model = AsyncMock()
        mock_model.generate = AsyncMock(return_value='{"total": 150.0}')
        await extractor.run(mock_model, tc)
        mock_model.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_uses_vision_for_image(self, image_extractor):
        tc = image_extractor.get_test_cases()[0]
        mock_model = AsyncMock()
        mock_model.generate_with_image = AsyncMock(return_value=json.dumps(EXPECTED_JSON))
        await image_extractor.run(mock_model, tc)
        mock_model.generate_with_image.assert_awaited_once()
