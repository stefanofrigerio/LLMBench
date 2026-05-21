"""
Worker registry for tracking distributed worker health and status.

Maintains real-time information about worker availability, current
assignments, and heartbeat monitoring.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional


@dataclass
class WorkerInfo:
    """Information about a registered worker."""

    worker_id: str
    ip_address: str
    status: Literal["idle", "busy", "offline"]
    current_task_id: Optional[str] = None
    last_heartbeat: datetime = field(default_factory=datetime.now)
    registered_at: datetime = field(default_factory=datetime.now)
    models_available: List[str] = field(default_factory=list)
    tasks_completed: int = 0
    tasks_failed: int = 0
    metadata: Dict[str, any] = field(default_factory=dict)


class WorkerRegistry:
    """
    Registry for managing worker lifecycle and health.

    Tracks worker registration, heartbeats, task assignments,
    and automatically marks workers offline after timeout.
    """

    def __init__(self, heartbeat_timeout: int = 60):
        """
        Initialize worker registry.

        Args:
            heartbeat_timeout: Seconds without heartbeat before marking offline
        """
        self._workers: Dict[str, WorkerInfo] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_timeout = heartbeat_timeout
        self._monitor_task: Optional[asyncio.Task] = None

    async def register(
        self,
        worker_id: str,
        ip_address: str,
        models_available: List[str],
        metadata: Optional[Dict] = None,
    ) -> WorkerInfo:
        """Register a new worker or update existing registration."""
        async with self._lock:
            if worker_id in self._workers:
                # Re-registration (worker restarted)
                worker = self._workers[worker_id]
                worker.status = "idle"
                worker.last_heartbeat = datetime.now()
                worker.models_available = models_available
                if metadata:
                    worker.metadata.update(metadata)
            else:
                # New worker
                worker = WorkerInfo(
                    worker_id=worker_id,
                    ip_address=ip_address,
                    status="idle",
                    models_available=models_available,
                    metadata=metadata or {},
                )
                self._workers[worker_id] = worker

            return worker

    async def heartbeat(self, worker_id: str) -> bool:
        """
        Record worker heartbeat.

        Returns:
            True if worker exists, False otherwise
        """
        async with self._lock:
            if worker_id not in self._workers:
                return False

            worker = self._workers[worker_id]
            worker.last_heartbeat = datetime.now()

            # If worker was offline, bring it back online
            if worker.status == "offline":
                worker.status = "idle"

            return True

    async def assign_task(self, worker_id: str, task_id: str) -> bool:
        """Mark worker as busy with a task."""
        async with self._lock:
            if worker_id not in self._workers:
                return False

            worker = self._workers[worker_id]
            worker.status = "busy"
            worker.current_task_id = task_id
            return True

    async def complete_task(self, worker_id: str, success: bool = True) -> bool:
        """Mark worker's current task as complete and return to idle."""
        async with self._lock:
            if worker_id not in self._workers:
                return False

            worker = self._workers[worker_id]
            worker.status = "idle"
            worker.current_task_id = None

            if success:
                worker.tasks_completed += 1
            else:
                worker.tasks_failed += 1

            return True

    async def mark_offline(self, worker_id: str) -> bool:
        """Manually mark a worker as offline."""
        async with self._lock:
            if worker_id not in self._workers:
                return False

            worker = self._workers[worker_id]
            worker.status = "offline"
            worker.current_task_id = None
            return True

    async def unregister(self, worker_id: str) -> bool:
        """Remove a worker from the registry."""
        async with self._lock:
            if worker_id in self._workers:
                del self._workers[worker_id]
                return True
            return False

    def get_worker(self, worker_id: str) -> Optional[WorkerInfo]:
        """Get information about a specific worker."""
        return self._workers.get(worker_id)

    def get_all_workers(self) -> List[WorkerInfo]:
        """Get all registered workers."""
        return list(self._workers.values())

    def get_active_workers(self) -> List[WorkerInfo]:
        """Get workers that are online (idle or busy)."""
        return [w for w in self._workers.values() if w.status != "offline"]

    def get_idle_workers(self) -> List[WorkerInfo]:
        """Get workers available for new tasks."""
        return [w for w in self._workers.values() if w.status == "idle"]

    def get_busy_workers(self) -> List[WorkerInfo]:
        """Get workers currently executing tasks."""
        return [w for w in self._workers.values() if w.status == "busy"]

    def get_offline_workers(self) -> List[WorkerInfo]:
        """Get workers marked as offline."""
        return [w for w in self._workers.values() if w.status == "offline"]

    def get_stats(self) -> dict:
        """Get registry statistics."""
        workers = list(self._workers.values())
        return {
            "total_workers": len(workers),
            "idle": len([w for w in workers if w.status == "idle"]),
            "busy": len([w for w in workers if w.status == "busy"]),
            "offline": len([w for w in workers if w.status == "offline"]),
            "total_tasks_completed": sum(w.tasks_completed for w in workers),
            "total_tasks_failed": sum(w.tasks_failed for w in workers),
        }

    async def check_timeouts(self) -> int:
        """
        Check for workers that haven't sent heartbeat in timeout period.

        Returns:
            Number of workers marked offline
        """
        now = datetime.now()
        marked_offline = 0

        async with self._lock:
            for worker in self._workers.values():
                if worker.status == "offline":
                    continue

                time_since_heartbeat = (now - worker.last_heartbeat).total_seconds()
                if time_since_heartbeat > self._heartbeat_timeout:
                    worker.status = "offline"
                    worker.current_task_id = None
                    marked_offline += 1

        return marked_offline

    async def start_monitoring(self, check_interval: int = 30):
        """Start background task to monitor worker heartbeats."""
        if self._monitor_task and not self._monitor_task.done():
            return  # Already monitoring

        async def monitor_loop():
            while True:
                await asyncio.sleep(check_interval)
                marked_offline = await self.check_timeouts()
                if marked_offline > 0:
                    print(f"⚠️  Marked {marked_offline} workers offline due to timeout")

        self._monitor_task = asyncio.create_task(monitor_loop())

    async def stop_monitoring(self):
        """Stop background heartbeat monitoring."""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
