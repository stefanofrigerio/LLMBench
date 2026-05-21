"""
Task queue system for distributed benchmark execution.

The task queue manages work items (benchmark tasks) and tracks their
lifecycle from creation through completion or failure.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from ..cube import Capability, BenchmarkResult
from ..models.base import ModelConfig
from ..capabilities.base import TestCase


@dataclass(order=True)
class WorkItem:
    """
    A single unit of work representing one benchmark test.

    Each WorkItem corresponds to testing one model on one capability
    with one test case at a specific complexity/sensitivity point.
    """

    # Fields without defaults must come first
    task_id: str = field(compare=False)
    model_config: ModelConfig = field(compare=False)
    capability: Capability = field(compare=False)
    test_case: TestCase = field(compare=False)

    # Fields with defaults (including priority for ordering)
    priority: int = field(default=0, compare=True)
    created_at: datetime = field(default_factory=datetime.now, compare=False)
    started_at: Optional[datetime] = field(default=None, compare=False)
    completed_at: Optional[datetime] = field(default=None, compare=False)
    worker_id: Optional[str] = field(default=None, compare=False)
    retry_count: int = field(default=0, compare=False)

    @classmethod
    def create(
        cls,
        model_config: ModelConfig,
        capability: Capability,
        test_case: TestCase,
        priority: int = 0,
    ) -> "WorkItem":
        """Create a new work item with auto-generated task ID."""
        return cls(
            task_id=str(uuid.uuid4()),
            model_config=model_config,
            capability=capability,
            test_case=test_case,
            priority=priority,
        )


class TaskQueue:
    """
    Async task queue for managing distributed benchmark execution.

    Provides FIFO queue with priority support, task lifecycle tracking,
    and failure recovery (requeuing failed tasks).
    """

    def __init__(self):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._pending: Dict[str, WorkItem] = {}  # Tasks being worked on
        self._completed: Dict[str, BenchmarkResult] = {}
        self._failed: Dict[str, tuple[WorkItem, str]] = {}  # task_id -> (item, error)
        self._lock = asyncio.Lock()
        self._total_enqueued = 0

    async def enqueue(self, item: WorkItem) -> None:
        """Add a work item to the queue."""
        async with self._lock:
            # WorkItem is orderable by priority (negated for max-heap behavior)
            # Create a new item with negated priority for proper ordering
            queued_item = WorkItem(
                task_id=item.task_id,
                model_config=item.model_config,
                capability=item.capability,
                test_case=item.test_case,
                priority=-item.priority,  # Negate for max-heap
                created_at=item.created_at,
                started_at=item.started_at,
                completed_at=item.completed_at,
                worker_id=item.worker_id,
                retry_count=item.retry_count,
            )
            await self._queue.put(queued_item)
            self._total_enqueued += 1

    async def enqueue_batch(self, items: list[WorkItem]) -> None:
        """Add multiple work items efficiently."""
        for item in items:
            await self.enqueue(item)

    async def dequeue(self, worker_id: str, timeout: Optional[float] = None) -> Optional[WorkItem]:
        """
        Dequeue next work item for a worker.

        Args:
            worker_id: ID of worker requesting work
            timeout: Maximum seconds to wait for work (None = wait forever)

        Returns:
            WorkItem if available, None if timeout expires
        """
        try:
            item = await asyncio.wait_for(
                self._queue.get(),
                timeout=timeout
            )

            async with self._lock:
                # Restore original priority (un-negate)
                item.priority = abs(item.priority)
                item.started_at = datetime.now()
                item.worker_id = worker_id
                self._pending[item.task_id] = item

            return item

        except asyncio.TimeoutError:
            return None

    async def complete(self, task_id: str, result: BenchmarkResult) -> None:
        """Mark a task as successfully completed."""
        async with self._lock:
            if task_id in self._pending:
                item = self._pending.pop(task_id)
                item.completed_at = datetime.now()
                self._completed[task_id] = result

    async def fail(self, task_id: str, error: str, max_retries: int = 3) -> None:
        """
        Mark a task as failed.

        If retry_count < max_retries, the task is requeued.
        Otherwise, it's marked as permanently failed.
        """
        async with self._lock:
            if task_id not in self._pending:
                return

            item = self._pending.pop(task_id)
            item.retry_count += 1

            if item.retry_count < max_retries:
                # Reset timestamps and requeue
                queued_item = WorkItem(
                    task_id=item.task_id,
                    model_config=item.model_config,
                    capability=item.capability,
                    test_case=item.test_case,
                    priority=-abs(item.priority),  # Negate for max-heap
                    created_at=item.created_at,
                    retry_count=item.retry_count,
                )
                await self._queue.put(queued_item)
            else:
                # Permanently failed
                self._failed[task_id] = (item, error)

    async def requeue_stale_tasks(self, timeout_seconds: int = 300) -> int:
        """
        Requeue tasks that have been pending too long (worker likely died).

        Returns:
            Number of tasks requeued
        """
        now = datetime.now()
        requeued = 0

        async with self._lock:
            stale_tasks = [
                task_id
                for task_id, item in self._pending.items()
                if item.started_at and (now - item.started_at).total_seconds() > timeout_seconds
            ]

            for task_id in stale_tasks:
                item = self._pending.pop(task_id)
                item.started_at = None
                item.worker_id = None
                # Re-enqueue with negated priority
                queued_item = WorkItem(
                    task_id=item.task_id,
                    model_config=item.model_config,
                    capability=item.capability,
                    test_case=item.test_case,
                    priority=-abs(item.priority),  # Negate for max-heap
                    created_at=item.created_at,
                )
                self._queue.put_nowait(queued_item)
                requeued += 1

        return requeued

    def get_status(self) -> dict:
        """Get current queue statistics."""
        return {
            "total_enqueued": self._total_enqueued,
            "queued": self._queue.qsize(),
            "pending": len(self._pending),
            "completed": len(self._completed),
            "failed": len(self._failed),
            "completion_rate": (
                len(self._completed) / self._total_enqueued
                if self._total_enqueued > 0
                else 0.0
            ),
        }

    def is_complete(self) -> bool:
        """Check if all tasks are done (completed or failed)."""
        return (
            self._queue.qsize() == 0
            and len(self._pending) == 0
            and self._total_enqueued > 0
        )

    def get_results(self) -> list[BenchmarkResult]:
        """Get all completed results."""
        return list(self._completed.values())

    def get_failed_tasks(self) -> list[tuple[WorkItem, str]]:
        """Get all permanently failed tasks."""
        return list(self._failed.values())
