"""
Distributed orchestrator for managing multiple cloud workers.

Coordinates infrastructure provisioning, benchmark dispatch,
and result collection across multiple cloud VMs.
"""

import asyncio
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import aiohttp

from ..cloud import CloudConfig


class DistributedOrchestrator:
    """
    Orchestrate distributed benchmarks across multiple cloud workers.

    Responsibilities:
    - Provision N cloud VMs with Terraform
    - Start local controller server
    - Wait for workers to register
    - Dispatch benchmark tasks
    - Monitor completion
    - Cleanup infrastructure
    """

    def __init__(
        self,
        config: CloudConfig,
        worker_count: int,
        project_root: Path,
        controller_port: int = 8000,
    ):
        self.config = config
        self.worker_count = worker_count
        self.project_root = project_root
        self.controller_port = controller_port

        # Generate unique run ID
        self.run_id = f"run-{int(time.time())}"

        # Controller URL (accessible from workers)
        self.controller_url = self._get_controller_url()

        # Infrastructure directory
        self.tf_dir = project_root / "infrastructure" / config.provider

        # State
        self.worker_ips: List[str] = []
        self.controller_task: Optional[asyncio.Task] = None

    def _get_controller_url(self) -> str:
        """
        Get controller URL accessible from cloud workers.

        For local testing, you may need to use:
        - ngrok/Cloudflare Tunnel for public endpoint
        - Tailscale for VPN mesh
        - Public IP with firewall rules
        """
        # For MVP, assume controller has public IP or tunnel
        # In production, get actual public IP or tunnel URL
        import socket

        hostname = socket.gethostname()
        # This is simplified - in production use actual public IP or tunnel
        return f"http://localhost:{self.controller_port}"

    async def start_controller(self):
        """Start the controller server in background."""
        from .api import create_app
        import uvicorn

        print(f"🎛️  Starting controller on port {self.controller_port}")

        app = create_app()

        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=self.controller_port,
            log_level="warning"  # Reduce noise
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def provision_workers(self) -> List[str]:
        """
        Provision worker infrastructure using Terraform.

        Returns:
            List of worker IP addresses
        """
        print(f"📦 Provisioning {self.worker_count} workers...")

        # Generate tfvars file
        tfvars = {
            "run_id": self.run_id,
            "worker_count": self.worker_count,
            "controller_url": self.controller_url,
            "region": self.config.region,
            "machine_type": self.config.machine_type,
            "use_spot": self.config.use_spot,
        }

        # Provider-specific vars
        if self.config.provider == "gcp":
            tfvars["project_id"] = self.config.project_id

        if self.config.gpu_type:
            tfvars["gpu_type"] = self.config.gpu_type

        if self.config.models_to_pull:
            tfvars["models_to_pull"] = self.config.models_to_pull

        tfvars_file = self.tf_dir / f"{self.run_id}.tfvars.json"
        tfvars_file.write_text(json.dumps(tfvars, indent=2))

        # Run terraform
        try:
            # Init
            subprocess.run(
                ["terraform", "init"],
                cwd=self.tf_dir,
                check=True,
                capture_output=True
            )

            # Apply
            result = subprocess.run(
                ["terraform", "apply", "-auto-approve", f"-var-file={tfvars_file.name}"],
                cwd=self.tf_dir,
                check=True,
                capture_output=True,
                text=True
            )

            # Get outputs
            output_result = subprocess.run(
                ["terraform", "output", "-json"],
                cwd=self.tf_dir,
                check=True,
                capture_output=True,
                text=True
            )

            outputs = json.loads(output_result.stdout)

            # Extract worker IPs
            if "worker_ips" in outputs:
                self.worker_ips = outputs["worker_ips"]["value"]
            else:
                # Single worker (legacy)
                self.worker_ips = [outputs["instance_ip"]["value"]]

            print(f"✅ Workers provisioned: {', '.join(self.worker_ips)}")
            return self.worker_ips

        except subprocess.CalledProcessError as e:
            print(f"❌ Terraform failed: {e.stderr if e.stderr else e}")
            raise

    async def wait_for_workers(self, timeout: int = 600):
        """
        Wait for workers to register with controller.

        Args:
            timeout: Maximum seconds to wait
        """
        print(f"⏳ Waiting for {self.worker_count} workers to register...")

        start_time = time.time()
        last_count = 0

        async with aiohttp.ClientSession() as session:
            while time.time() - start_time < timeout:
                try:
                    url = f"http://localhost:{self.controller_port}/api/workers"
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            workers = data.get("workers", [])
                            active_count = len([w for w in workers if w["status"] != "offline"])

                            if active_count != last_count:
                                print(f"   {active_count}/{self.worker_count} workers registered")
                                last_count = active_count

                            if active_count >= self.worker_count:
                                print(f"✅ All workers online!")
                                return

                except Exception as e:
                    pass  # Controller might not be ready yet

                await asyncio.sleep(5)

        raise TimeoutError(f"Workers did not register within {timeout}s")

    async def dispatch_benchmark(
        self,
        models: Optional[List[dict]] = None,
        capabilities: Optional[List[str]] = None,
    ):
        """
        Dispatch benchmark tasks to the queue.

        Args:
            models: List of model configs (defaults to standard set)
            capabilities: List of capability names (defaults to ['code_generation'])
        """
        if models is None:
            models = [
                {
                    "name": "deepseek-coder-6.7b",
                    "provider": "ollama",
                    "model_id": "deepseek-coder:6.7b",
                    "temperature": 0.2,
                },
                {
                    "name": "qwen2.5-coder-7b",
                    "provider": "ollama",
                    "model_id": "qwen2.5-coder:7b",
                    "temperature": 0.2,
                },
            ]

        if capabilities is None:
            capabilities = ["code_generation"]

        payload = {
            "run_id": self.run_id,
            "models": models,
            "capabilities": capabilities,
            "complexity_range": [1, 5],
            "sensitivity_range": [1, 5],
        }

        async with aiohttp.ClientSession() as session:
            url = f"http://localhost:{self.controller_port}/api/dispatch"
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✅ Dispatched {data['total_tasks']} tasks")
                else:
                    error = await resp.text()
                    raise Exception(f"Dispatch failed: {error}")

    async def wait_for_completion(self, poll_interval: int = 10):
        """
        Monitor benchmark progress until completion.

        Args:
            poll_interval: Seconds between status checks
        """
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    url = f"http://localhost:{self.controller_port}/api/status"
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            queue = data.get("queue_status", {})

                            total = queue.get("total_enqueued", 0)
                            completed = queue.get("completed", 0)
                            failed = queue.get("failed", 0)
                            pending = queue.get("pending", 0)
                            queued = queue.get("queued", 0)

                            progress = (completed / total * 100) if total > 0 else 0

                            print(f"   Progress: {completed}/{total} ({progress:.1f}%) | "
                                  f"Running: {pending} | Queued: {queued} | Failed: {failed}")

                            # Check if complete
                            if total > 0 and (completed + failed) >= total and pending == 0:
                                print(f"\n✅ Benchmark complete!")
                                print(f"   Completed: {completed}")
                                print(f"   Failed: {failed}")
                                return

                except Exception as e:
                    print(f"⚠️  Status check error: {e}")

                await asyncio.sleep(poll_interval)

    async def destroy_workers(self):
        """Destroy worker infrastructure."""
        print(f"🧹 Destroying workers...")

        tfvars_file = self.tf_dir / f"{self.run_id}.tfvars.json"

        try:
            subprocess.run(
                ["terraform", "destroy", "-auto-approve", f"-var-file={tfvars_file.name}"],
                cwd=self.tf_dir,
                check=True,
                capture_output=True
            )

            print(f"✅ Workers destroyed")

            # Clean up tfvars file
            if tfvars_file.exists():
                tfvars_file.unlink()

        except subprocess.CalledProcessError as e:
            print(f"❌ Destroy failed: {e.stderr if e.stderr else e}")
            raise
