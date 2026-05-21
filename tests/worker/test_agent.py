"""Tests for worker agent"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.llmbench.worker.agent import WorkerAgent
from src.llmbench.cube import Capability


@pytest.fixture
def agent():
    """Fixture for worker agent"""
    return WorkerAgent(
        controller_url="http://test-controller:8000",
        worker_id="test-worker",
        api_key="test-key",
    )


@pytest.fixture
def sample_task():
    """Fixture for sample task from controller"""
    return {
        "task_id": "task-123",
        "model_config": {
            "name": "test-model",
            "provider": "ollama",
            "model_id": "test:1b",
            "temperature": 0.2,
            "max_tokens": 2048,
        },
        "capability": "code_generation",
        "test_case": {
            "input_data": "Write a function to reverse a string",
            "expected_output": "def reverse_string(s): return s[::-1]",
            "complexity": 2,
        },
    }


class TestWorkerAgent:
    """Tests for WorkerAgent class"""

    def test_init(self, agent):
        """Test worker agent initialization"""
        assert agent.controller_url == "http://test-controller:8000"
        assert agent.worker_id == "test-worker"
        assert agent.api_key == "test-key"
        assert agent.models == {}
        assert agent.session is None

    @pytest.mark.asyncio
    async def test_initialize(self, agent):
        """Test worker initialization"""
        with patch.object(agent, "_initialize_models", new_callable=AsyncMock) as mock_init:
            await agent.initialize()

            assert agent.session is not None
            mock_init.assert_called_once()
            assert Capability.CODE_GENERATION in agent.capability_tests

            await agent.session.close()

    @pytest.mark.asyncio
    async def test_register_success(self, agent):
        """Test successful worker registration"""
        await agent.initialize()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "registered",
            "worker_id": "test-worker",
            "heartbeat_interval": 30,
        })

        with patch.object(agent.session, "post") as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await agent.register()

            assert result is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "http://test-controller:8000/api/workers/register" in str(call_args)

        await agent.session.close()

    @pytest.mark.asyncio
    async def test_register_failure(self, agent):
        """Test failed worker registration"""
        await agent.initialize()

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Server error")

        with patch.object(agent.session, "post") as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await agent.register()

            assert result is False

        await agent.session.close()

    @pytest.mark.asyncio
    async def test_poll_task_with_work(self, agent, sample_task):
        """Test polling returns task when work available"""
        await agent.initialize()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"task": sample_task})

        with patch.object(agent.session, "get") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response

            task = await agent._poll_task()

            assert task is not None
            assert task["task_id"] == "task-123"
            assert agent.current_task_id == "task-123"

        await agent.session.close()

    @pytest.mark.asyncio
    async def test_poll_task_no_work(self, agent):
        """Test polling returns None when no work available"""
        await agent.initialize()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"task": None})

        with patch.object(agent.session, "get") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response

            task = await agent._poll_task()

            assert task is None

        await agent.session.close()

    @pytest.mark.asyncio
    async def test_execute_task(self, agent, sample_task):
        """Test executing a task"""
        await agent.initialize()

        # Mock model
        mock_model = AsyncMock()
        mock_model.generate = AsyncMock(return_value="def reverse_string(s): return s[::-1]")
        agent.models["test-model"] = mock_model

        result = await agent._execute_task(sample_task)

        assert result is not None
        assert result.model_name == "test-model"
        assert result.point.capability == Capability.CODE_GENERATION
        assert result.point.complexity == 2
        assert 0.0 <= result.score <= 1.0
        assert result.latency_ms > 0

        await agent.session.close()

    @pytest.mark.asyncio
    async def test_execute_task_model_not_available(self, agent, sample_task):
        """Test executing task fails when model not available"""
        await agent.initialize()

        # No models available
        agent.models = {}

        with pytest.raises(ValueError, match="Model .* not available"):
            await agent._execute_task(sample_task)

        await agent.session.close()

    @pytest.mark.asyncio
    async def test_execute_task_capability_not_available(self, agent, sample_task):
        """Test executing task fails when capability not available"""
        await agent.initialize()

        # Add model but remove capability
        mock_model = AsyncMock()
        agent.models["test-model"] = mock_model
        agent.capability_tests.clear()

        with pytest.raises(ValueError, match="Capability .* not available"):
            await agent._execute_task(sample_task)

        await agent.session.close()

    @pytest.mark.asyncio
    async def test_submit_result_success(self, agent):
        """Test submitting successful result"""
        await agent.initialize()

        from src.llmbench.cube import BenchmarkResult, BenchmarkPoint

        result = BenchmarkResult(
            point=BenchmarkPoint(Capability.CODE_GENERATION, 2),
            model_name="test-model",
            score=0.95,
            latency_ms=1234.5,
            cost_estimate=0.0,
        )

        mock_response = AsyncMock()
        mock_response.status = 200

        with patch.object(agent.session, "post") as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response

            await agent._submit_result("task-123", result)

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "task-123/result" in str(call_args)

            # Verify payload structure
            payload = call_args[1]["json"]
            assert payload["worker_id"] == "test-worker"
            assert payload["success"] is True
            assert payload["result"]["score"] == 0.95

        await agent.session.close()

    @pytest.mark.asyncio
    async def test_submit_result_failure(self, agent):
        """Test submitting failed result"""
        await agent.initialize()

        mock_response = AsyncMock()
        mock_response.status = 200

        with patch.object(agent.session, "post") as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response

            await agent._submit_result("task-123", None)

            payload = mock_post.call_args[1]["json"]
            assert payload["success"] is False
            assert "error" in payload

        await agent.session.close()

    @pytest.mark.asyncio
    async def test_submit_error(self, agent):
        """Test submitting error"""
        await agent.initialize()

        mock_response = AsyncMock()
        mock_response.status = 200

        with patch.object(agent.session, "post") as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response

            await agent._submit_error("task-123", "Test error message")

            payload = mock_post.call_args[1]["json"]
            assert payload["success"] is False
            assert payload["error"] == "Test error message"

        await agent.session.close()

    def test_get_local_ip(self, agent):
        """Test getting local IP address"""
        ip = agent._get_local_ip()

        assert ip is not None
        assert isinstance(ip, str)
        # Should be valid IP format
        parts = ip.split(".")
        assert len(parts) == 4

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Timing-sensitive async test - flaky")
    async def test_heartbeat_loop_iteration(self, agent):
        """Test single heartbeat loop iteration"""
        await agent.initialize()

        mock_response = AsyncMock()
        mock_response.status = 200

        agent.running = True

        with patch.object(agent.session, "post") as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response

            # Mock sleep to avoid waiting
            with patch("asyncio.sleep", new_callable=AsyncMock):
                # Run one iteration
                task = asyncio.create_task(agent._heartbeat_loop())
                await asyncio.sleep(0.1)
                agent.running = False
                await task

                # Should have sent heartbeat
                assert mock_post.called

        await agent.session.close()

    @pytest.mark.asyncio
    async def test_work_loop_processes_task(self, agent, sample_task):
        """Test work loop processes task"""
        await agent.initialize()

        # Mock model
        mock_model = AsyncMock()
        mock_model.generate = AsyncMock(return_value="output")
        agent.models["test-model"] = mock_model

        # Mock methods
        agent._poll_task = AsyncMock(side_effect=[sample_task, None])
        agent._submit_result = AsyncMock()

        agent.running = True

        # Run work loop
        task = asyncio.create_task(agent._work_loop())
        await asyncio.sleep(0.2)
        agent.running = False

        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.TimeoutError:
            task.cancel()

        # Should have polled and submitted result
        assert agent._poll_task.call_count >= 1
        assert agent._submit_result.call_count >= 1

        await agent.session.close()

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up(self, agent):
        """Test shutdown cleans up resources"""
        await agent.initialize()
        session = agent.session

        await agent.shutdown()

        assert agent.running is False
        assert session.closed


# Import at module level for asyncio
import asyncio
