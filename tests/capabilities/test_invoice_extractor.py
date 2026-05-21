"""Tests for invoice_extractor capability"""

import json
import pytest
import tempfile
from pathlib import Path

from src.llmbench.capabilities.invoice_extractor import InvoiceExtractorTest
from src.llmbench.capabilities.base import GroundTruthCapabilityTest, TestCase


@pytest.fixture
def ground_truth_dir(tmp_path: Path) -> Path:
    """Build a minimal data/ tree in a temp dir."""
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
def extractor(ground_truth_dir: Path) -> InvoiceExtractorTest:
    return InvoiceExtractorTest(data_root=ground_truth_dir)


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
        assert cases1 is cases2  # same list object — not reloaded

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

    def test_partial_match_scores_0(self, extractor):
        tc = TestCase("invoice total: 150$", "150$", complexity=1)
        assert extractor.evaluate("The total is 150$", "150$", tc) == 0.0


class TestInvoiceExtractorPrompt:

    def test_prompt_contains_input(self, extractor):
        tc = TestCase("invoice total: 150$", "150$", complexity=1)
        prompt = extractor.build_prompt(tc)
        assert "invoice total: 150$" in prompt

    def test_prompt_instructs_amount_only(self, extractor):
        tc = TestCase("invoice total: 150$", "150$", complexity=1)
        prompt = extractor.build_prompt(tc)
        assert "amount only" in prompt.lower() or "only" in prompt.lower()

    def test_real_test_case_prompt(self, extractor):
        cases = extractor.get_test_cases()
        prompt = extractor.build_prompt(cases[0])
        assert "invoice total: 150$" in prompt
