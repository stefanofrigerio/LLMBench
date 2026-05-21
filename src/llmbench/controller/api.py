"""
FastAPI controller server for distributed LLMBench.

Provides REST API and WebSocket endpoints for worker coordination,
task dispatch, and real-time dashboard updates.
"""

import asyncio
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .task_queue import TaskQueue, WorkItem
from .worker_registry import WorkerRegistry, WorkerInfo
from ..cube import Capability, BenchmarkResult, BenchmarkPoint
from ..models.base import ModelConfig
from ..capabilities.base import TestCase
from ..storage.sqlite import SQLiteStorage


# Pydantic models for API requests/responses
class WorkerRegisterRequest(BaseModel):
    worker_id: str
    ip_address: str
    models_available: List[str]
    metadata: Optional[dict] = None


class HeartbeatRequest(BaseModel):
    worker_id: str


class TaskResultRequest(BaseModel):
    worker_id: str
    success: bool
    result: Optional[dict] = None  # BenchmarkResult as dict
    error: Optional[str] = None


class DispatchRequest(BaseModel):
    run_id: str
    models: List[dict]  # List of ModelConfig dicts
    capabilities: List[str]  # List of capability names
    complexity_range: tuple[int, int] = (1, 5)


class RecommendRequest(BaseModel):
    capability: str
    complexity: int
    sensitivity: int  # 1-5: business context — maps to min score threshold at query time


class ProvisionConfig(BaseModel):
    project_id: str
    run_id: str
    tailscale_auth_key: str          # reusable ephemeral key from tailscale admin
    controller_url: str              # http://<tailscale-ip>:8000
    machine_type: str = "n1-standard-4"
    worker_count: int = 1
    spot: bool = True
    gpu_type: str = ""
    gpu_count: int = 1
    models_to_pull: List[str] = ["deepseek-coder:6.7b", "qwen2.5-coder:7b"]
    region: str = "europe-west1"
    zone: str = "europe-west1-b"


class StatusResponse(BaseModel):
    queue_status: dict
    worker_stats: dict
    active_workers: int
    run_id: Optional[str] = None


# Global singletons (initialized in create_app)
task_queue: Optional[TaskQueue] = None
worker_registry: Optional[WorkerRegistry] = None
storage: Optional[SQLiteStorage] = None
websocket_connections: List[WebSocket] = []
current_run_id: Optional[str] = None

provision_state: dict = {
    "status": "idle",  # idle | provisioning | ready | destroying | error
    "logs": [],
    "worker_ips": [],
    "error": None,
    "run_id": None,
}


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    global task_queue, worker_registry, storage

    app = FastAPI(
        title="LLMBench Controller",
        description="Distributed benchmark coordination API",
        version="1.0.0",
    )

    # Initialize global components
    task_queue = TaskQueue()
    worker_registry = WorkerRegistry(heartbeat_timeout=60)
    storage = SQLiteStorage("results/benchmarks.db")

    # Start worker monitoring
    @app.on_event("startup")
    async def startup():
        await worker_registry.start_monitoring(check_interval=30)

    @app.on_event("shutdown")
    async def shutdown():
        await worker_registry.stop_monitoring()

    # Health check
    @app.get("/health")
    async def health_check():
        return {"status": "ok", "timestamp": datetime.now().isoformat()}

    # Worker registration
    @app.post("/api/workers/register")
    async def register_worker(req: WorkerRegisterRequest):
        """Register a new worker with the controller."""
        worker = await worker_registry.register(
            worker_id=req.worker_id,
            ip_address=req.ip_address,
            models_available=req.models_available,
            metadata=req.metadata,
        )

        await broadcast_worker_update()

        return {
            "status": "registered",
            "worker_id": worker.worker_id,
            "heartbeat_interval": 30,
        }

    # Worker heartbeat
    @app.post("/api/workers/heartbeat")
    async def worker_heartbeat(req: HeartbeatRequest):
        """Receive heartbeat from worker."""
        success = await worker_registry.heartbeat(req.worker_id)

        if not success:
            raise HTTPException(status_code=404, detail="Worker not registered")

        return {"status": "ok", "timestamp": datetime.now().isoformat()}

    # Get all workers
    @app.get("/api/workers")
    async def list_workers():
        """Get list of all registered workers."""
        workers = worker_registry.get_all_workers()
        return {
            "workers": [
                {
                    "worker_id": w.worker_id,
                    "ip_address": w.ip_address,
                    "status": w.status,
                    "current_task_id": w.current_task_id,
                    "last_heartbeat": w.last_heartbeat.isoformat(),
                    "models_available": w.models_available,
                    "tasks_completed": w.tasks_completed,
                    "tasks_failed": w.tasks_failed,
                }
                for w in workers
            ],
            "stats": worker_registry.get_stats(),
        }

    # Task polling by workers
    @app.get("/api/tasks/next")
    async def get_next_task(worker_id: str):
        """Worker polls for next available task."""
        # Verify worker is registered
        worker = worker_registry.get_worker(worker_id)
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not registered")

        # Try to get a task (5 second timeout)
        work_item = await task_queue.dequeue(worker_id, timeout=5.0)

        if work_item is None:
            return {"task": None}  # No work available

        # Mark worker as busy
        await worker_registry.assign_task(worker_id, work_item.task_id)
        await broadcast_status_update()

        return {
            "task": {
                "task_id": work_item.task_id,
                "model_config": {
                    "name": work_item.model_config.name,
                    "provider": work_item.model_config.provider,
                    "model_id": work_item.model_config.model_id,
                    "temperature": work_item.model_config.temperature,
                    "max_tokens": work_item.model_config.max_tokens,
                },
                "capability": work_item.capability.value,
                "test_case": {
                    "input_data": work_item.test_case.input_data,
                    "expected_output": work_item.test_case.expected_output,
                    "complexity": work_item.test_case.complexity,
                },
            }
        }

    # Task result submission
    @app.post("/api/tasks/{task_id}/result")
    async def submit_task_result(task_id: str, req: TaskResultRequest):
        """Worker submits completed task result."""
        if req.success and req.result:
            # Parse result dict into BenchmarkResult
            result_data = req.result
            point = BenchmarkPoint(
                capability=Capability(result_data["capability"]),
                complexity=result_data["complexity"],
            )

            result = BenchmarkResult(
                point=point,
                model_name=result_data["model_name"],
                score=result_data["score"],
                latency_ms=result_data["latency_ms"],
                cost_estimate=result_data.get("cost_estimate", 0.0),
                error=result_data.get("error"),
                raw_output=result_data.get("raw_output"),
                metadata=result_data.get("metadata"),
            )

            await task_queue.complete(task_id, result)

            # Save to database
            if current_run_id:
                # Add run_id and worker_id to metadata
                if result.metadata is None:
                    result.metadata = {}
                result.metadata["run_id"] = current_run_id
                result.metadata["worker_id"] = req.worker_id

            storage.save_result(result)

            await worker_registry.complete_task(req.worker_id, success=True)
        else:
            # Task failed
            error_msg = req.error or "Unknown error"
            await task_queue.fail(task_id, error_msg, max_retries=3)
            await worker_registry.complete_task(req.worker_id, success=False)

        await broadcast_status_update()

        return {"status": "recorded"}

    # Dispatch new benchmark run
    @app.post("/api/dispatch")
    async def dispatch_benchmark(req: DispatchRequest):
        """
        Dispatch a new benchmark run by populating the task queue.

        This generates all (model, capability, test_case) combinations
        and adds them to the queue for workers to process.
        """
        global current_run_id
        current_run_id = req.run_id

        # Parse model configs
        models = [
            ModelConfig(
                name=m["name"],
                provider=m["provider"],
                model_id=m["model_id"],
                temperature=m.get("temperature", 0.2),
                max_tokens=m.get("max_tokens", 2048),
            )
            for m in req.models
        ]

        # For this MVP, we'll use hardcoded test cases
        # In production, load from capability tests
        from ..capabilities.code_generation import CodeGenerationTest

        capability_tests = {Capability.CODE_GENERATION: CodeGenerationTest()}

        work_items = []

        for model_config in models:
            for cap_name in req.capabilities:
                capability = Capability(cap_name)
                if capability not in capability_tests:
                    continue

                cap_test = capability_tests[capability]
                test_cases = cap_test.get_test_cases()

                # Filter by complexity range
                filtered_cases = [
                    tc
                    for tc in test_cases
                    if req.complexity_range[0] <= tc.complexity <= req.complexity_range[1]
                ]

                for test_case in filtered_cases:
                    work_item = WorkItem.create(
                        model_config=model_config,
                        capability=capability,
                        test_case=test_case,
                    )
                    work_items.append(work_item)

        # Enqueue all work items
        await task_queue.enqueue_batch(work_items)

        # Record run in database
        storage.create_run(
            run_id=req.run_id,
            worker_count=len(worker_registry.get_active_workers()),
            total_tasks=len(work_items),
        )

        await broadcast_status_update()

        return {
            "status": "dispatched",
            "run_id": req.run_id,
            "total_tasks": len(work_items),
            "active_workers": len(worker_registry.get_active_workers()),
        }

    # Get current status
    @app.get("/api/status")
    async def get_status():
        """Get overall system status."""
        return {
            "queue_status": task_queue.get_status(),
            "worker_stats": worker_registry.get_stats(),
            "active_workers": len(worker_registry.get_active_workers()),
            "run_id": current_run_id,
            "timestamp": datetime.now().isoformat(),
        }

    # Query results
    @app.get("/api/results")
    async def get_results(
        run_id: Optional[str] = None,
        capability: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        """Query benchmark results with optional filters."""
        db_results = storage.get_results(capability=capability, model_name=model_name)

        # Supplement with in-memory results not yet persisted
        in_memory = task_queue.get_results()
        in_memory_dicts = [
            {
                "model_name": r.model_name,
                "capability": r.point.capability.value,
                "complexity": r.point.complexity,
                "score": r.score,
                "latency_ms": r.latency_ms,
                "cost_estimate": r.cost_estimate,
                "error": r.error,
            }
            for r in in_memory
            if (capability is None or r.point.capability.value == capability)
            and (model_name is None or r.model_name == model_name)
        ]

        # Merge: db_results first (most recent from DB), then in-memory
        all_results = db_results + in_memory_dicts

        return {
            "results": all_results,
            "count": len(all_results),
        }

    # Model recommendation endpoint
    @app.post("/api/recommend")
    async def recommend_model(req: RecommendRequest):
        """
        Return the best model for a given (capability, complexity, sensitivity) triple.

        Sensitivity is a business-context parameter: it maps to a minimum score
        threshold (1→0.60 … 5→0.95). Returns None if no open-source model qualifies
        — the caller should fall back to a proprietary model.
        """
        recommendation = storage.recommend_model(
            capability=req.capability,
            complexity=req.complexity,
            sensitivity=req.sensitivity,
        )

        if recommendation is None:
            return {
                "recommendation": None,
                "message": (
                    f"No open-source model meets sensitivity={req.sensitivity} "
                    f"(min_score={req.sensitivity * 0.0875 + 0.5125:.2f}) "
                    f"for {req.capability} at complexity={req.complexity}. "
                    "Use a proprietary model."
                ),
            }

        return {"recommendation": recommendation}

    # All scores for a (capability, complexity) point
    @app.get("/api/scores")
    async def get_scores(capability: str, complexity: int):
        """Return performance array for all models at a benchmark point."""
        scores = storage.get_all_scores(capability=capability, complexity=complexity)
        return {"capability": capability, "complexity": complexity, "models": scores}

    # Provision workers via Terraform
    @app.post("/api/provision")
    async def provision_workers(config: ProvisionConfig):
        """Provision cloud workers via Terraform (GCP)."""
        global provision_state

        if provision_state["status"] in ("provisioning", "destroying"):
            raise HTTPException(
                status_code=409,
                detail=f"Provision operation already in progress: {provision_state['status']}",
            )

        provision_state = {
            "status": "provisioning",
            "logs": [],
            "worker_ips": [],
            "error": None,
            "run_id": config.run_id,
        }

        await broadcast_provision_update()

        # Run Terraform in background
        asyncio.create_task(_run_terraform_provision(config))

        return {"status": "provisioning", "run_id": config.run_id}

    @app.get("/api/provision/status")
    async def get_provision_status():
        """Return current provisioning state."""
        return provision_state

    @app.post("/api/provision/destroy")
    async def destroy_workers():
        """Destroy provisioned cloud workers via Terraform."""
        global provision_state

        if provision_state["status"] == "idle":
            raise HTTPException(status_code=400, detail="No active provision run to destroy")

        if provision_state["status"] in ("provisioning", "destroying"):
            raise HTTPException(
                status_code=409,
                detail=f"Provision operation already in progress: {provision_state['status']}",
            )

        run_id = provision_state.get("run_id")
        if not run_id:
            raise HTTPException(status_code=400, detail="No run_id found in provision state")

        provision_state["status"] = "destroying"
        provision_state["logs"].append("Starting terraform destroy...")

        await broadcast_provision_update()

        asyncio.create_task(_run_terraform_destroy(run_id))

        return {"status": "destroying", "run_id": run_id}

    # WebSocket for real-time dashboard updates
    @app.websocket("/ws/dashboard")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket connection for real-time updates."""
        await websocket.accept()
        websocket_connections.append(websocket)

        try:
            # Send initial status
            await websocket.send_json(
                {
                    "type": "status",
                    "data": {
                        "queue_status": task_queue.get_status(),
                        "worker_stats": worker_registry.get_stats(),
                        "workers": [
                            {
                                "worker_id": w.worker_id,
                                "status": w.status,
                                "current_task_id": w.current_task_id,
                            }
                            for w in worker_registry.get_all_workers()
                        ],
                    },
                }
            )

            # Keep connection alive and listen for client messages
            while True:
                data = await websocket.receive_text()
                # Client can request refresh
                if data == "refresh":
                    await websocket.send_json(
                        {
                            "type": "status",
                            "data": {
                                "queue_status": task_queue.get_status(),
                                "worker_stats": worker_registry.get_stats(),
                            },
                        }
                    )

        except WebSocketDisconnect:
            websocket_connections.remove(websocket)

    # Mount static files for React frontend (if built)
    frontend_dist = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")

    return app


async def broadcast_status_update():
    """Broadcast status update to all connected WebSocket clients."""
    if not websocket_connections:
        return

    message = {
        "type": "status_update",
        "data": {
            "queue_status": task_queue.get_status(),
            "worker_stats": worker_registry.get_stats(),
            "timestamp": datetime.now().isoformat(),
        },
    }

    # Send to all connections (remove failed ones)
    disconnected = []
    for ws in websocket_connections:
        try:
            await ws.send_json(message)
        except:
            disconnected.append(ws)

    for ws in disconnected:
        websocket_connections.remove(ws)


async def broadcast_worker_update():
    """Broadcast worker list update to dashboard."""
    if not websocket_connections:
        return

    message = {
        "type": "workers_update",
        "data": {
            "workers": [
                {
                    "worker_id": w.worker_id,
                    "status": w.status,
                    "current_task_id": w.current_task_id,
                    "tasks_completed": w.tasks_completed,
                }
                for w in worker_registry.get_all_workers()
            ],
            "timestamp": datetime.now().isoformat(),
        },
    }

    disconnected = []
    for ws in websocket_connections:
        try:
            await ws.send_json(message)
        except:
            disconnected.append(ws)

    for ws in disconnected:
        websocket_connections.remove(ws)


async def broadcast_provision_update():
    """Broadcast provision state update to dashboard."""
    if not websocket_connections:
        return

    message = {
        "type": "provision_update",
        "data": {**provision_state, "timestamp": datetime.now().isoformat()},
    }

    disconnected = []
    for ws in websocket_connections:
        try:
            await ws.send_json(message)
        except:
            disconnected.append(ws)

    for ws in disconnected:
        websocket_connections.remove(ws)


def _terraform_dir() -> Path:
    return Path(__file__).parent.parent.parent.parent / "infrastructure" / "gcp"


async def _run_terraform_provision(config: ProvisionConfig):
    """Background task: write tfvars, run terraform init + apply."""
    global provision_state

    infra_dir = _terraform_dir()

    def _append_log(line: str):
        provision_state["logs"].append(line)
        # Keep last 200 log lines
        if len(provision_state["logs"]) > 200:
            provision_state["logs"] = provision_state["logs"][-200:]

    try:
        # Write tfvars file
        tfvars_path = infra_dir / f"tfvars-{config.run_id}.json"
        tfvars = {
            "project_id": config.project_id,
            "run_id": config.run_id,
            "machine_type": config.machine_type,
            "worker_count": config.worker_count,
            "spot": config.spot,
            "region": config.region,
            "zone": config.zone,
            "models_to_pull": config.models_to_pull,
            "controller_url": config.controller_url,
            "tailscale_auth_key": config.tailscale_auth_key,
        }
        if config.gpu_type:
            tfvars["gpu_type"] = config.gpu_type
            tfvars["gpu_count"] = config.gpu_count

        infra_dir.mkdir(parents=True, exist_ok=True)
        tfvars_path.write_text(json.dumps(tfvars, indent=2))
        _append_log(f"Wrote tfvars to {tfvars_path}")
        await broadcast_provision_update()

        # terraform init
        _append_log("Running terraform init...")
        await broadcast_provision_update()
        proc = await asyncio.create_subprocess_exec(
            "terraform", "init", "-no-color",
            cwd=str(infra_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        async for line in proc.stdout:
            _append_log(line.decode().rstrip())
        await proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"terraform init failed with code {proc.returncode}")

        # terraform apply
        _append_log("Running terraform apply...")
        await broadcast_provision_update()
        proc = await asyncio.create_subprocess_exec(
            "terraform", "apply", "-auto-approve", "-no-color",
            f"-var-file={tfvars_path}",
            cwd=str(infra_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        async for line in proc.stdout:
            _append_log(line.decode().rstrip())
        await proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"terraform apply failed with code {proc.returncode}")

        # Parse outputs
        _append_log("Fetching terraform outputs...")
        output_proc = await asyncio.create_subprocess_exec(
            "terraform", "output", "-json",
            cwd=str(infra_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await output_proc.communicate()
        worker_ips: list = []
        if output_proc.returncode == 0:
            try:
                tf_output = json.loads(stdout.decode())
                # Expect either "worker_ips" list or "instance_ip" string
                if "worker_ips" in tf_output:
                    raw = tf_output["worker_ips"].get("value", [])
                    worker_ips = raw if isinstance(raw, list) else [raw]
                elif "instance_ip" in tf_output:
                    ip = tf_output["instance_ip"].get("value")
                    if ip:
                        worker_ips = [ip]
            except json.JSONDecodeError:
                _append_log("Warning: could not parse terraform output JSON")

        provision_state["status"] = "ready"
        provision_state["worker_ips"] = worker_ips
        _append_log(f"Provisioning complete. Worker IPs: {worker_ips}")

    except Exception as exc:
        provision_state["status"] = "error"
        provision_state["error"] = str(exc)
        _append_log(f"ERROR: {exc}")

    await broadcast_provision_update()


async def _run_terraform_destroy(run_id: str):
    """Background task: run terraform destroy."""
    global provision_state

    infra_dir = _terraform_dir()
    tfvars_path = infra_dir / f"tfvars-{run_id}.json"

    def _append_log(line: str):
        provision_state["logs"].append(line)
        if len(provision_state["logs"]) > 200:
            provision_state["logs"] = provision_state["logs"][-200:]

    try:
        if not tfvars_path.exists():
            raise FileNotFoundError(f"tfvars file not found: {tfvars_path}")

        proc = await asyncio.create_subprocess_exec(
            "terraform", "destroy", "-auto-approve", "-no-color",
            f"-var-file={tfvars_path}",
            cwd=str(infra_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        async for line in proc.stdout:
            _append_log(line.decode().rstrip())
        await proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"terraform destroy failed with code {proc.returncode}")

        provision_state["status"] = "idle"
        provision_state["worker_ips"] = []
        provision_state["run_id"] = None
        _append_log("Terraform destroy complete.")

    except Exception as exc:
        provision_state["status"] = "error"
        provision_state["error"] = str(exc)
        _append_log(f"ERROR: {exc}")

    await broadcast_provision_update()
