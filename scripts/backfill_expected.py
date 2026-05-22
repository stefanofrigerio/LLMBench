#!/usr/bin/env python3
"""
Backfill expected_output for rows where it is NULL.
Run this once after upgrading from a DB that predates the expected_output column.

Usage:
    poetry run python scripts/backfill_expected.py
    poetry run python scripts/backfill_expected.py results/benchmarks.db
"""

import json
import sqlite3
import sys
from pathlib import Path

# Allow running from any directory
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from llmbench.capabilities import REGISTRY
from llmbench.cube import Capability

db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else repo_root / "results" / "benchmarks.db"

if not db_path.exists():
    print(f"DB not found: {db_path}")
    sys.exit(0)

updated_total = 0

with sqlite3.connect(db_path) as conn:
    for capability, test_class in REGISTRY.items():
        cap_test = test_class()
        try:
            cases = cap_test.get_test_cases()
        except FileNotFoundError as e:
            print(f"  skip {capability.value}: {e}")
            continue

        for tc in cases:
            expected_str = (
                json.dumps(tc.expected_output, ensure_ascii=False)
                if isinstance(tc.expected_output, (dict, list))
                else str(tc.expected_output)
            )
            result = conn.execute(
                "UPDATE benchmark_results SET expected_output = ? "
                "WHERE capability = ? AND expected_output IS NULL",
                (expected_str, capability.value),
            )
            if result.rowcount:
                print(f"  {capability.value}: updated {result.rowcount} rows")
                updated_total += result.rowcount

print(f"\nDone. {updated_total} rows updated in {db_path}")
