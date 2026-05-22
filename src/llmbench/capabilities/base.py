"""
Base capability test interface
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
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


class GroundTruthCapabilityTest(CapabilityTest):
    """
    Capability test that loads test cases from a manifest file + ground truth files.

    Directory layout:
        data/<capability_name>/
            manifest.json
            <test_id>/
                test.txt           (input sent to the model)
                test_expected.txt  (expected output for scoring)

    manifest.json schema:
        {
          "capability": "<name>",
          "test_cases": [
            {
              "id": "<unique_id>",
              "input_file": "<relative_path_to_test.txt>",
              "expected_file": "<relative_path_to_test_expected.txt>",
              "complexity": <1-5>,
              "metadata": { ... }   // optional
            }
          ]
        }
    """

    # Subclasses must set this to the capability name (= data/ subfolder name)
    capability_name: str = ""

    def __init__(self, data_root: Optional[Path] = None):
        if data_root is None:
            # Default: <repo_root>/data
            data_root = Path(__file__).parent.parent.parent.parent / "data"
        self._data_root = data_root
        self._test_cases: Optional[List[TestCase]] = None

    def get_test_cases(self) -> List[TestCase]:
        if self._test_cases is None:
            self._test_cases = self._load_from_manifest()
        return self._test_cases

    def _load_from_manifest(self) -> List[TestCase]:
        capability_dir = self._data_root / self.capability_name
        manifest_path = capability_dir / "manifest.json"

        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Manifest not found: {manifest_path}\n"
                f"Expected layout: data/{self.capability_name}/manifest.json"
            )

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        test_cases = []

        IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

        for entry in manifest["test_cases"]:
            input_path = capability_dir / entry["input_file"]
            expected_path = capability_dir / entry["expected_file"]

            if not input_path.exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")
            if not expected_path.exists():
                raise FileNotFoundError(f"Expected file not found: {expected_path}")

            metadata = entry.get("metadata") or {}
            metadata["test_id"] = entry["id"]

            # For image inputs, store the absolute path as a string so capabilities
            # can load the raw bytes themselves (e.g. for vision API calls).
            if input_path.suffix.lower() in IMAGE_SUFFIXES:
                input_data = str(input_path.resolve())
            else:
                input_data = input_path.read_text(encoding="utf-8").strip()

            # JSON expected files are parsed to dict; text files kept as string
            raw_expected = expected_path.read_text(encoding="utf-8").strip()
            if expected_path.suffix.lower() == ".json":
                expected_output = json.loads(raw_expected)
            else:
                expected_output = raw_expected

            test_cases.append(TestCase(
                input_data=input_data,
                expected_output=expected_output,
                complexity=entry["complexity"],
                metadata=metadata,
            ))

        return test_cases
