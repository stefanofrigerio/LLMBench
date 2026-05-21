"""Tests for task queue system"""

import pytest
import asyncio
from datetime import datetime

from src.llmbench.controller.task_queue import TaskQueue, WorkItem
from src.llmbench.cube import Capability, BenchmarkResult, BenchmarkPoint
from src.llmbench.models.base import ModelConfig
from src.llmbench.capabilities.base import TestCase


@pytest.fixture
def model_config():
    """Fixture for model configuration"""
    return ModelConfig(
        name="test-model",
        provider="ollama",
        model_id="test:1b",
        temperature=0.2,
    )


@pytest.fixture
def test_case():
    """Fixture for test case"""
    return TestCase(
        input_data="test input",
        expected_output="test output",
        complexity=3,
    )


@pytest.fixture
def work_item(model_config, test_case):
    """Fixture for work item"""
    return WorkItem.create(
        model_config=model_config,
        capability=Capability.CODE_GENERATION,
        test_case=test_case,
    )


@pytest.fixture
def benchmark_result():
    """Fixture for benchmark result"""
    point = BenchmarkPoint(
        capability=Capability.CODE_GENERATION,
        complexity=3,
    )
    return BenchmarkResult(
        point=point,
        model_name="test-model",
        score=0.85,
        latency_ms=1500.0,
        cost_estimate=0.01,
    )


class TestWorkItem:
    """Tests for WorkItem dataclass"""

    def test_create_work_item(self, model_config, test_case):
        """Test work item creation"""
        item = WorkItem.create(
            model_config=model_config,
            capability=Capability.CODE_GENERATION,
            test_case=test_case,
            priority=1,
        )

        assert item.task_id is not None
        assert item.model_config == model_config
        assert item.capability == Capability.CODE_GENERATION
        assert item.test_case == test_case
        assert item.priority == 1
        assert item.retry_count == 0
        assert item.worker_id is None

    def test_work_item_timestamps(self, work_item):
        """Test work item has correct timestamps"""
        assert work_item.created_at is not None
        assert isinstance(work_item.created_at, datetime)
        assert work_item.started_at is None
        assert work_item.completed_at is None


class TestTaskQueue:
    """Tests for TaskQueue class"""

    @pytest.mark.asyncio
    async def test_enqueue_single_item(self, work_item):
        """Test enqueueing a single work item"""
        queue = TaskQueue()
        await queue.enqueue(work_item)

        status = queue.get_status()
        assert status["total_enqueued"] == 1
        assert status["queued"] == 1
        assert status["pending"] == 0
        assert status["completed"] == 0

    @pytest.mark.asyncio
    async def test_enqueue_batch(self, model_config, test_case):
        """Test batch enqueueing"""
        queue = TaskQueue()
        items = [
            WorkItem.create(model_config, Capability.CODE_GENERATION, test_case)
            for _ in range(5)
        ]

        await queue.enqueue_batch(items)

        status = queue.get_status()
        assert status["total_enqueued"] == 5
        assert status["queued"] == 5

    @pytest.mark.asyncio
    async def test_dequeue_item(self, work_item):
        """Test dequeueing a work item"""
        queue = TaskQueue()
        await queue.enqueue(work_item)

        dequeued = await queue.dequeue("worker-1", timeout=1.0)

        assert dequeued is not None
        assert dequeued.task_id == work_item.task_id
        assert dequeued.worker_id == "worker-1"
        assert dequeued.started_at is not None

        status = queue.get_status()
        assert status["queued"] == 0
        assert status["pending"] == 1

    @pytest.mark.asyncio
    async def test_dequeue_timeout(self):
        """Test dequeue timeout when queue is empty"""
        queue = TaskQueue()

        dequeued = await queue.dequeue("worker-1", timeout=0.1)

        assert dequeued is None

    @pytest.mark.asyncio
    async def test_priority_ordering(self, model_config, test_case):
        """Test that higher priority items are dequeued first"""
        queue = TaskQueue()

        # Enqueue low priority first
        low = WorkItem.create(model_config, Capability.CODE_GENERATION, test_case, priority=1)
        high = WorkItem.create(model_config, Capability.CODE_GENERATION, test_case, priority=10)
        medium = WorkItem.create(model_config, Capability.CODE_GENERATION, test_case, priority=5)

        await queue.enqueue(low)
        await queue.enqueue(high)
        await queue.enqueue(medium)

        # Dequeue should return high priority first
        first = await queue.dequeue("worker-1", timeout=1.0)
        second = await queue.dequeue("worker-1", timeout=1.0)
        third = await queue.dequeue("worker-1", timeout=1.0)

        assert first.task_id == high.task_id
        assert second.task_id == medium.task_id
        assert third.task_id == low.task_id

    @pytest.mark.asyncio
    async def test_complete_task(self, work_item, benchmark_result):
        """Test marking task as complete"""
        queue = TaskQueue()
        await queue.enqueue(work_item)

        dequeued = await queue.dequeue("worker-1", timeout=1.0)
        await queue.complete(dequeued.task_id, benchmark_result)

        status = queue.get_status()
        assert status["pending"] == 0
        assert status["completed"] == 1

        results = queue.get_results()
        assert len(results) == 1
        assert results[0] == benchmark_result

    @pytest.mark.asyncio
    async def test_fail_task_with_retry(self, work_item):
        """Test task failure with retry"""
        queue = TaskQueue()
        await queue.enqueue(work_item)

        dequeued = await queue.dequeue("worker-1", timeout=1.0)
        await queue.fail(dequeued.task_id, "Test error", max_retries=3)

        status = queue.get_status()
        assert status["pending"] == 0
        assert status["queued"] == 1  # Requeued
        assert status["failed"] == 0  # Not permanently failed yet

    @pytest.mark.asyncio
    async def test_fail_task_max_retries(self, work_item):
        """Test task failure exceeds max retries"""
        queue = TaskQueue()
        work_item.retry_count = 2  # Already tried twice
        await queue.enqueue(work_item)

        dequeued = await queue.dequeue("worker-1", timeout=1.0)
        await queue.fail(dequeued.task_id, "Test error", max_retries=3)

        status = queue.get_status()
        assert status["pending"] == 0
        assert status["failed"] == 1

        failed_tasks = queue.get_failed_tasks()
        assert len(failed_tasks) == 1
        assert failed_tasks[0][0].task_id == work_item.task_id
        assert failed_tasks[0][1] == "Test error"

    @pytest.mark.asyncio
    async def test_requeue_stale_tasks(self, work_item):
        """Test requeuing stale tasks (worker timeout)"""
        queue = TaskQueue()
        await queue.enqueue(work_item)

        # Dequeue and mark as started long ago
        dequeued = await queue.dequeue("worker-1", timeout=1.0)
        dequeued.started_at = datetime(2020, 1, 1)  # Very old

        # Requeue stale tasks
        requeued_count = await queue.requeue_stale_tasks(timeout_seconds=60)

        assert requeued_count == 1
        status = queue.get_status()
        assert status["pending"] == 0
        assert status["queued"] == 1

    @pytest.mark.asyncio
    async def test_is_complete(self, work_item, benchmark_result):
        """Test checking if queue is complete"""
        queue = TaskQueue()
        assert not queue.is_complete()  # Empty queue

        await queue.enqueue(work_item)
        assert not queue.is_complete()  # Has pending work

        dequeued = await queue.dequeue("worker-1", timeout=1.0)
        assert not queue.is_complete()  # Task in progress

        await queue.complete(dequeued.task_id, benchmark_result)
        assert queue.is_complete()  # All done

    @pytest.mark.asyncio
    async def test_completion_rate(self, model_config, test_case, benchmark_result):
        """Test completion rate calculation"""
        queue = TaskQueue()

        # Enqueue 5 items
        items = [
            WorkItem.create(model_config, Capability.CODE_GENERATION, test_case)
            for _ in range(5)
        ]
        await queue.enqueue_batch(items)

        # Complete 3
        for _ in range(3):
            dequeued = await queue.dequeue("worker-1", timeout=1.0)
            await queue.complete(dequeued.task_id, benchmark_result)

        status = queue.get_status()
        assert status["completion_rate"] == 0.6  # 3/5

    @pytest.mark.asyncio
    async def test_concurrent_dequeue(self, model_config, test_case):
        """Test multiple workers dequeueing concurrently"""
        queue = TaskQueue()

        # Enqueue 10 items
        items = [
            WorkItem.create(model_config, Capability.CODE_GENERATION, test_case)
            for _ in range(10)
        ]
        await queue.enqueue_batch(items)

        # Simulate 3 workers dequeueing
        async def worker_dequeue(worker_id):
            tasks = []
            for _ in range(3):
                task = await queue.dequeue(worker_id, timeout=1.0)
                if task:
                    tasks.append(task)
            return tasks

        results = await asyncio.gather(
            worker_dequeue("worker-1"),
            worker_dequeue("worker-2"),
            worker_dequeue("worker-3"),
        )

        # Should have dequeued 9 items total (3 per worker)
        total_dequeued = sum(len(tasks) for tasks in results)
        assert total_dequeued == 9

        # All task IDs should be unique
        all_task_ids = [task.task_id for tasks in results for task in tasks]
        assert len(all_task_ids) == len(set(all_task_ids))

        status = queue.get_status()
        assert status["pending"] == 9
        assert status["queued"] == 1
