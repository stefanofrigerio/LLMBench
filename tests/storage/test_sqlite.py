"""Tests for SQLite storage"""

import pytest
import tempfile
from pathlib import Path

from src.llmbench.storage.sqlite import SQLiteStorage
from src.llmbench.cube import BenchmarkResult, BenchmarkPoint, Capability


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def storage(temp_db):
    return SQLiteStorage(temp_db)


@pytest.fixture
def sample_result():
    point = BenchmarkPoint(capability=Capability.CODE_GENERATION, complexity=3)
    return BenchmarkResult(
        point=point,
        model_name="test-model",
        score=0.85,
        latency_ms=1500.0,
        cost_estimate=0.01,
        raw_output="test output",
    )


class TestSQLiteStorage:

    def test_init_creates_database(self, temp_db):
        storage = SQLiteStorage(temp_db)
        assert Path(temp_db).exists()
        result = BenchmarkResult(
            point=BenchmarkPoint(Capability.CODE_GENERATION, 1),
            model_name="test",
            score=1.0,
            latency_ms=100.0,
            cost_estimate=0.0,
        )
        storage.save_result(result)  # should not raise

    def test_save_single_result(self, storage, sample_result):
        storage.save_result(sample_result)

        import sqlite3
        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM benchmark_results")
            assert cursor.fetchone()[0] == 1

            cursor = conn.execute("SELECT model_name, score FROM benchmark_results")
            row = cursor.fetchone()
            assert row[0] == "test-model"
            assert row[1] == 0.85

    def test_save_multiple_results(self, storage):
        results = [
            BenchmarkResult(
                point=BenchmarkPoint(Capability.CODE_GENERATION, i + 1),
                model_name=f"model-{i}",
                score=0.5 + i * 0.1,
                latency_ms=1000.0 + i * 100,
                cost_estimate=0.01 * i,
            )
            for i in range(5)
        ]
        storage.save_results(results)

        import sqlite3
        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM benchmark_results")
            assert cursor.fetchone()[0] == 5

    def test_save_result_with_metadata(self, storage):
        result = BenchmarkResult(
            point=BenchmarkPoint(Capability.CODE_GENERATION, 3),
            model_name="test-model",
            score=0.85,
            latency_ms=1500.0,
            cost_estimate=0.01,
            metadata={"run_id": "run-123", "worker_id": "worker-1"},
        )
        storage.save_result(result)

        import sqlite3
        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.execute("SELECT run_id, worker_id FROM benchmark_results")
            row = cursor.fetchone()
            assert row[0] == "run-123"
            assert row[1] == "worker-1"

    # --- recommend_model tests ---

    def test_recommend_model_returns_best(self, storage):
        """Returns model with highest score above threshold for the given sensitivity"""
        for model_name, score in [("model-low", 0.75), ("model-high", 0.95), ("model-mid", 0.85)]:
            storage.save_result(BenchmarkResult(
                point=BenchmarkPoint(Capability.CODE_GENERATION, 3),
                model_name=model_name,
                score=score,
                latency_ms=1000.0,
                cost_estimate=0.01,
            ))

        # sensitivity=3 → threshold=0.80; model-low (0.75) excluded
        rec = storage.recommend_model("code_generation", complexity=3, sensitivity=3)
        assert rec is not None
        assert rec["model_name"] == "model-high"
        assert rec["sensitivity"] == 3
        assert rec["min_score_threshold"] == 0.80

    def test_recommend_model_returns_none_when_none_qualifies(self, storage, sample_result):
        sample_result.score = 0.5
        storage.save_result(sample_result)

        # sensitivity=5 → threshold=0.95; nothing qualifies
        rec = storage.recommend_model("code_generation", complexity=3, sensitivity=5)
        assert rec is None

    def test_recommend_model_sensitivity_thresholds(self, storage):
        """Each sensitivity level maps to the correct threshold"""
        for s, expected_threshold in [(1, 0.60), (2, 0.70), (3, 0.80), (4, 0.90), (5, 0.95)]:
            # Store a model that barely passes the threshold
            storage.save_result(BenchmarkResult(
                point=BenchmarkPoint(Capability.CODE_GENERATION, s),
                model_name=f"model-s{s}",
                score=expected_threshold,
                latency_ms=1000.0,
                cost_estimate=0.01,
            ))
            rec = storage.recommend_model("code_generation", complexity=s, sensitivity=s)
            assert rec is not None, f"Expected recommendation for sensitivity={s}"
            assert rec["min_score_threshold"] == expected_threshold

    def test_recommend_model_latency_tiebreaker(self, storage):
        """Latency is tiebreaker when scores are equal"""
        for model_name, latency in [("fast-model", 500.0), ("slow-model", 2000.0)]:
            storage.save_result(BenchmarkResult(
                point=BenchmarkPoint(Capability.CODE_GENERATION, 3),
                model_name=model_name,
                score=0.90,
                latency_ms=latency,
                cost_estimate=0.01,
            ))

        rec = storage.recommend_model("code_generation", complexity=3, sensitivity=4)
        assert rec is not None
        assert rec["model_name"] == "fast-model"

    def test_recommend_model_ignores_errors(self, storage):
        """Results with errors are excluded from recommendation"""
        storage.save_result(BenchmarkResult(
            point=BenchmarkPoint(Capability.CODE_GENERATION, 3),
            model_name="good-model",
            score=0.90,
            latency_ms=1000.0,
            cost_estimate=0.01,
        ))
        storage.save_result(BenchmarkResult(
            point=BenchmarkPoint(Capability.CODE_GENERATION, 3),
            model_name="error-model",
            score=0.99,
            latency_ms=500.0,
            cost_estimate=0.01,
            error="crashed",
        ))

        rec = storage.recommend_model("code_generation", complexity=3, sensitivity=3)
        assert rec is not None
        assert rec["model_name"] == "good-model"

    # --- get_all_scores tests ---

    def test_get_all_scores_returns_sorted_array(self, storage):
        """Returns all models sorted by score desc for a benchmark point"""
        for model_name, score in [("model-a", 0.70), ("model-b", 0.90), ("model-c", 0.80)]:
            storage.save_result(BenchmarkResult(
                point=BenchmarkPoint(Capability.CODE_GENERATION, 3),
                model_name=model_name,
                score=score,
                latency_ms=1000.0,
                cost_estimate=0.01,
            ))

        scores = storage.get_all_scores("code_generation", complexity=3)
        assert len(scores) == 3
        assert scores[0]["model_name"] == "model-b"
        assert scores[1]["model_name"] == "model-c"
        assert scores[2]["model_name"] == "model-a"

    def test_get_all_scores_empty(self, storage):
        scores = storage.get_all_scores("code_generation", complexity=3)
        assert scores == []

    # --- get_model_summary tests ---

    def test_get_model_summary(self, storage):
        capabilities = [Capability.CODE_GENERATION, Capability.TEXT_SUMMARIZATION]
        for cap in capabilities:
            for i in range(3):
                storage.save_result(BenchmarkResult(
                    point=BenchmarkPoint(cap, i + 1),
                    model_name="test-model",
                    score=0.8 + i * 0.05,
                    latency_ms=1000.0 + i * 100,
                    cost_estimate=0.01,
                ))

        summary = storage.get_model_summary("test-model")
        assert len(summary) == 6  # 2 capabilities × 3 complexity levels
        assert any(row["capability"] == "code_generation" for row in summary)
        assert any(row["capability"] == "text_summarization" for row in summary)

    def test_get_model_summary_includes_errors(self, storage):
        point = BenchmarkPoint(Capability.CODE_GENERATION, 3)
        storage.save_result(BenchmarkResult(point, "test-model", 0.9, 1000.0, 0.01))
        storage.save_result(BenchmarkResult(point, "test-model", 0.0, 1000.0, 0.01, error="Error"))

        summary = storage.get_model_summary("test-model")
        assert len(summary) == 1
        assert summary[0]["test_count"] == 2
        assert summary[0]["error_count"] == 1

    # --- run tracking tests ---

    def test_create_run(self, storage):
        storage.create_run(run_id="run-123", worker_count=3, total_tasks=100)

        import sqlite3
        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.execute("SELECT * FROM benchmark_runs WHERE run_id = ?", ("run-123",))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "run-123"
            assert row[2] == "running"
            assert row[3] == 3
            assert row[4] == 100

    def test_update_run_status(self, storage):
        storage.create_run("run-123", 3, 100)
        storage.update_run_status("run-123", "completed", completed_tasks=100)

        import sqlite3
        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.execute(
                "SELECT status, completed_tasks FROM benchmark_runs WHERE run_id = ?", ("run-123",)
            )
            row = cursor.fetchone()
            assert row[0] == "completed"
            assert row[1] == 100

    def test_get_run_status(self, storage):
        storage.create_run("run-123", 3, 100)
        status = storage.get_run_status("run-123")
        assert status is not None
        assert status["run_id"] == "run-123"
        assert status["status"] == "running"
        assert status["worker_count"] == 3

    def test_get_run_status_nonexistent(self, storage):
        assert storage.get_run_status("nonexistent") is None

    def test_log_worker_event(self, storage):
        storage.log_worker_event(
            run_id="run-123",
            worker_id="worker-1",
            event_type="registered",
            metadata={"ip": "192.168.1.100"},
        )

        import sqlite3
        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.execute("SELECT run_id, worker_id, event_type FROM worker_events")
            row = cursor.fetchone()
            assert row[0] == "run-123"
            assert row[1] == "worker-1"
            assert row[2] == "registered"

    def test_get_worker_stats(self, storage):
        for worker_id in ["worker-1", "worker-2"]:
            for i in range(3):
                storage.save_result(BenchmarkResult(
                    point=BenchmarkPoint(Capability.CODE_GENERATION, i + 1),
                    model_name="test-model",
                    score=0.8 + i * 0.05,
                    latency_ms=1000.0 + i * 100,
                    cost_estimate=0.01,
                    metadata={"run_id": "run-123", "worker_id": worker_id},
                ))

        stats = storage.get_worker_stats("run-123")
        assert len(stats) == 2
        worker_ids = {stat["worker_id"] for stat in stats}
        assert worker_ids == {"worker-1", "worker-2"}
        for stat in stats:
            assert stat["tasks_completed"] == 3
