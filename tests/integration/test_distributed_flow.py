"""Integration tests for distributed benchmark flow"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from src.llmbench.controller.task_queue import TaskQueue, WorkItem
from src.llmbench.controller.worker_registry import WorkerRegistry
from src.llmbench.cube import Capability, BenchmarkResult, BenchmarkPoint
from src.llmbench.models.base import ModelConfig
from src.llmbench.capabilities.base import TestCase


@pytest.fixture
def queue():
    """Fixture for task queue"""
    return TaskQueue()


@pytest.fixture
def registry():
    """Fixture for worker registry"""
    return WorkerRegistry(heartbeat_timeout=60)


@pytest.fixture
def work_items():
    """Fixture for sample work items"""
    model_config = ModelConfig(
        name="test-model",
        provider="ollama",
        model_id="test:1b",
        temperature=0.2,
    )

    test_case = TestCase(
        input_data="test",
        expected_output="output",
        complexity=3,
        sensitivity=4,
    )

    return [
        WorkItem.create(model_config, Capability.CODE_GENERATION, test_case)
        for _ in range(10)
    ]


class TestDistributedFlow:
    """Integration tests for complete distributed flow"""

    @pytest.mark.asyncio
    async def test_single_worker_flow(self, queue, registry, work_items):
        """Test complete flow with single worker"""
        # 1. Register worker
        await registry.register(
            worker_id="worker-1",
            ip_address="192.168.1.100",
            models_available=["test-model"],
        )

        # 2. Enqueue tasks
        await queue.enqueue_batch(work_items)

        assert queue.get_status()["queued"] == 10

        # 3. Worker processes tasks
        completed_tasks = []
        for _ in range(10):
            # Dequeue
            task = await queue.dequeue("worker-1", timeout=1.0)
            assert task is not None

            # Update worker status
            await registry.assign_task("worker-1", task.task_id)

            # Simulate task execution
            result = BenchmarkResult(
                point=BenchmarkPoint(Capability.CODE_GENERATION, 3, 4),
                model_name="test-model",
                score=0.9,
                latency_ms=1000.0,
                cost_estimate=0.0,
            )

            # Complete task
            await queue.complete(task.task_id, result)
            await registry.complete_task("worker-1", success=True)

            completed_tasks.append(task.task_id)

        # 4. Verify completion
        assert queue.is_complete()
        assert queue.get_status()["completed"] == 10

        worker = registry.get_worker("worker-1")
        assert worker.tasks_completed == 10
        assert worker.status == "idle"

    @pytest.mark.asyncio
    async def test_multi_worker_parallel_flow(self, queue, registry, work_items):
        """Test parallel execution with multiple workers"""
        # 1. Register multiple workers
        for i in range(3):
            await registry.register(
                worker_id=f"worker-{i}",
                ip_address=f"192.168.1.{100+i}",
                models_available=["test-model"],
            )

        # 2. Enqueue tasks
        await queue.enqueue_batch(work_items)

        # 3. Simulate workers processing in parallel
        async def worker_process(worker_id):
            processed = 0
            while True:
                # Try to dequeue
                task = await queue.dequeue(worker_id, timeout=0.5)
                if task is None:
                    break  # No more work

                # Process task
                await registry.assign_task(worker_id, task.task_id)

                # Simulate work
                await asyncio.sleep(0.01)

                result = BenchmarkResult(
                    point=BenchmarkPoint(Capability.CODE_GENERATION, 3, 4),
                    model_name="test-model",
                    score=0.9,
                    latency_ms=1000.0,
                    cost_estimate=0.0,
                )

                await queue.complete(task.task_id, result)
                await registry.complete_task(worker_id, success=True)

                processed += 1

            return processed

        # Run workers in parallel
        results = await asyncio.gather(
            worker_process("worker-0"),
            worker_process("worker-1"),
            worker_process("worker-2"),
        )

        # 4. Verify all tasks completed
        total_processed = sum(results)
        assert total_processed == 10
        assert queue.is_complete()

        # Each worker should have processed some tasks
        for i in range(3):
            worker = registry.get_worker(f"worker-{i}")
            assert worker.tasks_completed > 0

    @pytest.mark.asyncio
    async def test_worker_failure_and_retry(self, queue, registry, work_items):
        """Test task retry when worker fails"""
        # 1. Register worker
        await registry.register("worker-1", "192.168.1.100", ["test-model"])

        # 2. Enqueue single task
        await queue.enqueue(work_items[0])

        # 3. Worker dequeues and fails
        task = await queue.dequeue("worker-1", timeout=1.0)
        await registry.assign_task("worker-1", task.task_id)

        # Simulate failure
        await queue.fail(task.task_id, "Worker crashed", max_retries=3)
        await registry.complete_task("worker-1", success=False)

        # 4. Verify task requeued
        status = queue.get_status()
        assert status["queued"] == 1  # Requeued
        assert status["failed"] == 0  # Not permanently failed

        worker = registry.get_worker("worker-1")
        assert worker.tasks_failed == 1
        assert worker.status == "idle"

        # 5. Worker retries successfully
        retry_task = await queue.dequeue("worker-1", timeout=1.0)
        assert retry_task.task_id == task.task_id
        assert retry_task.retry_count == 1

        await registry.assign_task("worker-1", retry_task.task_id)

        result = BenchmarkResult(
            point=BenchmarkPoint(Capability.CODE_GENERATION, 3, 4),
            model_name="test-model",
            score=0.9,
            latency_ms=1000.0,
            cost_estimate=0.0,
        )

        await queue.complete(retry_task.task_id, result)
        await registry.complete_task("worker-1", success=True)

        # 6. Verify success
        assert queue.is_complete()
        assert queue.get_status()["completed"] == 1

    @pytest.mark.asyncio
    async def test_worker_timeout_recovery(self, queue, registry, work_items):
        """Test recovering from worker timeout"""
        # 1. Register worker
        await registry.register("worker-1", "192.168.1.100", ["test-model"])

        # 2. Enqueue and dequeue task
        await queue.enqueue(work_items[0])
        task = await queue.dequeue("worker-1", timeout=1.0)
        await registry.assign_task("worker-1", task.task_id)

        # 3. Simulate worker timeout (set old started_at time for requeue)
        from datetime import datetime, timedelta

        # Mark task as started long ago
        task_in_queue = queue._pending[task.task_id]
        task_in_queue.started_at = datetime.now() - timedelta(seconds=120)

        worker = registry.get_worker("worker-1")
        worker.last_heartbeat = datetime.now() - timedelta(seconds=120)

        # 4. Check timeout marks worker offline
        marked_offline = await registry.check_timeouts()
        assert marked_offline == 1

        worker = registry.get_worker("worker-1")
        assert worker.status == "offline"
        assert worker.current_task_id is None  # Task cleared

        # 5. Requeue stale tasks
        requeued = await queue.requeue_stale_tasks(timeout_seconds=60)
        assert requeued == 1

        # 6. New worker picks up task
        await registry.register("worker-2", "192.168.1.101", ["test-model"])

        retry_task = await queue.dequeue("worker-2", timeout=1.0)
        assert retry_task.task_id == task.task_id

        await registry.assign_task("worker-2", retry_task.task_id)

        result = BenchmarkResult(
            point=BenchmarkPoint(Capability.CODE_GENERATION, 3, 4),
            model_name="test-model",
            score=0.9,
            latency_ms=1000.0,
            cost_estimate=0.0,
        )

        await queue.complete(retry_task.task_id, result)
        await registry.complete_task("worker-2", success=True)

        # 7. Verify recovery
        assert queue.is_complete()
        worker2 = registry.get_worker("worker-2")
        assert worker2.tasks_completed == 1

    @pytest.mark.asyncio
    async def test_priority_scheduling(self, queue, registry):
        """Test high priority tasks processed first"""
        model_config = ModelConfig("test", "ollama", "test:1b", 0.2)
        test_case = TestCase("test", "output", 3, 4)

        # Enqueue with different priorities
        low_priority = WorkItem.create(model_config, Capability.CODE_GENERATION, test_case, priority=1)
        high_priority = WorkItem.create(model_config, Capability.CODE_GENERATION, test_case, priority=10)

        await queue.enqueue(low_priority)
        await queue.enqueue(high_priority)

        # Register worker
        await registry.register("worker-1", "192.168.1.100", ["test"])

        # Dequeue should get high priority first
        first_task = await queue.dequeue("worker-1", timeout=1.0)
        assert first_task.task_id == high_priority.task_id

        # Complete and get next
        result = BenchmarkResult(
            point=BenchmarkPoint(Capability.CODE_GENERATION, 3, 4),
            model_name="test",
            score=0.9,
            latency_ms=1000.0,
            cost_estimate=0.0,
        )
        await queue.complete(first_task.task_id, result)

        second_task = await queue.dequeue("worker-1", timeout=1.0)
        assert second_task.task_id == low_priority.task_id

    @pytest.mark.asyncio
    async def test_worker_heartbeat_monitoring(self, registry):
        """Test automatic worker monitoring"""
        # Start monitoring with fast interval
        await registry.start_monitoring(check_interval=0.5)

        # Register worker
        await registry.register("worker-1", "192.168.1.100", ["test"])

        # Set old heartbeat
        from datetime import datetime, timedelta

        worker = registry.get_worker("worker-1")
        worker.last_heartbeat = datetime.now() - timedelta(seconds=120)

        # Wait for monitoring to detect timeout
        await asyncio.sleep(1)

        # Worker should be marked offline
        worker = registry.get_worker("worker-1")
        assert worker.status == "offline"

        # Stop monitoring
        await registry.stop_monitoring()

    @pytest.mark.asyncio
    async def test_load_balancing(self, queue, registry):
        """Test tasks distributed evenly across workers"""
        # Register 3 workers
        for i in range(3):
            await registry.register(f"worker-{i}", f"192.168.1.{100+i}", ["test"])

        # Enqueue 30 tasks
        model_config = ModelConfig("test", "ollama", "test:1b", 0.2)
        test_case = TestCase("test", "output", 3, 4)

        items = [
            WorkItem.create(model_config, Capability.CODE_GENERATION, test_case)
            for _ in range(30)
        ]
        await queue.enqueue_batch(items)

        # Process tasks in parallel
        async def worker_process(worker_id):
            count = 0
            while True:
                task = await queue.dequeue(worker_id, timeout=0.5)
                if not task:
                    break

                result = BenchmarkResult(
                    point=BenchmarkPoint(Capability.CODE_GENERATION, 3, 4),
                    model_name="test",
                    score=0.9,
                    latency_ms=1000.0,
                    cost_estimate=0.0,
                )

                await queue.complete(task.task_id, result)
                await registry.complete_task(worker_id, success=True)
                count += 1

            return count

        results = await asyncio.gather(
            worker_process("worker-0"),
            worker_process("worker-1"),
            worker_process("worker-2"),
        )

        # Each worker should have processed some tasks (roughly balanced)
        # Allow wider range due to async timing variations
        assert all(6 <= count <= 14 for count in results)
        assert sum(results) == 30
