"""Tests for invoice_extractor capability"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock

from src.llmbench.capabilities.invoice_extractor import InvoiceExtractorTest
from src.llmbench.capabilities.base import GroundTruthCapabilityTest, TestCase


@pytest.fixture
def text_ground_truth_dir(tmp_path: Path) -> Path:
    """Minimal data/ tree with a text-based test case."""
    cap_dir = tmp_path / "invoice_extractor"
    case_dir = cap_dir / "example"
    case_dir.mkdir(parents=True)

    (case_dir / "test.txt").write_text("invoice total: 150$")
    (case_dir / "test_expected.txt").write_text("150$")

    manifest = {
        "capability": "invoice_extractor",
        "test_cases": [
            {
                "id": "example",
                "input_file": "example/test.txt",
                "expected_file": "example/test_expected.txt",
                "complexity": 1,
                "metadata": {"description": "Simple total extraction"},
            }
        ],
    }
    (cap_dir / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path


@pytest.fixture
def image_ground_truth_dir(tmp_path: Path) -> Path:
    """Minimal data/ tree with a JPEG test case (1x1 pixel JPEG)."""
    cap_dir = tmp_path / "invoice_extractor"
    case_dir = cap_dir / "item1"
    case_dir.mkdir(parents=True)

    # Minimal valid JPEG bytes (1x1 white pixel)
    jpeg_bytes = bytes([
        0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xff, 0xdb, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0a, 0x0c, 0x14, 0x0d, 0x0c, 0x0b, 0x0b, 0x0c, 0x19, 0x12,
        0x13, 0x0f, 0x14, 0x1d, 0x1a, 0x1f, 0x1e, 0x1d, 0x1a, 0x1c, 0x1c, 0x20,
        0x24, 0x2e, 0x27, 0x20, 0x22, 0x2c, 0x23, 0x1c, 0x1c, 0x28, 0x37, 0x29,
        0x2c, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1f, 0x27, 0x39, 0x3d, 0x38, 0x32,
        0x3c, 0x2e, 0x33, 0x34, 0x32, 0xff, 0xc0, 0x00, 0x0b, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xff, 0xc4, 0x00, 0x1f, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0a, 0x0b, 0xff, 0xc4, 0x00, 0xb5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7d,
        0xff, 0xda, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3f, 0x00, 0xfb, 0xd3,
        0xff, 0xd9,
    ])
    (case_dir / "invoice.jpg").write_bytes(jpeg_bytes)
    (case_dir / "expected.txt").write_text("$1,725.00")

    manifest = {
        "capability": "invoice_extractor",
        "test_cases": [
            {
                "id": "item1",
                "input_file": "item1/invoice.jpg",
                "expected_file": "item1/expected.txt",
                "complexity": 3,
            }
        ],
    }
    (cap_dir / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path


@pytest.fixture
def extractor(text_ground_truth_dir: Path) -> InvoiceExtractorTest:
    return InvoiceExtractorTest(data_root=text_ground_truth_dir)


class TestGroundTruthLoader:

    def test_loads_test_cases_from_manifest(self, extractor):
        cases = extractor.get_test_cases()
        assert len(cases) == 1
        assert cases[0].input_data == "invoice total: 150$"
        assert cases[0].expected_output == "150$"
        assert cases[0].complexity == 1
        assert cases[0].metadata["test_id"] == "example"

    def test_missing_manifest_raises(self, tmp_path):
        cap = InvoiceExtractorTest(data_root=tmp_path)
        with pytest.raises(FileNotFoundError, match="manifest.json"):
            cap.get_test_cases()

    def test_missing_input_file_raises(self, tmp_path):
        cap_dir = tmp_path / "invoice_extractor"
        cap_dir.mkdir()
        manifest = {
            "capability": "invoice_extractor",
            "test_cases": [
                {
                    "id": "bad",
                    "input_file": "missing/test.txt",
                    "expected_file": "missing/test_expected.txt",
                    "complexity": 1,
                }
            ],
        }
        (cap_dir / "manifest.json").write_text(json.dumps(manifest))
        cap = InvoiceExtractorTest(data_root=tmp_path)
        with pytest.raises(FileNotFoundError, match="Input file not found"):
            cap.get_test_cases()

    def test_test_cases_cached(self, extractor):
        cases1 = extractor.get_test_cases()
        cases2 = extractor.get_test_cases()
        assert cases1 is cases2

    def test_multiple_test_cases(self, tmp_path):
        cap_dir = tmp_path / "invoice_extractor"
        for i in range(3):
            d = cap_dir / f"case{i}"
            d.mkdir(parents=True)
            (d / "test.txt").write_text(f"total: {i*10}$")
            (d / "test_expected.txt").write_text(f"{i*10}$")

        manifest = {
            "capability": "invoice_extractor",
            "test_cases": [
                {
                    "id": f"case{i}",
                    "input_file": f"case{i}/test.txt",
                    "expected_file": f"case{i}/test_expected.txt",
                    "complexity": i + 1,
                }
                for i in range(3)
            ],
        }
        (cap_dir / "manifest.json").write_text(json.dumps(manifest))
        cap = InvoiceExtractorTest(data_root=tmp_path)
        cases = cap.get_test_cases()
        assert len(cases) == 3
        assert [c.complexity for c in cases] == [1, 2, 3]

    def test_image_input_stored_as_path(self, image_ground_truth_dir):
        cap = InvoiceExtractorTest(data_root=image_ground_truth_dir)
        cases = cap.get_test_cases()
        assert len(cases) == 1
        assert cases[0].input_data.endswith(".jpg")
        assert Path(cases[0].input_data).exists()


class TestInvoiceExtractorEvaluate:

    def test_exact_match_scores_1(self, extractor):
        tc = TestCase("invoice total: 150$", "150$", complexity=1)
        assert extractor.evaluate("150$", "150$", tc) == 1.0

    def test_wrong_output_scores_0(self, extractor):
        tc = TestCase("invoice total: 150$", "150$", complexity=1)
        assert extractor.evaluate("200$", "150$", tc) == 0.0

    def test_whitespace_stripped(self, extractor):
        tc = TestCase("invoice total: 150$", "150$", complexity=1)
        assert extractor.evaluate("  150$  ", "  150$  ", tc) == 1.0

    def test_wrong_amount_in_sentence_scores_0(self, extractor):
        tc = TestCase("invoice total: 150$", "150$", complexity=1)
        assert extractor.evaluate("The total is 200$", "150$", tc) == 0.0

    def test_correct_amount_in_sentence_scores_1(self, extractor):
        # Fuzzy match: amount found in output even if not standalone
        tc = TestCase("invoice total: 150$", "150$", complexity=1)
        assert extractor.evaluate("The total is 150$", "150$", tc) == 1.0

    def test_fuzzy_amount_match(self, extractor):
        # Same numeric value, different formatting
        tc = TestCase("", "$1,725.00", complexity=3)
        assert extractor.evaluate("$1725.00", "$1,725.00", tc) == 1.0

    def test_amount_embedded_in_output_matches(self, extractor):
        # Model returns amount as part of a sentence → should still match
        tc = TestCase("", "$1,725.00", complexity=3)
        assert extractor.evaluate("Balance Due: $1,725.00", "$1,725.00", tc) == 1.0


class TestInvoiceExtractorPrompt:

    def test_prompt_contains_input_for_text(self, extractor):
        tc = TestCase("invoice total: 150$", "150$", complexity=1)
        prompt = extractor.build_prompt(tc)
        assert "invoice total: 150$" in prompt

    def test_prompt_instructs_amount_only(self, extractor):
        tc = TestCase("invoice total: 150$", "150$", complexity=1)
        prompt = extractor.build_prompt(tc)
        assert "amount only" in prompt.lower()

    def test_image_prompt_does_not_contain_path(self, image_ground_truth_dir):
        cap = InvoiceExtractorTest(data_root=image_ground_truth_dir)
        cases = cap.get_test_cases()
        prompt = cap.build_prompt(cases[0])
        # Path should not leak into prompt — model receives image via API
        assert cases[0].input_data not in prompt
        assert "image" in prompt.lower() or "invoice" in prompt.lower()

    def test_real_text_test_case_prompt(self, extractor):
        cases = extractor.get_test_cases()
        prompt = extractor.build_prompt(cases[0])
        assert "invoice total: 150$" in prompt


class TestInvoiceExtractorRunMethod:

    @pytest.mark.asyncio
    async def test_run_uses_generate_for_text(self, extractor):
        tc = TestCase("invoice total: 150$", "150$", complexity=1)
        mock_model = AsyncMock()
        mock_model.generate = AsyncMock(return_value="150$")
        result = await extractor.run(mock_model, tc)
        mock_model.generate.assert_awaited_once()
        mock_model.generate_with_image.assert_not_called()
        assert result == "150$"

    @pytest.mark.asyncio
    async def test_run_uses_vision_for_image(self, image_ground_truth_dir):
        cap = InvoiceExtractorTest(data_root=image_ground_truth_dir)
        tc = cap.get_test_cases()[0]
        mock_model = AsyncMock()
        mock_model.generate_with_image = AsyncMock(return_value="$1,725.00")
        result = await cap.run(mock_model, tc)
        mock_model.generate_with_image.assert_awaited_once()
        assert result == "$1,725.00"
