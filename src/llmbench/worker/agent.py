"""
Worker agent for executing distributed benchmark tasks.

The worker agent runs on cloud VMs, polls the controller for work,
executes benchmarks using existing BenchmarkRunner infrastructure,
and reports results back to the controller.
"""

import asyncio
import socket
import time
from typing import Dict, Optional

import aiohttp

from ..cube import Capability, BenchmarkPoint, BenchmarkResult
from ..models.base import ModelConfig, BaseModel
from ..models.ollama import OllamaModel
from ..capabilities.base import CapabilityTest, TestCase
from ..capabilities.code_generation import CodeGenerationTest


class WorkerAgent:
    """
    Worker agent that coordinates with controller to execute benchmarks.

    Lifecycle:
    1. Register with controller at startup
    2. Start heartbeat loop (every 30s)
    3. Start work loop (poll for tasks)
    4. Execute tasks using BenchmarkRunner infrastructure
    5. Report results to controller
    """

    def __init__(
        self,
        controller_url: str,
        worker_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize worker agent.

        Args:
            controller_url: Base URL of controller API (e.g., http://controller:8000)
            worker_id: Unique worker identifier (defaults to hostname)
            api_key: Optional API key for authentication
        """
        self.controller_url = controller_url.rstrip("/")
        self.worker_id = worker_id or socket.gethostname()
        self.api_key = api_key

        # Initialize models
        self.models: Dict[str, BaseModel] = {}
        self.capability_tests: Dict[Capability, CapabilityTest] = {}

        # HTTP session for controller communication
        self.session: Optional[aiohttp.ClientSession] = None

        # State
        self.running = False
        self.current_task_id: Optional[str] = None

    async def initialize(self):
        """Initialize worker resources."""
        # Create HTTP session
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.session = aiohttp.ClientSession(headers=headers)

        # Initialize models (detect available Ollama models)
        await self._initialize_models()

        # Initialize capability tests
        self._initialize_capability_tests()

    async def _initialize_models(self):
        """Discover and initialize available Ollama models."""
        # For MVP, we'll configure a default set of models
        # In production, query Ollama API for available models
        default_models = [
            ("deepseek-coder-6.7b", "deepseek-coder:6.7b"),
            ("qwen2.5-coder-7b", "qwen2.5-coder:7b"),
            ("codellama-7b", "codellama:7b"),
        ]

        for name, model_id in default_models:
            try:
                model = OllamaModel(
                    ModelConfig(
                        name=name,
                        provider="ollama",
                        model_id=model_id,
                        temperature=0.2,
                    )
                )

                # Check if model is available
                if await model.health_check():
                    self.models[name] = model
                    print(f"✅ Model available: {name}")
                else:
                    print(f"⚠️  Model not available: {name}")

            except Exception as e:
                print(f"❌ Failed to initialize model {name}: {e}")

    def _initialize_capability_tests(self):
        """Initialize capability test runners."""
        self.capability_tests = {
            Capability.CODE_GENERATION: CodeGenerationTest(),
            # Add more capability tests as they're implemented
        }

    async def start(self):
        """Start the worker agent (main entry point)."""
        await self.initialize()

        if not self.models:
            print("❌ No models available - cannot start worker")
            return

        # Register with controller
        if not await self.register():
            print("❌ Failed to register with controller")
            return

        print(f"✅ Worker {self.worker_id} started")
        print(f"📡 Controller: {self.controller_url}")
        print(f"🤖 Models: {', '.join(self.models.keys())}")

        self.running = True

        try:
            # Run heartbeat and work loops concurrently
            await asyncio.gather(
                self._heartbeat_loop(),
                self._work_loop(),
            )
        except KeyboardInterrupt:
            print("\n⚠️  Shutting down...")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Clean up resources."""
        self.running = False
        if self.session:
            await self.session.close()

    async def register(self) -> bool:
        """Register worker with controller."""
        try:
            url = f"{self.controller_url}/api/workers/register"
            payload = {
                "worker_id": self.worker_id,
                "ip_address": self._get_local_ip(),
                "models_available": list(self.models.keys()),
                "metadata": {
                    "capabilities": [c.value for c in self.capability_tests.keys()],
                },
            }

            async with self.session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✅ Registered with controller: {data}")
                    return True
                else:
                    error = await resp.text()
                    print(f"❌ Registration failed: {error}")
                    return False

        except Exception as e:
            print(f"❌ Registration error: {e}")
            return False

    async def _heartbeat_loop(self):
        """Send periodic heartbeat to controller."""
        while self.running:
            try:
                await asyncio.sleep(30)  # Every 30 seconds

                url = f"{self.controller_url}/api/workers/heartbeat"
                payload = {"worker_id": self.worker_id}

                async with self.session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        print(f"⚠️  Heartbeat failed: {resp.status}")

            except Exception as e:
                print(f"⚠️  Heartbeat error: {e}")

    async def _work_loop(self):
        """Main work loop - poll for tasks and execute them."""
        while self.running:
            try:
                # Poll for next task
                task = await self._poll_task()

                if task is None:
                    # No work available, wait before polling again
                    await asyncio.sleep(2)
                    continue

                # Execute task
                result = await self._execute_task(task)

                # Submit result
                await self._submit_result(task["task_id"], result)

            except Exception as e:
                print(f"❌ Work loop error: {e}")
                # Report task failure if we have a current task
                if self.current_task_id:
                    await self._submit_error(self.current_task_id, str(e))
                    self.current_task_id = None

                await asyncio.sleep(5)  # Back off on error

    async def _poll_task(self) -> Optional[dict]:
        """Poll controller for next available task."""
        try:
            url = f"{self.controller_url}/api/tasks/next"
            params = {"worker_id": self.worker_id}

            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    task = data.get("task")

                    if task:
                        self.current_task_id = task["task_id"]
                        print(f"📥 Received task: {task['task_id'][:8]}... "
                              f"({task['capability']} / {task['model_config']['name']})")
                        return task

                    return None  # No work available

                else:
                    print(f"⚠️  Task poll failed: {resp.status}")
                    return None

        except Exception as e:
            print(f"⚠️  Poll error: {e}")
            return None

    async def _execute_task(self, task: dict) -> Optional[BenchmarkResult]:
        """Execute a benchmark task."""
        try:
            # Parse task components
            model_config_data = task["model_config"]
            model_config = ModelConfig(
                name=model_config_data["name"],
                provider=model_config_data["provider"],
                model_id=model_config_data["model_id"],
                temperature=model_config_data.get("temperature", 0.2),
                max_tokens=model_config_data.get("max_tokens", 2048),
            )

            capability = Capability(task["capability"])

            test_case_data = task["test_case"]
            test_case = TestCase(
                input_data=test_case_data["input_data"],
                expected_output=test_case_data["expected_output"],
                complexity=test_case_data["complexity"],
                sensitivity=test_case_data["sensitivity"],
            )

            # Get model and capability test
            model = self.models.get(model_config.name)
            if not model:
                raise ValueError(f"Model {model_config.name} not available on this worker")

            capability_test = self.capability_tests.get(capability)
            if not capability_test:
                raise ValueError(f"Capability {capability.value} not available on this worker")

            # Execute benchmark (similar to BenchmarkRunner.run_single_test)
            print(f"⚙️  Executing: {capability.value} / complexity={test_case.complexity}")

            start_time = time.time()

            # Build prompt
            prompt = capability_test.build_prompt(test_case)

            # Generate output
            output = await model.generate(prompt)

            # Measure latency
            latency_ms = (time.time() - start_time) * 1000

            # Evaluate result
            score = capability_test.evaluate(output, test_case.expected_output, test_case)

            # Create result
            point = BenchmarkPoint(
                capability=capability,
                complexity=test_case.complexity,
                sensitivity=test_case.sensitivity,
            )

            result = BenchmarkResult(
                point=point,
                model_name=model_config.name,
                score=score,
                latency_ms=latency_ms,
                cost_estimate=0.0,  # Free for Ollama
                raw_output=output,
            )

            print(f"✅ Completed: score={score:.2f}, latency={latency_ms:.0f}ms")

            return result

        except Exception as e:
            print(f"❌ Task execution failed: {e}")
            raise

    async def _submit_result(self, task_id: str, result: Optional[BenchmarkResult]):
        """Submit task result to controller."""
        try:
            url = f"{self.controller_url}/api/tasks/{task_id}/result"

            if result:
                payload = {
                    "worker_id": self.worker_id,
                    "success": True,
                    "result": {
                        "capability": result.point.capability.value,
                        "complexity": result.point.complexity,
                        "sensitivity": result.point.sensitivity,
                        "model_name": result.model_name,
                        "score": result.score,
                        "latency_ms": result.latency_ms,
                        "cost_estimate": result.cost_estimate,
                        "raw_output": result.raw_output,
                        "error": result.error,
                        "metadata": result.metadata,
                    },
                }
            else:
                payload = {
                    "worker_id": self.worker_id,
                    "success": False,
                    "error": "Task execution returned no result",
                }

            async with self.session.post(url, json=payload) as resp:
                if resp.status == 200:
                    print(f"📤 Result submitted for {task_id[:8]}...")
                else:
                    print(f"⚠️  Result submission failed: {resp.status}")

            self.current_task_id = None

        except Exception as e:
            print(f"❌ Result submission error: {e}")

    async def _submit_error(self, task_id: str, error: str):
        """Submit task error to controller."""
        try:
            url = f"{self.controller_url}/api/tasks/{task_id}/result"
            payload = {
                "worker_id": self.worker_id,
                "success": False,
                "error": error,
            }

            async with self.session.post(url, json=payload) as resp:
                if resp.status != 200:
                    print(f"⚠️  Error submission failed: {resp.status}")

        except Exception as e:
            print(f"❌ Error submission failed: {e}")

    def _get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            # Create a socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
