"""
SQLite storage for benchmark results
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from ..cube import BenchmarkResult


class SQLiteStorage:
    """Store benchmark results in SQLite database"""

    def __init__(self, db_path: str = "results/benchmarks.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS benchmark_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    complexity INTEGER NOT NULL,
                    sensitivity INTEGER NOT NULL,
                    model_name TEXT NOT NULL,
                    score REAL NOT NULL,
                    latency_ms REAL NOT NULL,
                    cost_estimate REAL NOT NULL,
                    error TEXT,
                    raw_output TEXT,
                    metadata TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_model_capability
                ON benchmark_results(model_name, capability)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_point
                ON benchmark_results(capability, complexity, sensitivity)
            """)

    def save_result(self, result: BenchmarkResult):
        """Save a single benchmark result"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO benchmark_results
                (timestamp, capability, complexity, sensitivity, model_name,
                 score, latency_ms, cost_estimate, error, raw_output, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                result.point.capability.value,
                result.point.complexity,
                result.point.sensitivity,
                result.model_name,
                result.score,
                result.latency_ms,
                result.cost_estimate,
                result.error,
                result.raw_output,
                json.dumps(result.metadata) if result.metadata else None
            ))

    def save_results(self, results: List[BenchmarkResult]):
        """Save multiple benchmark results"""
        for result in results:
            self.save_result(result)

    def get_best_model(
        self,
        capability: str,
        complexity: int,
        sensitivity: int,
        min_score: float = 0.8
    ) -> Optional[dict]:
        """
        Get the best model for a specific point in the cube.
        Returns the model with highest score above min_score threshold,
        with lowest cost as tiebreaker.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT
                    model_name,
                    AVG(score) as avg_score,
                    AVG(latency_ms) as avg_latency,
                    AVG(cost_estimate) as avg_cost,
                    COUNT(*) as sample_count
                FROM benchmark_results
                WHERE capability = ?
                  AND complexity = ?
                  AND sensitivity = ?
                  AND error IS NULL
                GROUP BY model_name
                HAVING avg_score >= ?
                ORDER BY avg_score DESC, avg_cost ASC
                LIMIT 1
            """, (capability, complexity, sensitivity, min_score))

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_model_summary(self, model_name: str) -> dict:
        """Get performance summary for a model across all capabilities"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT
                    capability,
                    AVG(score) as avg_score,
                    AVG(latency_ms) as avg_latency,
                    COUNT(*) as test_count,
                    SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM benchmark_results
                WHERE model_name = ?
                GROUP BY capability
            """, (model_name,))

            return [dict(row) for row in cursor.fetchall()]
