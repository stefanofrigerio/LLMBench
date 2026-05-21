"""Tests for worker registry"""

import pytest
import asyncio
from datetime import datetime, timedelta

from src.llmbench.controller.worker_registry import WorkerRegistry, WorkerInfo


@pytest.fixture
def registry():
    """Fixture for worker registry"""
    return WorkerRegistry(heartbeat_timeout=60)


@pytest.fixture
def worker_info():
    """Fixture for worker info"""
    return {
        "worker_id": "worker-1",
        "ip_address": "192.168.1.100",
        "models_available": ["model-a", "model-b"],
        "metadata": {"region": "us-central1"},
    }


class TestWorkerRegistry:
    """Tests for WorkerRegistry class"""

    @pytest.mark.asyncio
    async def test_register_new_worker(self, registry, worker_info):
        """Test registering a new worker"""
        worker = await registry.register(**worker_info)

        assert worker.worker_id == "worker-1"
        assert worker.ip_address == "192.168.1.100"
        assert worker.status == "idle"
        assert worker.models_available == ["model-a", "model-b"]
        assert worker.metadata["region"] == "us-central1"

        # Check it's in registry
        retrieved = registry.get_worker("worker-1")
        assert retrieved is not None
        assert retrieved.worker_id == "worker-1"

    @pytest.mark.asyncio
    async def test_register_existing_worker(self, registry, worker_info):
        """Test re-registering an existing worker"""
        # Initial registration
        await registry.register(**worker_info)

        # Re-register with updated models
        updated_info = {**worker_info, "models_available": ["model-c"]}
        worker = await registry.register(**updated_info)

        assert worker.models_available == ["model-c"]

        # Should still be only one worker
        all_workers = registry.get_all_workers()
        assert len(all_workers) == 1

    @pytest.mark.asyncio
    async def test_heartbeat_existing_worker(self, registry, worker_info):
        """Test heartbeat updates last_heartbeat"""
        await registry.register(**worker_info)

        # Get initial heartbeat time
        worker = registry.get_worker("worker-1")
        initial_heartbeat = worker.last_heartbeat

        # Wait a bit
        await asyncio.sleep(0.1)

        # Send heartbeat
        success = await registry.heartbeat("worker-1")

        assert success is True
        worker = registry.get_worker("worker-1")
        assert worker.last_heartbeat > initial_heartbeat

    @pytest.mark.asyncio
    async def test_heartbeat_nonexistent_worker(self, registry):
        """Test heartbeat for non-existent worker returns False"""
        success = await registry.heartbeat("nonexistent")
        assert success is False

    @pytest.mark.asyncio
    async def test_heartbeat_brings_offline_worker_back(self, registry, worker_info):
        """Test heartbeat brings offline worker back online"""
        await registry.register(**worker_info)

        # Mark worker as offline
        await registry.mark_offline("worker-1")
        worker = registry.get_worker("worker-1")
        assert worker.status == "offline"

        # Send heartbeat
        await registry.heartbeat("worker-1")

        worker = registry.get_worker("worker-1")
        assert worker.status == "idle"

    @pytest.mark.asyncio
    async def test_assign_task(self, registry, worker_info):
        """Test assigning task to worker"""
        await registry.register(**worker_info)

        success = await registry.assign_task("worker-1", "task-123")

        assert success is True
        worker = registry.get_worker("worker-1")
        assert worker.status == "busy"
        assert worker.current_task_id == "task-123"

    @pytest.mark.asyncio
    async def test_assign_task_nonexistent_worker(self, registry):
        """Test assigning task to non-existent worker fails"""
        success = await registry.assign_task("nonexistent", "task-123")
        assert success is False

    @pytest.mark.asyncio
    async def test_complete_task_success(self, registry, worker_info):
        """Test completing task successfully"""
        await registry.register(**worker_info)
        await registry.assign_task("worker-1", "task-123")

        success = await registry.complete_task("worker-1", success=True)

        assert success is True
        worker = registry.get_worker("worker-1")
        assert worker.status == "idle"
        assert worker.current_task_id is None
        assert worker.tasks_completed == 1
        assert worker.tasks_failed == 0

    @pytest.mark.asyncio
    async def test_complete_task_failure(self, registry, worker_info):
        """Test completing task with failure"""
        await registry.register(**worker_info)
        await registry.assign_task("worker-1", "task-123")

        success = await registry.complete_task("worker-1", success=False)

        assert success is True
        worker = registry.get_worker("worker-1")
        assert worker.status == "idle"
        assert worker.tasks_completed == 0
        assert worker.tasks_failed == 1

    @pytest.mark.asyncio
    async def test_mark_offline(self, registry, worker_info):
        """Test manually marking worker offline"""
        await registry.register(**worker_info)
        await registry.assign_task("worker-1", "task-123")

        success = await registry.mark_offline("worker-1")

        assert success is True
        worker = registry.get_worker("worker-1")
        assert worker.status == "offline"
        assert worker.current_task_id is None  # Task cleared

    @pytest.mark.asyncio
    async def test_unregister_worker(self, registry, worker_info):
        """Test unregistering a worker"""
        await registry.register(**worker_info)

        success = await registry.unregister("worker-1")

        assert success is True
        worker = registry.get_worker("worker-1")
        assert worker is None

    @pytest.mark.asyncio
    async def test_unregister_nonexistent(self, registry):
        """Test unregistering non-existent worker"""
        success = await registry.unregister("nonexistent")
        assert success is False

    @pytest.mark.asyncio
    async def test_get_active_workers(self, registry):
        """Test getting only active workers"""
        await registry.register("worker-1", "192.168.1.100", ["model-a"])
        await registry.register("worker-2", "192.168.1.101", ["model-b"])
        await registry.register("worker-3", "192.168.1.102", ["model-c"])

        # Mark one offline
        await registry.mark_offline("worker-2")

        active = registry.get_active_workers()
        assert len(active) == 2
        assert all(w.status != "offline" for w in active)

    @pytest.mark.asyncio
    async def test_get_idle_workers(self, registry):
        """Test getting idle workers"""
        await registry.register("worker-1", "192.168.1.100", ["model-a"])
        await registry.register("worker-2", "192.168.1.101", ["model-b"])

        # Assign task to one
        await registry.assign_task("worker-1", "task-123")

        idle = registry.get_idle_workers()
        assert len(idle) == 1
        assert idle[0].worker_id == "worker-2"

    @pytest.mark.asyncio
    async def test_get_busy_workers(self, registry):
        """Test getting busy workers"""
        await registry.register("worker-1", "192.168.1.100", ["model-a"])
        await registry.register("worker-2", "192.168.1.101", ["model-b"])

        await registry.assign_task("worker-1", "task-123")

        busy = registry.get_busy_workers()
        assert len(busy) == 1
        assert busy[0].worker_id == "worker-1"

    @pytest.mark.asyncio
    async def test_get_offline_workers(self, registry):
        """Test getting offline workers"""
        await registry.register("worker-1", "192.168.1.100", ["model-a"])
        await registry.register("worker-2", "192.168.1.101", ["model-b"])

        await registry.mark_offline("worker-1")

        offline = registry.get_offline_workers()
        assert len(offline) == 1
        assert offline[0].worker_id == "worker-1"

    @pytest.mark.asyncio
    async def test_get_stats(self, registry):
        """Test getting registry statistics"""
        await registry.register("worker-1", "192.168.1.100", ["model-a"])
        await registry.register("worker-2", "192.168.1.101", ["model-b"])

        await registry.assign_task("worker-1", "task-123")
        await registry.complete_task("worker-1", success=True)

        await registry.assign_task("worker-2", "task-456")
        await registry.complete_task("worker-2", success=False)

        await registry.mark_offline("worker-2")

        stats = registry.get_stats()
        assert stats["total_workers"] == 2
        assert stats["idle"] == 1
        assert stats["busy"] == 0
        assert stats["offline"] == 1
        assert stats["total_tasks_completed"] == 1
        assert stats["total_tasks_failed"] == 1

    @pytest.mark.asyncio
    async def test_check_timeouts(self, registry):
        """Test automatic timeout detection"""
        # Create registry with 1 second timeout
        registry = WorkerRegistry(heartbeat_timeout=1)

        await registry.register("worker-1", "192.168.1.100", ["model-a"])

        # Set old heartbeat
        worker = registry.get_worker("worker-1")
        worker.last_heartbeat = datetime.now() - timedelta(seconds=2)

        # Check timeouts
        marked_offline = await registry.check_timeouts()

        assert marked_offline == 1
        worker = registry.get_worker("worker-1")
        assert worker.status == "offline"

    @pytest.mark.asyncio
    async def test_check_timeouts_already_offline(self, registry):
        """Test timeout check ignores already offline workers"""
        registry = WorkerRegistry(heartbeat_timeout=1)

        await registry.register("worker-1", "192.168.1.100", ["model-a"])
        await registry.mark_offline("worker-1")

        # Set very old heartbeat
        worker = registry.get_worker("worker-1")
        worker.last_heartbeat = datetime.now() - timedelta(hours=1)

        # Check timeouts
        marked_offline = await registry.check_timeouts()

        assert marked_offline == 0  # Already offline, not counted

    @pytest.mark.asyncio
    async def test_monitoring_lifecycle(self, registry):
        """Test starting and stopping monitoring"""
        # Start monitoring
        await registry.start_monitoring(check_interval=1)

        assert registry._monitor_task is not None
        assert not registry._monitor_task.done()

        # Stop monitoring
        await registry.stop_monitoring()

        assert registry._monitor_task.done()

    @pytest.mark.asyncio
    async def test_monitoring_detects_timeout(self):
        """Test monitoring loop detects timeout"""
        registry = WorkerRegistry(heartbeat_timeout=1)

        await registry.register("worker-1", "192.168.1.100", ["model-a"])

        # Set old heartbeat
        worker = registry.get_worker("worker-1")
        worker.last_heartbeat = datetime.now() - timedelta(seconds=2)

        # Start monitoring with fast check
        await registry.start_monitoring(check_interval=0.5)

        # Wait for monitoring to run
        await asyncio.sleep(1)

        # Worker should be offline
        worker = registry.get_worker("worker-1")
        assert worker.status == "offline"

        await registry.stop_monitoring()

    @pytest.mark.asyncio
    async def test_multiple_workers_lifecycle(self, registry):
        """Test full lifecycle with multiple workers"""
        # Register 3 workers
        for i in range(3):
            await registry.register(
                f"worker-{i}",
                f"192.168.1.{100+i}",
                [f"model-{i}"],
            )

        # Assign tasks
        await registry.assign_task("worker-0", "task-1")
        await registry.assign_task("worker-1", "task-2")

        # Complete one success, one failure
        await registry.complete_task("worker-0", success=True)
        await registry.complete_task("worker-1", success=False)

        # Mark one offline
        await registry.mark_offline("worker-2")

        stats = registry.get_stats()
        assert stats["total_workers"] == 3
        assert stats["idle"] == 2
        assert stats["offline"] == 1
        assert stats["total_tasks_completed"] == 1
        assert stats["total_tasks_failed"] == 1
