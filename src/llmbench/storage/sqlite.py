"""
SQLite storage for benchmark results
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from ..cube import BenchmarkResult, sensitivity_to_threshold


class SQLiteStorage:
    """Store benchmark results in SQLite database"""

    def __init__(self, db_path: str = "results/benchmarks.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS benchmark_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    complexity INTEGER NOT NULL,
                    model_name TEXT NOT NULL,
                    score REAL NOT NULL,
                    latency_ms REAL NOT NULL,
                    cost_estimate REAL NOT NULL,
                    error TEXT,
                    raw_output TEXT,
                    expected_output TEXT,
                    metadata TEXT,
                    run_id TEXT,
                    worker_id TEXT
                )
            """)
            # Add expected_output column to existing databases that predate this field
            try:
                conn.execute("ALTER TABLE benchmark_results ADD COLUMN expected_output TEXT")
            except sqlite3.OperationalError:
                pass  # column already exists

            conn.execute("""
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    worker_count INTEGER,
                    total_tasks INTEGER,
                    completed_tasks INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS worker_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_model_capability
                ON benchmark_results(model_name, capability)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_point
                ON benchmark_results(capability, complexity)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_run_id
                ON benchmark_results(run_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_worker_events_run
                ON worker_events(run_id, worker_id)
            """)

    def save_result(self, result: BenchmarkResult):
        """Save a single benchmark result"""
        with sqlite3.connect(self.db_path) as conn:
            run_id = None
            worker_id = None
            if result.metadata:
                run_id = result.metadata.get("run_id")
                worker_id = result.metadata.get("worker_id")

            conn.execute("""
                INSERT INTO benchmark_results
                (timestamp, capability, complexity, model_name,
                 score, latency_ms, cost_estimate, error, raw_output, expected_output,
                 metadata, run_id, worker_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                result.point.capability.value,
                result.point.complexity,
                result.model_name,
                result.score,
                result.latency_ms,
                result.cost_estimate,
                result.error,
                result.raw_output,
                result.expected_output,
                json.dumps(result.metadata) if result.metadata else None,
                run_id,
                worker_id,
            ))

    def save_results(self, results: List[BenchmarkResult]):
        for result in results:
            self.save_result(result)

    def recommend_model(
        self,
        capability: str,
        complexity: int,
        sensitivity: int,
    ) -> Optional[dict]:
        """
        Recommend the best model for a given (capability, complexity, sensitivity) triple.

        Sensitivity is a business-context parameter that maps linearly to a minimum
        score threshold (1→0.60, 2→0.70, 3→0.80, 4→0.90, 5→0.95).

        Returns the model with the highest average score above the threshold,
        with lowest latency as tiebreaker. Returns None if no model qualifies —
        meaning a proprietary model should be used instead.
        """
        min_score = sensitivity_to_threshold(sensitivity)

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
                  AND error IS NULL
                GROUP BY model_name
                HAVING avg_score >= ?
                ORDER BY avg_score DESC, avg_latency ASC
                LIMIT 1
            """, (capability, complexity, min_score))

            row = cursor.fetchone()
            if row is None:
                return None
            return {**dict(row), "min_score_threshold": min_score, "sensitivity": sensitivity}

    def get_all_scores(
        self,
        capability: str,
        complexity: int,
    ) -> List[dict]:
        """
        Return the performance array for a (capability, complexity) point:
        all models with their average score and latency, ordered by score desc.
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
                  AND error IS NULL
                GROUP BY model_name
                ORDER BY avg_score DESC
            """, (capability, complexity))

            return [dict(row) for row in cursor.fetchall()]

    def get_model_summary(self, model_name: str) -> List[dict]:
        """Get performance summary for a model across all capabilities"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT
                    capability,
                    complexity,
                    AVG(score) as avg_score,
                    AVG(latency_ms) as avg_latency,
                    COUNT(*) as test_count,
                    SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
                FROM benchmark_results
                WHERE model_name = ?
                GROUP BY capability, complexity
                ORDER BY capability, complexity
            """, (model_name,))

            return [dict(row) for row in cursor.fetchall()]

    def create_run(self, run_id: str, worker_count: int, total_tasks: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO benchmark_runs
                (run_id, created_at, status, worker_count, total_tasks, completed_tasks)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (run_id, datetime.now().isoformat(), "running", worker_count, total_tasks, 0))

    def update_run_status(self, run_id: str, status: str, completed_tasks: Optional[int] = None):
        with sqlite3.connect(self.db_path) as conn:
            if completed_tasks is not None:
                conn.execute("""
                    UPDATE benchmark_runs
                    SET status = ?, completed_tasks = ?
                    WHERE run_id = ?
                """, (status, completed_tasks, run_id))
            else:
                conn.execute("""
                    UPDATE benchmark_runs SET status = ? WHERE run_id = ?
                """, (status, run_id))

    def get_run_status(self, run_id: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM benchmark_runs WHERE run_id = ?", (run_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def log_worker_event(
        self,
        run_id: str,
        worker_id: str,
        event_type: str,
        metadata: Optional[dict] = None,
    ):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO worker_events
                (run_id, worker_id, event_type, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (
                run_id, worker_id, event_type,
                datetime.now().isoformat(),
                json.dumps(metadata) if metadata else None,
            ))

    def get_worker_stats(self, run_id: str) -> List[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT
                    worker_id,
                    COUNT(*) as tasks_completed,
                    AVG(score) as avg_score,
                    AVG(latency_ms) as avg_latency
                FROM benchmark_results
                WHERE run_id = ? AND worker_id IS NOT NULL
                GROUP BY worker_id
            """, (run_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_results(
        self,
        capability: Optional[str] = None,
        model_name: Optional[str] = None,
        limit: int = 500,
    ) -> List[dict]:
        """Return raw benchmark results with optional filters."""
        conditions = []
        params: list = []

        if capability:
            conditions.append("capability = ?")
            params.append(capability)

        if model_name:
            conditions.append("model_name = ?")
            params.append(model_name)

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f"""
                SELECT
                    id,
                    model_name,
                    capability,
                    complexity,
                    score,
                    latency_ms,
                    cost_estimate,
                    error,
                    raw_output,
                    expected_output,
                    timestamp
                FROM benchmark_results
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
            """, params)
            return [dict(row) for row in cursor.fetchall()]
