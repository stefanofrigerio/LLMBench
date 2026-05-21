# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Workflow

**IMPORTANT: After every major edit, push to GitHub:**
```bash
git add -A
git commit -m "Descriptive message

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
git push origin master
```

**CRITICAL: Unit tests are mandatory:**
- Write unit tests for all new code
- Minimum test coverage: **90%**
- Run tests before pushing: `poetry run pytest tests/ --cov=src/llmbench --cov-report=term-missing`
- Tests must pass before merging

**Poetry & Virtual Environments:**
- This project uses **Poetry** for dependency management
- Poetry automatically creates and manages a virtual environment
- All commands should run via `poetry run` or inside the activated venv

## Project Overview

LLMBench is a 3D cube benchmarking system for evaluating open-source LLMs across three dimensions:
- **Capability** (what to do): code_generation, unit_test_writing, ocr, reasoning, etc.
- **Complexity** (how hard): 1-5 scale from trivial to expert
- **Sensitivity** (how critical): 1-5 scale from low to critical impact

The system runs in three modes:
- **Local Mode**: Uses Ollama on your machine (single-threaded)
- **Cloud Mode (Legacy)**: Single cloud VM with Terraform
- **Distributed Mode**: Multiple cloud workers coordinated by local controller (NEW!)

## Common Commands

### Running Benchmarks

**Local Mode:**
```bash
# Run benchmark using examples script
python examples/run_benchmark.py

# Results stored in results/benchmarks.db
```

**Distributed Mode (Recommended for Production):**
```bash
# Start controller locally
llmbench controller start --port 8000

# Dispatch benchmark to cloud workers (provisions, runs, destroys)
llmbench dispatch --provider gcp --project YOUR_PROJECT_ID --workers 3

# Monitor progress
llmbench status --run-id run-TIMESTAMP

# Cleanup workers manually
llmbench cleanup --provider gcp --run-id run-TIMESTAMP
```

**Cloud Mode (Legacy - Single VM):**
```bash
# GCP with GPU
llmbench run --provider gcp --project YOUR_PROJECT_ID --gpu nvidia-tesla-t4

# AWS with spot instance
llmbench run --provider aws --region us-east-1 --machine g4dn.xlarge --spot

# Keep instance after benchmark (for debugging)
llmbench run --provider gcp --project YOUR_PROJECT_ID --keep

# Provision only (no benchmark)
llmbench provision --provider gcp --project YOUR_PROJECT_ID

# Destroy infrastructure
llmbench destroy --provider gcp --run-id run-TIMESTAMP
```

**Manual Worker (for testing):**
```bash
# Start a worker agent pointing to controller
llmbench worker --controller-url http://CONTROLLER_IP:8000 --worker-id worker-test
```

### Development

```bash
# Initial setup (one-time)
./setup-venv.sh

# Or manually with Poetry
poetry install --with dev

# Activate virtual environment
source .venv/bin/activate

# Run tests with coverage (MUST be ≥90% before pushing)
poetry run pytest tests/ --cov=src/llmbench --cov-report=term-missing --cov-fail-under=90

# Run specific test file
poetry run pytest tests/controller/test_task_queue.py -v

# Format code (Black, line length 100)
poetry run black src/

# Type checking
poetry run mypy src/

# Run CLI commands
poetry run llmbench --help
poetry run llmbench controller start --port 8000
```

**Poetry Commands:**
```bash
# Add a new dependency
poetry add <package>

# Add a dev dependency
poetry add --group dev <package>

# Update dependencies
poetry update

# Show installed packages
poetry show

# Export requirements.txt (if needed for Docker)
poetry export -f requirements.txt --output requirements.txt --without-hashes
```

**Test Coverage Requirements:**
- **Minimum coverage: 90%** for all modules
- Test both success and failure paths
- Mock external dependencies (HTTP calls, subprocess, file I/O)
- Use `pytest-asyncio` for async tests
- Use `pytest-cov` to verify coverage before commit

### Testing with Ollama

```bash
# Pull models for local testing
ollama pull deepseek-coder:6.7b
ollama pull qwen2.5-coder:7b
ollama pull codellama:7b

# Check Ollama is running
curl http://localhost:11434/api/tags
```

## Architecture

### Distributed System (New!)

LLMBench now supports distributed benchmarking across multiple cloud workers:

```
┌─────────────────────────────────────────────────────────────┐
│                    Local Controller                         │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │  FastAPI Server│  │   Task Queue   │  │  SQLite DB   │  │
│  │  REST + WS API │  │  (In-memory)   │  │  (Results)   │  │
│  └────────┬───────┘  └───────┬────────┘  └──────┬───────┘  │
│           └──────────────────┴───────────────────┘          │
└─────────────────────────────────────────────────────────────┘
                           ▲ Push results via REST API
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼───────┐  ┌───────▼───────┐  ┌──────▼────────┐
│  Cloud Worker │  │  Cloud Worker │  │ Cloud Worker  │
│   (GCP/AWS)   │  │   (GCP/AWS)   │  │  (GCP/AWS)    │
│               │  │               │  │               │
│ ┌───────────┐ │  │ ┌───────────┐ │  │ ┌───────────┐ │
│ │  Ollama   │ │  │ │  Ollama   │ │  │ │  Ollama   │ │
│ │  Models   │ │  │ │  Models   │ │  │ │  Models   │ │
│ └───────────┘ │  │ └───────────┘ │  │ └───────────┘ │
│               │  │               │  │               │
│ Worker Agent  │  │ Worker Agent  │  │ Worker Agent  │
│ (Python Loop) │  │ (Python Loop) │  │ (Python Loop) │
└───────────────┘  └───────────────┘  └───────────────┘
```

**How It Works:**
1. **Controller** runs locally (FastAPI server), exposes REST API and WebSocket
2. **Task Queue** holds all benchmark work items (model + capability + test case)
3. **Workers** are cloud VMs provisioned via Terraform
4. **Worker Agents** auto-start on boot (systemd), poll controller for tasks
5. **Results** pushed back to controller, saved to SQLite

**Key Components:**
- `src/llmbench/controller/api.py` - FastAPI server with endpoints
- `src/llmbench/controller/task_queue.py` - Async task queue with retry logic
- `src/llmbench/controller/worker_registry.py` - Worker health tracking
- `src/llmbench/controller/orchestrator.py` - Provisions and coordinates workers
- `src/llmbench/worker/agent.py` - Worker agent that polls and executes tasks

**API Endpoints:**
- `POST /api/workers/register` - Worker registration
- `POST /api/workers/heartbeat` - Keep-alive (every 30s)
- `GET /api/tasks/next` - Poll for next task
- `POST /api/tasks/{task_id}/result` - Submit result
- `POST /api/dispatch` - Create new benchmark run
- `GET /api/status` - Overall system status
- `GET /api/workers` - List active workers
- `WebSocket /ws/dashboard` - Real-time updates

### Core Data Model

The **BenchmarkPoint** represents a single cell in the 3D cube:
```python
BenchmarkPoint(
    capability=Capability.CODE_GENERATION,
    complexity=3,  # 1-5
    sensitivity=4  # 1-5
)
```

Each point can have multiple **BenchmarkResult** entries (one per model tested) containing score, latency, and cost.

### Component Flow

1. **Capability Tests** (`src/llmbench/capabilities/`) define test cases and evaluation logic
   - Each test returns a list of TestCase objects with varying complexity/sensitivity
   - `evaluate()` method scores model output (0-1 range)
   - `build_prompt()` generates the prompt for the model

2. **Models** (`src/llmbench/models/`) implement the `BaseModel` interface
   - `generate()` takes a prompt and returns output
   - `health_check()` verifies the model is available
   - Currently only OllamaModel is implemented

3. **BenchmarkRunner** (`src/llmbench/runners/benchmark.py`) orchestrates execution
   - Iterates through models × capabilities × test cases
   - Measures latency and evaluates scores
   - Returns list of BenchmarkResult objects

4. **Storage** (`src/llmbench/storage/sqlite.py`) persists results
   - SQLite database at `results/benchmarks.db`
   - Queries for best model by point coordinates
   - Aggregates model performance summaries

5. **CloudOrchestrator** (`src/llmbench/cloud/orchestrator.py`) manages cloud infrastructure
   - Generates Terraform variables from CloudConfig
   - Runs terraform init/apply/destroy via TerraformRunner
   - Uses rsync for code deployment and result fetching
   - Executes benchmark via SSH

### Cloud Infrastructure

**Terraform modules** in `infrastructure/{gcp,aws}/`:
- `main.tf`: VM instance with GPU (optional), cloud-init provisioning
- `variables.tf`: Configuration inputs (machine type, GPU, models, SSH keys)
- `outputs.tf`: Instance IP, run ID

**Provisioning scripts** in `infrastructure/scripts/`:
- `cloud-init.yaml`: Installs Ollama, pulls models, sets up Python environment
- `deploy_benchmark.sh`: Waits for SSH, deploys code, installs dependencies

### Key Design Decisions

**Why async/await?** Model API calls are I/O bound. Using `asyncio` enables parallel test execution across multiple test cases.

**Why SQLite?** Simple, portable, no external dependencies. Results are local by default. Future: add export to BigQuery/S3 for large-scale analysis.

**Why separate local/cloud modes?** Local mode is fast for development. Cloud mode provides reproducible, GPU-accelerated benchmarks at scale.

**Why Terraform?** Infrastructure-as-code makes cloud resources reproducible and destroyable. Each run gets a unique `run_id` to prevent state conflicts.

## Adding New Capabilities

1. Create `src/llmbench/capabilities/your_capability.py`:
```python
from .base import CapabilityTest, TestCase

class YourCapabilityTest(CapabilityTest):
    def get_test_cases(self) -> list[TestCase]:
        # Return test cases with varying complexity/sensitivity
        return [
            TestCase(
                input_data="...",
                expected_output="...",
                complexity=2,
                sensitivity=3
            ),
            # ... more cases
        ]
    
    def evaluate(self, output: str, expected: Any, test_case: TestCase) -> float:
        # Return score between 0.0 and 1.0
        return score
    
    def build_prompt(self, test_case: TestCase) -> str:
        return f"Task: {test_case.input_data}"
```

2. Add to `Capability` enum in `src/llmbench/cube.py`:
```python
class Capability(str, Enum):
    # ...
    YOUR_CAPABILITY = "your_capability"
```

3. Register in benchmark script:
```python
capability_tests = {
    Capability.YOUR_CAPABILITY: YourCapabilityTest(),
}
```

## Adding New Model Providers

Implement `BaseModel` in `src/llmbench/models/your_provider.py`:
```python
from .base import BaseModel, ModelConfig

class YourProviderModel(BaseModel):
    async def generate(self, prompt: str, **kwargs) -> str:
        # Call your API
        response = await self._call_api(prompt)
        return response.text
    
    async def health_check(self) -> bool:
        # Verify API is reachable
        return True
```

## Cloud Provider Setup

**GCP Prerequisites:**
- `gcloud auth login && gcloud auth application-default login`
- `gcloud services enable compute.googleapis.com`
- Set project: `gcloud config set project YOUR_PROJECT_ID`

**AWS Prerequisites:**
- `aws configure` with Access Key ID and Secret Access Key
- Ensure EC2 and VPC permissions

**GPU Availability:**
- GCP: Check GPU quotas in IAM & Admin → Quotas
- AWS: Spot instances may have limited GPU availability in some regions

## Important Notes

**Python Version:** Requires Python 3.11+ (uses `|` union syntax and other modern features)

**New Dependencies (Distributed Mode):**
- `fastapi>=0.109.0` - REST API framework
- `uvicorn[standard]>=0.27.0` - ASGI server
- `websockets>=12.0` - Real-time dashboard updates

**Database Location:** Results are stored in `results/benchmarks.db` for local mode, `results/cloud/run-TIMESTAMP/` for cloud mode

**Cloud-init Timing:** VM provisioning takes 3-5 minutes. The system waits for `/opt/llmbench/setup-complete` marker before deploying code.

**Spot Instances:** Default to `--spot` for cost savings. Non-spot requires explicit `--no-spot` flag.

**SSH Keys:** Default SSH key is `~/.ssh/id_rsa`. Override with `--ssh-key` if needed.

**Terraform State:** Each run creates a unique tfvars file (`run-TIMESTAMP.tfvars.json`) to avoid state conflicts. Destroy requires the run ID.

**Model Warmup:** First Ollama request may be slower. Consider warmup request before benchmarking for consistent latency measurements.

**Controller Networking:** For distributed mode, workers need to reach the controller. Options:
- **Cloudflare Tunnel / ngrok:** Easiest for testing (free tier works)
- **Public IP + Firewall:** Expose port 8000, restrict to worker IPs
- **VPN (Tailscale):** Private mesh network for controller + workers
- **Cloud-based Controller:** Run controller on GCP/AWS instead of locally

**Worker Auto-Start:** Workers automatically start the agent via systemd (`llmbench-worker.service`). Check logs with:
```bash
ssh ubuntu@WORKER_IP
journalctl -u llmbench-worker -f
```

## Querying Results

```python
from llmbench.storage.sqlite import SQLiteStorage

storage = SQLiteStorage()

# Find best model for a specific point in the cube
best = storage.get_best_model(
    capability="code_generation",
    complexity=3,
    sensitivity=4,
    min_score=0.8  # Minimum acceptable score
)

# Get overall model performance
summary = storage.get_model_summary("deepseek-coder-6.7b")
```

Query logic: Returns model with highest average score at that point. If multiple models tie, returns the one with lowest cost estimate.

## Testing Guidelines

### Test Structure

```
tests/
├── controller/
│   ├── test_task_queue.py
│   ├── test_worker_registry.py
│   └── test_api.py
├── worker/
│   └── test_agent.py
├── storage/
│   └── test_sqlite.py
└── integration/
    └── test_distributed_benchmark.py
```

### Coverage Requirements

**MANDATORY: 90% minimum coverage before pushing code.**

```bash
# Check coverage
pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=90

# Generate HTML report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

### Writing Tests

**For async code:**
```python
import pytest

@pytest.mark.asyncio
async def test_task_queue_enqueue():
    queue = TaskQueue()
    item = WorkItem.create(model_config, capability, test_case)
    await queue.enqueue(item)
    assert queue.get_status()["queued"] == 1
```

**Mock external dependencies:**
```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_worker_registration():
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_post.return_value.__aenter__.return_value.status = 200
        agent = WorkerAgent("http://test", "worker-1")
        result = await agent.register()
        assert result is True
```

**Test both success and failure:**
```python
def test_benchmark_point_valid():
    point = BenchmarkPoint(Capability.CODE_GENERATION, 3, 4)
    assert point.complexity == 3

def test_benchmark_point_invalid_complexity():
    with pytest.raises(ValueError):
        BenchmarkPoint(Capability.CODE_GENERATION, 6, 4)  # complexity > 5
```

### What to Test

- ✅ **Business logic**: Task queue operations, worker registry, scoring
- ✅ **Error handling**: Invalid inputs, timeouts, network failures
- ✅ **Edge cases**: Empty queues, offline workers, retry limits
- ✅ **Integration**: Full flow from dispatch to result collection
- ❌ **Don't test**: External libraries (aiohttp, fastapi), cloud provider APIs

### Pre-Push Checklist

Before every `git push`:
1. ✅ Activate venv: `source .venv/bin/activate`
2. ✅ Run tests: `poetry run pytest tests/ --cov=src/llmbench --cov-fail-under=90`
3. ✅ Format code: `poetry run black src/ tests/`
4. ✅ Type check: `poetry run mypy src/`
5. ✅ All tests pass
6. ✅ Coverage ≥ 90%
7. ✅ Commit with descriptive message
8. ✅ Push to GitHub
