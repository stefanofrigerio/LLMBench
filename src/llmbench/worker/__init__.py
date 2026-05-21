"""
Worker components for distributed LLMBench system.

Workers poll for tasks from the controller, execute benchmarks,
and report results back.
"""

from .agent import WorkerAgent

__all__ = ["WorkerAgent"]
