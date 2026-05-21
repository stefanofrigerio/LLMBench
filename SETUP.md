# Quick Setup Guide

Get started with LLMBench in 5 minutes.

## Option 1: Cloud Mode (Recommended)

### 1. Install Prerequisites

```bash
# Install Terraform
brew install terraform  # macOS
# or download from https://terraform.io

# Install cloud CLI
brew install google-cloud-sdk  # for GCP
# or
brew install awscli  # for AWS
```

### 2. Authenticate

**GCP:**
```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable compute.googleapis.com
```

**AWS:**
```bash
aws configure
# Enter your Access Key ID and Secret Access Key
```

### 3. Install LLMBench

```bash
cd LLMBench
pip install -e .
```

### 4. Run Your First Benchmark

**GCP:**
```bash
llmbench run --provider gcp --project YOUR_PROJECT_ID
```

**AWS:**
```bash
llmbench run --provider aws --region us-east-1
```

That's it! The system will:
- ✅ Create a cloud VM
- ✅ Install Ollama and pull models
- ✅ Run benchmarks
- ✅ Fetch results
- ✅ Destroy the VM

Results will be in `results/cloud/run-TIMESTAMP/`

---

## Option 2: Local Mode

### 1. Install Ollama

Visit https://ollama.ai and follow installation instructions.

### 2. Pull Models

```bash
ollama pull deepseek-coder:6.7b
ollama pull qwen2.5-coder:7b
ollama pull llama3.1:8b
```

### 3. Install LLMBench

```bash
cd LLMBench
pip install -e .
```

### 4. Run Benchmark

```bash
python examples/run_benchmark.py
```

Results will be in `results/benchmarks.db`

---

## What's Next?

### View Results

```python
from llmbench.storage.sqlite import SQLiteStorage

storage = SQLiteStorage()

# Get best model for a task
best = storage.get_best_model(
    capability="code_generation",
    complexity=3,
    sensitivity=4,
    min_score=0.8
)

print(f"Use {best['model_name']} with score {best['avg_score']:.2f}")
```

### Add Custom Tests

Create a new capability test:

```python
# src/llmbench/capabilities/my_capability.py
from .base import CapabilityTest, TestCase

class MyCapabilityTest(CapabilityTest):
    def get_test_cases(self):
        return [
            TestCase(
                input_data="your test input",
                expected_output="expected result",
                complexity=3,
                sensitivity=2
            )
        ]

    def evaluate(self, output, expected, test_case):
        # Return score 0-1
        return 1.0 if output == expected else 0.0

    def build_prompt(self, test_case):
        return f"Task: {test_case.input_data}"
```

### Cost Optimization

```bash
# Use spot instances (default)
llmbench run --provider gcp --project my-project --spot

# Use smaller machines for simple tests
llmbench run --provider gcp --project my-project --machine n1-standard-2

# CPU-only (no GPU)
llmbench run --provider aws --machine c5.2xlarge
```

### CI/CD Integration

Add to `.github/workflows/benchmark.yml`:

```yaml
name: Weekly Benchmark
on:
  schedule:
    - cron: '0 0 * * 0'

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: hashicorp/setup-terraform@v2

      - name: Run benchmark
        env:
          GOOGLE_CREDENTIALS: ${{ secrets.GCP_SA_KEY }}
        run: |
          pip install -e .
          llmbench run --provider gcp --project ${{ secrets.GCP_PROJECT }}
```

## Troubleshooting

### "Quota exceeded" error

Request quota increase:
- **GCP**: https://console.cloud.google.com/iam-admin/quotas
- **AWS**: https://console.aws.amazon.com/servicequotas

### Connection timeout

Wait longer - instance provisioning takes 3-5 minutes. Check:
```bash
# See terraform output
cd infrastructure/gcp  # or aws
terraform output
```

### Can't find models

Models are pulled during cloud-init. Check the log:
```bash
ssh ubuntu@INSTANCE_IP
cat /opt/llmbench/setup.log
```

## Need Help?

- 📖 Full docs: [README.md](README.md)
- ☁️ Cloud guide: [CLOUD.md](CLOUD.md)
- 🐛 Issues: https://github.com/stefanofrigerio/LLMBench/issues
