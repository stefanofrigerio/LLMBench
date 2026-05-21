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
    return TaskQueue()


@pytest.fixture
def registry():
    return WorkerRegistry(heartbeat_timeout=60)


@pytest.fixture
def work_items():
    model_config = ModelConfig(
        name="test-model",
        provider="ollama",
        model_id="test:1b",
        temperature=0.2,
    )
    test_case = TestCase(input_data="test", expected_output="output", complexity=3)
    return [
        WorkItem.create(model_config, Capability.CODE_GENERATION, test_case)
        for _ in range(10)
    ]


def _make_result() -> BenchmarkResult:
    return BenchmarkResult(
        point=BenchmarkPoint(Capability.CODE_GENERATION, 3),
        model_name="test-model",
        score=0.9,
        latency_ms=1000.0,
        cost_estimate=0.0,
    )


class TestDistributedFlow:

    @pytest.mark.asyncio
    async def test_single_worker_flow(self, queue, registry, work_items):
        await registry.register(
            worker_id="worker-1",
            ip_address="192.168.1.100",
            models_available=["test-model"],
        )
        await queue.enqueue_batch(work_items)
        assert queue.get_status()["queued"] == 10

        completed_tasks = []
        for _ in range(10):
            task = await queue.dequeue("worker-1", timeout=1.0)
            assert task is not None

            await registry.assign_task("worker-1", task.task_id)
            await queue.complete(task.task_id, _make_result())
            await registry.complete_task("worker-1", success=True)
            completed_tasks.append(task.task_id)

        assert queue.is_complete()
        assert queue.get_status()["completed"] == 10

        worker = registry.get_worker("worker-1")
        assert worker.tasks_completed == 10
        assert worker.status == "idle"

    @pytest.mark.asyncio
    async def test_multi_worker_parallel_flow(self, queue, registry, work_items):
        for i in range(3):
            await registry.register(
                worker_id=f"worker-{i}",
                ip_address=f"192.168.1.{100+i}",
                models_available=["test-model"],
            )
        await queue.enqueue_batch(work_items)

        async def worker_process(worker_id):
            processed = 0
            while True:
                task = await queue.dequeue(worker_id, timeout=0.5)
                if task is None:
                    break
                await registry.assign_task(worker_id, task.task_id)
                await asyncio.sleep(0.01)
                await queue.complete(task.task_id, _make_result())
                await registry.complete_task(worker_id, success=True)
                processed += 1
            return processed

        results = await asyncio.gather(
            worker_process("worker-0"),
            worker_process("worker-1"),
            worker_process("worker-2"),
        )

        assert sum(results) == 10
        assert queue.is_complete()
        for i in range(3):
            assert registry.get_worker(f"worker-{i}").tasks_completed > 0

    @pytest.mark.asyncio
    async def test_worker_failure_and_retry(self, queue, registry, work_items):
        await registry.register("worker-1", "192.168.1.100", ["test-model"])
        await queue.enqueue(work_items[0])

        task = await queue.dequeue("worker-1", timeout=1.0)
        await registry.assign_task("worker-1", task.task_id)

        await queue.fail(task.task_id, "Worker crashed", max_retries=3)
        await registry.complete_task("worker-1", success=False)

        status = queue.get_status()
        assert status["queued"] == 1
        assert status["failed"] == 0

        worker = registry.get_worker("worker-1")
        assert worker.tasks_failed == 1
        assert worker.status == "idle"

        retry_task = await queue.dequeue("worker-1", timeout=1.0)
        assert retry_task.task_id == task.task_id
        assert retry_task.retry_count == 1

        await registry.assign_task("worker-1", retry_task.task_id)
        await queue.complete(retry_task.task_id, _make_result())
        await registry.complete_task("worker-1", success=True)

        assert queue.is_complete()
        assert queue.get_status()["completed"] == 1

    @pytest.mark.asyncio
    async def test_worker_timeout_recovery(self, queue, registry, work_items):
        await registry.register("worker-1", "192.168.1.100", ["test-model"])
        await queue.enqueue(work_items[0])
        task = await queue.dequeue("worker-1", timeout=1.0)
        await registry.assign_task("worker-1", task.task_id)

        from datetime import datetime, timedelta

        task_in_queue = queue._pending[task.task_id]
        task_in_queue.started_at = datetime.now() - timedelta(seconds=120)

        worker = registry.get_worker("worker-1")
        worker.last_heartbeat = datetime.now() - timedelta(seconds=120)

        marked_offline = await registry.check_timeouts()
        assert marked_offline == 1

        worker = registry.get_worker("worker-1")
        assert worker.status == "offline"
        assert worker.current_task_id is None

        requeued = await queue.requeue_stale_tasks(timeout_seconds=60)
        assert requeued == 1

        await registry.register("worker-2", "192.168.1.101", ["test-model"])
        retry_task = await queue.dequeue("worker-2", timeout=1.0)
        assert retry_task.task_id == task.task_id

        await registry.assign_task("worker-2", retry_task.task_id)
        await queue.complete(retry_task.task_id, _make_result())
        await registry.complete_task("worker-2", success=True)

        assert queue.is_complete()
        assert registry.get_worker("worker-2").tasks_completed == 1

    @pytest.mark.asyncio
    async def test_priority_scheduling(self, queue, registry):
        model_config = ModelConfig("test", "ollama", "test:1b", 0.2)
        test_case = TestCase("test", "output", 3)

        low_priority = WorkItem.create(model_config, Capability.CODE_GENERATION, test_case, priority=1)
        high_priority = WorkItem.create(model_config, Capability.CODE_GENERATION, test_case, priority=10)

        await queue.enqueue(low_priority)
        await queue.enqueue(high_priority)

        await registry.register("worker-1", "192.168.1.100", ["test"])

        first_task = await queue.dequeue("worker-1", timeout=1.0)
        assert first_task.task_id == high_priority.task_id

        await queue.complete(first_task.task_id, _make_result())

        second_task = await queue.dequeue("worker-1", timeout=1.0)
        assert second_task.task_id == low_priority.task_id

    @pytest.mark.asyncio
    async def test_worker_heartbeat_monitoring(self, registry):
        await registry.start_monitoring(check_interval=0.5)
        await registry.register("worker-1", "192.168.1.100", ["test"])

        from datetime import datetime, timedelta
        worker = registry.get_worker("worker-1")
        worker.last_heartbeat = datetime.now() - timedelta(seconds=120)

        await asyncio.sleep(1)

        worker = registry.get_worker("worker-1")
        assert worker.status == "offline"

        await registry.stop_monitoring()

    @pytest.mark.asyncio
    async def test_load_balancing(self, queue, registry):
        for i in range(3):
            await registry.register(f"worker-{i}", f"192.168.1.{100+i}", ["test"])

        model_config = ModelConfig("test", "ollama", "test:1b", 0.2)
        test_case = TestCase("test", "output", 3)

        items = [
            WorkItem.create(model_config, Capability.CODE_GENERATION, test_case)
            for _ in range(30)
        ]
        await queue.enqueue_batch(items)

        async def worker_process(worker_id):
            count = 0
            while True:
                task = await queue.dequeue(worker_id, timeout=0.5)
                if not task:
                    break
                await asyncio.sleep(0.01)  # yield to allow other workers interleaving
                await queue.complete(task.task_id, _make_result())
                await registry.complete_task(worker_id, success=True)
                count += 1
            return count

        results = await asyncio.gather(
            worker_process("worker-0"),
            worker_process("worker-1"),
            worker_process("worker-2"),
        )

        assert all(count >= 1 for count in results)
        assert sum(results) == 30
