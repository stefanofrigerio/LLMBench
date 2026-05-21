"""Tests for SQLite storage"""

import pytest
import tempfile
from pathlib import Path

from src.llmbench.storage.sqlite import SQLiteStorage
from src.llmbench.cube import BenchmarkResult, BenchmarkPoint, Capability


@pytest.fixture
def temp_db():
    """Fixture for temporary database"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def storage(temp_db):
    """Fixture for SQLite storage"""
    return SQLiteStorage(temp_db)


@pytest.fixture
def sample_result():
    """Fixture for sample benchmark result"""
    point = BenchmarkPoint(
        capability=Capability.CODE_GENERATION,
        complexity=3,
        sensitivity=4,
    )
    return BenchmarkResult(
        point=point,
        model_name="test-model",
        score=0.85,
        latency_ms=1500.0,
        cost_estimate=0.01,
        raw_output="test output",
    )


class TestSQLiteStorage:
    """Tests for SQLiteStorage class"""

    def test_init_creates_database(self, temp_db):
        """Test database initialization creates tables"""
        storage = SQLiteStorage(temp_db)

        # Database file should exist
        assert Path(temp_db).exists()

        # Tables should be created (verify by inserting)
        result = BenchmarkResult(
            point=BenchmarkPoint(Capability.CODE_GENERATION, 1, 1),
            model_name="test",
            score=1.0,
            latency_ms=100.0,
            cost_estimate=0.0,
        )
        storage.save_result(result)  # Should not raise

    def test_save_single_result(self, storage, sample_result):
        """Test saving a single result"""
        storage.save_result(sample_result)

        # Verify it was saved
        import sqlite3

        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM benchmark_results")
            count = cursor.fetchone()[0]
            assert count == 1

            cursor = conn.execute("SELECT * FROM benchmark_results")
            row = cursor.fetchone()
            assert row[5] == "test-model"  # model_name
            assert row[6] == 0.85  # score

    def test_save_multiple_results(self, storage):
        """Test saving multiple results"""
        results = []
        for i in range(5):
            point = BenchmarkPoint(Capability.CODE_GENERATION, i + 1, i + 1)
            result = BenchmarkResult(
                point=point,
                model_name=f"model-{i}",
                score=0.5 + i * 0.1,
                latency_ms=1000.0 + i * 100,
                cost_estimate=0.01 * i,
            )
            results.append(result)

        storage.save_results(results)

        import sqlite3

        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM benchmark_results")
            count = cursor.fetchone()[0]
            assert count == 5

    def test_save_result_with_metadata(self, storage):
        """Test saving result with metadata"""
        point = BenchmarkPoint(Capability.CODE_GENERATION, 3, 4)
        result = BenchmarkResult(
            point=point,
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

    def test_get_best_model_single_model(self, storage):
        """Test getting best model with single model"""
        for i in range(3):
            point = BenchmarkPoint(Capability.CODE_GENERATION, 3, 4)
            result = BenchmarkResult(
                point=point,
                model_name="test-model",
                score=0.8 + i * 0.05,
                latency_ms=1500.0,
                cost_estimate=0.01,
            )
            storage.save_result(result)

        best = storage.get_best_model(
            capability="code_generation",
            complexity=3,
            sensitivity=4,
            min_score=0.8,
        )

        assert best is not None
        assert best["model_name"] == "test-model"
        assert best["avg_score"] >= 0.85
        assert best["sample_count"] == 3

    def test_get_best_model_multiple_models(self, storage):
        """Test getting best model chooses highest score"""
        models = [
            ("model-low", 0.75),
            ("model-high", 0.95),
            ("model-medium", 0.85),
        ]

        for model_name, score in models:
            point = BenchmarkPoint(Capability.CODE_GENERATION, 3, 4)
            result = BenchmarkResult(
                point=point,
                model_name=model_name,
                score=score,
                latency_ms=1500.0,
                cost_estimate=0.01,
            )
            storage.save_result(result)

        best = storage.get_best_model(
            capability="code_generation",
            complexity=3,
            sensitivity=4,
            min_score=0.8,
        )

        assert best is not None
        assert best["model_name"] == "model-high"
        assert best["avg_score"] == 0.95

    def test_get_best_model_below_threshold(self, storage, sample_result):
        """Test get_best_model returns None if below threshold"""
        sample_result.score = 0.5  # Low score
        storage.save_result(sample_result)

        best = storage.get_best_model(
            capability="code_generation",
            complexity=3,
            sensitivity=4,
            min_score=0.8,  # Higher threshold
        )

        assert best is None

    def test_get_best_model_cost_tiebreaker(self, storage):
        """Test cost is used as tiebreaker for equal scores"""
        models = [
            ("model-expensive", 0.9, 0.1),
            ("model-cheap", 0.9, 0.01),
        ]

        for model_name, score, cost in models:
            point = BenchmarkPoint(Capability.CODE_GENERATION, 3, 4)
            result = BenchmarkResult(
                point=point,
                model_name=model_name,
                score=score,
                latency_ms=1500.0,
                cost_estimate=cost,
            )
            storage.save_result(result)

        best = storage.get_best_model(
            capability="code_generation",
            complexity=3,
            sensitivity=4,
            min_score=0.8,
        )

        assert best is not None
        assert best["model_name"] == "model-cheap"

    def test_get_best_model_ignores_errors(self, storage):
        """Test get_best_model ignores results with errors"""
        # Good result
        point = BenchmarkPoint(Capability.CODE_GENERATION, 3, 4)
        good_result = BenchmarkResult(
            point=point,
            model_name="good-model",
            score=0.9,
            latency_ms=1500.0,
            cost_estimate=0.01,
        )
        storage.save_result(good_result)

        # Error result
        error_result = BenchmarkResult(
            point=point,
            model_name="error-model",
            score=0.95,  # Higher score but has error
            latency_ms=1500.0,
            cost_estimate=0.01,
            error="Test error",
        )
        storage.save_result(error_result)

        best = storage.get_best_model(
            capability="code_generation",
            complexity=3,
            sensitivity=4,
            min_score=0.8,
        )

        assert best is not None
        assert best["model_name"] == "good-model"  # Error model ignored

    def test_get_model_summary(self, storage):
        """Test getting model summary"""
        # Add results for different capabilities
        capabilities = [
            Capability.CODE_GENERATION,
            Capability.TEXT_SUMMARIZATION,
        ]

        for cap in capabilities:
            for i in range(3):
                point = BenchmarkPoint(cap, i + 1, i + 1)
                result = BenchmarkResult(
                    point=point,
                    model_name="test-model",
                    score=0.8 + i * 0.05,
                    latency_ms=1000.0 + i * 100,
                    cost_estimate=0.01,
                )
                storage.save_result(result)

        summary = storage.get_model_summary("test-model")

        assert len(summary) == 2  # Two capabilities
        assert any(row["capability"] == "code_generation" for row in summary)
        assert any(row["capability"] == "text_summarization" for row in summary)

        # Check aggregation
        code_gen = next(r for r in summary if r["capability"] == "code_generation")
        assert code_gen["test_count"] == 3
        assert code_gen["avg_score"] > 0.8

    def test_get_model_summary_includes_errors(self, storage):
        """Test model summary includes error count"""
        point = BenchmarkPoint(Capability.CODE_GENERATION, 3, 4)

        # Add success
        storage.save_result(
            BenchmarkResult(point, "test-model", 0.9, 1000.0, 0.01)
        )

        # Add error
        storage.save_result(
            BenchmarkResult(point, "test-model", 0.0, 1000.0, 0.01, error="Error")
        )

        summary = storage.get_model_summary("test-model")

        assert len(summary) == 1
        assert summary[0]["test_count"] == 2
        assert summary[0]["error_count"] == 1

    def test_create_run(self, storage):
        """Test creating a benchmark run"""
        storage.create_run(
            run_id="run-123",
            worker_count=3,
            total_tasks=100,
        )

        import sqlite3

        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.execute("SELECT * FROM benchmark_runs WHERE run_id = ?", ("run-123",))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "run-123"  # run_id
            assert row[2] == "running"  # status
            assert row[3] == 3  # worker_count
            assert row[4] == 100  # total_tasks

    def test_update_run_status(self, storage):
        """Test updating run status"""
        storage.create_run("run-123", 3, 100)
        storage.update_run_status("run-123", "completed", completed_tasks=100)

        import sqlite3

        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.execute("SELECT status, completed_tasks FROM benchmark_runs WHERE run_id = ?", ("run-123",))
            row = cursor.fetchone()
            assert row[0] == "completed"
            assert row[1] == 100

    def test_get_run_status(self, storage):
        """Test getting run status"""
        storage.create_run("run-123", 3, 100)

        status = storage.get_run_status("run-123")

        assert status is not None
        assert status["run_id"] == "run-123"
        assert status["status"] == "running"
        assert status["worker_count"] == 3

    def test_get_run_status_nonexistent(self, storage):
        """Test get_run_status returns None for non-existent run"""
        status = storage.get_run_status("nonexistent")
        assert status is None

    def test_log_worker_event(self, storage):
        """Test logging worker event"""
        storage.log_worker_event(
            run_id="run-123",
            worker_id="worker-1",
            event_type="registered",
            metadata={"ip": "192.168.1.100"},
        )

        import sqlite3

        with sqlite3.connect(storage.db_path) as conn:
            cursor = conn.execute("SELECT * FROM worker_events")
            row = cursor.fetchone()
            assert row is not None
            assert row[1] == "run-123"  # run_id
            assert row[2] == "worker-1"  # worker_id
            assert row[3] == "registered"  # event_type

    def test_get_worker_stats(self, storage):
        """Test getting per-worker statistics"""
        # Add results from different workers
        for worker_id in ["worker-1", "worker-2"]:
            for i in range(3):
                point = BenchmarkPoint(Capability.CODE_GENERATION, i + 1, i + 1)
                result = BenchmarkResult(
                    point=point,
                    model_name="test-model",
                    score=0.8 + i * 0.05,
                    latency_ms=1000.0 + i * 100,
                    cost_estimate=0.01,
                    metadata={"run_id": "run-123", "worker_id": worker_id},
                )
                storage.save_result(result)

        stats = storage.get_worker_stats("run-123")

        assert len(stats) == 2
        worker_ids = {stat["worker_id"] for stat in stats}
        assert worker_ids == {"worker-1", "worker-2"}

        # Each worker should have 3 tasks
        for stat in stats:
            assert stat["tasks_completed"] == 3
