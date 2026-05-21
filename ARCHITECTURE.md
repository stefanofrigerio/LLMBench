# LLMBench Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         LLMBench System                         │
└─────────────────────────────────────────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
         ┌──────▼──────┐              ┌──────▼──────┐
         │ Local Mode  │              │ Cloud Mode  │
         └──────┬──────┘              └──────┬──────┘
                │                             │
                │                      ┌──────▼───────┐
                │                      │  Terraform   │
                │                      │  Provision   │
                │                      └──────┬───────┘
                │                             │
                │                      ┌──────▼───────┐
                │                      │  Cloud VM    │
                │                      │  + Ollama    │
                │                      └──────┬───────┘
                │                             │
         ┌──────▼─────────────────────────────▼──────┐
         │         Benchmark Runner                  │
         │  ┌──────────────────────────────────┐     │
         │  │  Capability Tests                 │     │
         │  │  - Code Generation                │     │
         │  │  - Unit Test Writing              │     │
         │  │  - OCR                            │     │
         │  │  - Reasoning                      │     │
         │  │  - ...                            │     │
         │  └──────────────┬───────────────────┘     │
         │                 │                          │
         │  ┌──────────────▼───────────────────┐     │
         │  │  Model Interface                  │     │
         │  │  - Ollama (local/remote)          │     │
         │  │  - OpenAI (comparison)            │     │
         │  │  - Anthropic (comparison)         │     │
         │  └──────────────┬───────────────────┘     │
         │                 │                          │
         │  ┌──────────────▼───────────────────┐     │
         │  │  Results Evaluation               │     │
         │  │  - Score calculation              │     │
         │  │  - Latency measurement            │     │
         │  │  - Cost estimation                │     │
         │  └──────────────┬───────────────────┘     │
         └─────────────────┼───────────────────────────┘
                           │
                  ┌────────▼────────┐
                  │  SQLite Storage │
                  │  - Results DB   │
                  │  - Query API    │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │  Model Selection │
                  │  - Query by point│
                  │  - Best model    │
                  └──────────────────┘
```

## The 3D Cube Model

```
              Sensitivity (Z-axis)
                    ↑
                5   │ ███  Critical
                4   │ ███  High
                3   │ ███  Medium
                2   │ ███  Minor
                1   │ ███  Low
                    │
                    └─────────────→ Complexity (X-axis)
                   / 1  2  3  4  5
                  /
                 /
          Capability (Y-axis)
          - code_generation
          - unit_test_writing
          - ocr
          - reasoning
          - structured_output
          - translation
```

Each cell in the cube contains:
- Best model recommendation
- Performance score (0-1)
- Average latency (ms)
- Cost estimate
- Sample size

## Component Architecture

### 1. Core Components (`src/llmbench/`)

#### `cube.py`
```
BenchmarkPoint(capability, complexity, sensitivity)
    ↓
BenchmarkResult(point, model, score, latency, cost)
```

#### `models/`
```
BaseModel (abstract)
    ├── OllamaModel
    │   ├── generate(prompt) → output
    │   └── health_check() → bool
    ├── OpenAIModel (future)
    └── AnthropicModel (future)
```

#### `capabilities/`
```
CapabilityTest (abstract)
    ├── get_test_cases() → [TestCase]
    ├── evaluate(output, expected) → score
    └── build_prompt(test_case) → prompt

Implementations:
    ├── CodeGenerationTest
    ├── UnitTestWritingTest (future)
    ├── OCRTest (future)
    └── ReasoningTest (future)
```

#### `runners/benchmark.py`
```
BenchmarkRunner
    ├── run_single_test(model, capability, test_case)
    ├── run_capability(model, capability)
    └── run_full_benchmark() → [BenchmarkResult]
```

#### `storage/sqlite.py`
```
SQLiteStorage
    ├── save_result(result)
    ├── save_results(results)
    ├── get_best_model(capability, complexity, sensitivity)
    └── get_model_summary(model_name)
```

### 2. Cloud Infrastructure (`infrastructure/`)

#### Terraform Modules

**GCP (`infrastructure/gcp/`):**
```
main.tf
    ├── google_compute_instance
    │   ├── Machine type (n1-standard-*)
    │   ├── GPU (optional: T4, V100, A100)
    │   ├── Boot disk (Ubuntu 22.04)
    │   └── Cloud-init user data
    └── google_compute_firewall
        └── SSH access
```

**AWS (`infrastructure/aws/`):**
```
main.tf
    ├── aws_instance
    │   ├── Instance type (c5.*, g4dn.*)
    │   ├── AMI (Ubuntu 22.04)
    │   ├── Spot instance (optional)
    │   └── User data (cloud-init)
    ├── aws_security_group
    │   └── SSH ingress
    └── aws_key_pair
```

#### Provisioning (`infrastructure/scripts/`)

**cloud-init.yaml:**
```
1. Install system packages
2. Install Ollama
3. Start Ollama service
4. Pull models from config
5. Setup Python venv
6. Mark setup complete
```

**deploy_benchmark.sh:**
```
1. Wait for SSH ready
2. Wait for cloud-init complete
3. Rsync code to instance
4. Install Python dependencies
5. Ready for benchmark
```

### 3. Cloud Orchestration (`src/llmbench/cloud/`)

```
CloudOrchestrator
    │
    ├── provision_infrastructure()
    │   ├── Create tfvars
    │   ├── terraform init
    │   ├── terraform apply
    │   └── Return instance IP
    │
    ├── deploy_and_run_benchmark()
    │   ├── Deploy code (rsync)
    │   ├── SSH and run benchmark
    │   └── Capture output
    │
    ├── fetch_results()
    │   └── Rsync results back
    │
    ├── destroy_infrastructure()
    │   ├── terraform destroy
    │   └── Cleanup tfvars
    │
    └── run_full_cycle()
        ├── provision
        ├── deploy & run
        ├── fetch results
        └── destroy (unless --keep)
```

## Data Flow

### Local Benchmark Flow

```
1. User runs: python examples/run_benchmark.py

2. BenchmarkRunner initialized
   - Load models from config
   - Load capability tests

3. For each model:
   a. Health check (is Ollama responding?)
   b. For each capability:
      i.   Get test cases
      ii.  For each test case:
           - Build prompt
           - Generate output (measure latency)
           - Evaluate output → score
           - Create BenchmarkResult
      iii. Save results to SQLite

4. Print summary
   - Model performance
   - Best model recommendations
```

### Cloud Benchmark Flow

```
1. User runs: llmbench run --provider gcp --project my-project

2. CloudOrchestrator.run_full_cycle()

3. Provision Phase:
   a. Generate tfvars with run_id
   b. terraform init
   c. terraform apply
   d. Wait for outputs (instance_ip)

4. Deploy Phase:
   a. Wait for SSH ready
   b. Wait for cloud-init complete
   c. rsync code to /opt/llmbench/code
   d. Install dependencies

5. Execution Phase:
   a. SSH to instance
   b. Run: python examples/run_benchmark.py
   c. Capture output and logs

6. Fetch Phase:
   a. rsync results/ from instance
   b. Save to local results/cloud/run-TIMESTAMP/

7. Cleanup Phase:
   a. terraform destroy
   b. Remove tfvars file
   c. Print summary
```

## Database Schema

```sql
CREATE TABLE benchmark_results (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    capability TEXT NOT NULL,
    complexity INTEGER NOT NULL (1-5),
    sensitivity INTEGER NOT NULL (1-5),
    model_name TEXT NOT NULL,
    score REAL NOT NULL (0.0-1.0),
    latency_ms REAL NOT NULL,
    cost_estimate REAL NOT NULL,
    error TEXT,
    raw_output TEXT,
    metadata TEXT (JSON)
);

CREATE INDEX idx_model_capability 
    ON benchmark_results(model_name, capability);

CREATE INDEX idx_point 
    ON benchmark_results(capability, complexity, sensitivity);
```

## Query Patterns

### Get Best Model for Task
```python
best = storage.get_best_model(
    capability="code_generation",
    complexity=3,
    sensitivity=4,
    min_score=0.8
)
# Returns: model with highest avg_score >= 0.8, 
#          with lowest cost as tiebreaker
```

### Get Model Performance Summary
```python
summary = storage.get_model_summary("deepseek-coder")
# Returns: per-capability stats (avg_score, latency, test_count, errors)
```

## Extension Points

### Adding New Capability

1. Create `src/llmbench/capabilities/my_capability.py`:
   ```python
   class MyCapabilityTest(CapabilityTest):
       def get_test_cases(self): ...
       def evaluate(self, output, expected, test_case): ...
       def build_prompt(self, test_case): ...
   ```

2. Add to `Capability` enum in `cube.py`

3. Register in runner:
   ```python
   capability_tests = {
       Capability.MY_CAPABILITY: MyCapabilityTest(),
   }
   ```

### Adding New Model Provider

1. Create `src/llmbench/models/my_provider.py`:
   ```python
   class MyProviderModel(BaseModel):
       async def generate(self, prompt, **kwargs): ...
       async def health_check(self): ...
   ```

2. Use in benchmark:
   ```python
   model = MyProviderModel(ModelConfig(...))
   ```

### Adding New Cloud Provider

1. Create `infrastructure/azure/` (or other provider)
2. Write `main.tf` and `variables.tf`
3. Update `CloudOrchestrator` to support provider
4. Add CLI option for provider

## Security Considerations

### Cloud Infrastructure
- ✅ Firewall rules limit SSH to specific IPs
- ✅ Instances use service accounts with minimal permissions
- ✅ Preemptible/spot instances reduce cost attack surface
- ✅ Automatic cleanup prevents orphaned resources
- ⚠️  SSH keys should be rotated regularly
- ⚠️  Consider using bastion hosts for production

### Data Privacy
- ✅ Test data should not contain sensitive information
- ✅ Results stored locally by default
- ✅ Cloud VMs destroyed after benchmark (no data persistence)
- ⚠️  Model outputs may leak test data - review before sharing

### Cost Controls
- ✅ Spot/preemptible instances by default
- ✅ Automatic destruction after benchmark
- ✅ Run ID prevents accidental multiple provisions
- ⚠️  Set up billing alerts in cloud console
- ⚠️  Monitor terraform state for orphaned resources

## Performance Optimization

### Parallel Execution
```python
# Run multiple test cases in parallel
results = await asyncio.gather(*[
    runner.run_single_test(model, capability, test_case)
    for test_case in test_cases
])
```

### Result Caching
- SQLite stores all historical results
- Avoid re-running identical tests
- Query existing results first

### Model Warmup
- First request to Ollama may be slow
- Consider warmup request before benchmark

### Resource Sizing

**For CPU-only inference:**
- GCP: n1-standard-4 (4 vCPU, 15 GB RAM)
- AWS: c5.2xlarge (8 vCPU, 16 GB RAM)

**For GPU inference:**
- GCP: n1-standard-4 + T4 GPU
- AWS: g4dn.xlarge (T4 GPU)

**For large models (>13B):**
- GCP: n1-standard-8 + V100 or A100
- AWS: g4dn.2xlarge or larger

## Future Enhancements

### Short Term
- [ ] Add more capability tests (OCR, reasoning, translation)
- [ ] Web dashboard for cube visualization
- [ ] Export results to CSV/JSON
- [ ] Support for private model registries

### Medium Term
- [ ] Multi-region benchmarking
- [ ] Cost comparison with proprietary APIs
- [ ] Automated threshold tuning
- [ ] Model recommendation engine with ML

### Long Term
- [ ] Distributed benchmarking across multiple instances
- [ ] Real-time monitoring and alerting
- [ ] A/B testing framework for model selection
- [ ] Integration with MLOps platforms (MLflow, Weights & Biases)
