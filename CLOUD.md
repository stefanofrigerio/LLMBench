# Cloud Benchmarking Guide

LLMBench supports running benchmarks on cloud infrastructure (GCP and AWS) to leverage powerful GPU instances for inference.

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Local     │      │  Terraform   │      │   Cloud     │
│   Machine   │─────>│  Provision   │─────>│  Instance   │
│             │      │              │      │  + Ollama   │
└─────────────┘      └──────────────┘      └─────────────┘
       │                                            │
       │  Deploy Code & Run Benchmark               │
       │───────────────────────────────────────────>│
       │                                            │
       │  Fetch Results                             │
       │<───────────────────────────────────────────│
       │                                            │
       │  Terraform Destroy                         │
       │───────────────────────────────────────────>│
                                                    X
```

## Prerequisites

### Required Tools

1. **Terraform** (>= 1.0)
   ```bash
   # macOS
   brew install terraform

   # Linux
   wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
   unzip terraform_1.6.0_linux_amd64.zip
   sudo mv terraform /usr/local/bin/
   ```

2. **Cloud CLI**

   **For GCP:**
   ```bash
   # Install gcloud CLI
   brew install google-cloud-sdk  # macOS
   # or visit: https://cloud.google.com/sdk/docs/install

   # Authenticate
   gcloud auth login
   gcloud auth application-default login

   # Set project
   gcloud config set project YOUR_PROJECT_ID
   ```

   **For AWS:**
   ```bash
   # Install AWS CLI
   brew install awscli  # macOS
   # or visit: https://aws.amazon.com/cli/

   # Configure credentials
   aws configure
   ```

3. **SSH Key**
   ```bash
   # Generate if you don't have one
   ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa
   ```

### Cloud Setup

#### GCP Setup

1. **Enable Required APIs:**
   ```bash
   gcloud services enable compute.googleapis.com
   gcloud services enable cloudresourcemanager.googleapis.com
   ```

2. **Set up permissions:**
   Ensure your account has:
   - `Compute Admin` role
   - `Service Account User` role

3. **Check quotas:**
   - GPU quota (if using GPUs): https://console.cloud.google.com/iam-admin/quotas
   - For T4 GPUs: request "NVIDIA T4 GPUs" quota increase

#### AWS Setup

1. **Check limits:**
   - EC2 instance limits: https://console.aws.amazon.com/servicequotas
   - For GPU instances (g4dn family), check GPU quotas

2. **VPC Configuration:**
   - LLMBench uses the default VPC
   - Ensure default VPC exists in your region

## Usage

### Quick Start

```bash
# Install LLMBench
pip install -e .

# Run benchmark on GCP
llmbench run --provider gcp --project my-project

# Run benchmark on AWS
llmbench run --provider aws --region us-east-1
```

### Full Command Reference

#### 1. Run Full Benchmark Cycle

Provision → Run → Fetch Results → Destroy

```bash
# GCP with GPU
llmbench run \
  --provider gcp \
  --project my-project \
  --region us-central1 \
  --machine n1-standard-4 \
  --gpu nvidia-tesla-t4 \
  --models deepseek-coder:6.7b qwen2.5-coder:7b

# AWS with GPU (spot instance)
llmbench run \
  --provider aws \
  --region us-east-1 \
  --machine g4dn.xlarge \
  --spot

# Keep instance running after benchmark
llmbench run --provider gcp --project my-project --keep
```

#### 2. Provision Only

Create infrastructure without running benchmark:

```bash
llmbench provision --provider gcp --project my-project --gpu nvidia-tesla-t4
```

This outputs the instance IP and run ID. You can then:
- SSH into the instance
- Run benchmarks manually
- Iterate on tests

#### 3. Destroy Infrastructure

```bash
llmbench destroy --provider gcp --run-id run-1234567890
```

### Python API

```python
import asyncio
from pathlib import Path
from llmbench.cloud import CloudOrchestrator, CloudConfig

async def main():
    config = CloudConfig(
        provider="gcp",
        project_id="my-project",
        region="us-central1",
        machine_type="n1-standard-4",
        gpu_type="nvidia-tesla-t4",
        models_to_pull=[
            "deepseek-coder:6.7b",
            "qwen2.5-coder:7b"
        ],
        use_spot=True
    )

    orchestrator = CloudOrchestrator(config, Path.cwd())

    # Full cycle
    await orchestrator.run_full_cycle(keep_instance=False)

asyncio.run(main())
```

## Machine Types & Costs

### GCP

| Machine Type | vCPUs | RAM | GPU | Spot Price/hr | On-Demand Price/hr |
|--------------|-------|-----|-----|---------------|-------------------|
| n1-standard-4 | 4 | 15 GB | - | ~$0.04 | ~$0.19 |
| n1-standard-8 | 8 | 30 GB | - | ~$0.08 | ~$0.38 |
| n1-standard-4 + T4 | 4 | 15 GB | T4 | ~$0.15 | ~$0.51 |
| n1-standard-8 + T4 | 8 | 30 GB | T4 | ~$0.23 | ~$0.70 |

**GPU Options:**
- `nvidia-tesla-t4` - Good for inference, 16GB VRAM
- `nvidia-tesla-v100` - Higher performance, 16GB VRAM
- `nvidia-tesla-a100` - Best performance, 40GB VRAM

### AWS

| Instance Type | vCPUs | RAM | GPU | Spot Price/hr | On-Demand Price/hr |
|---------------|-------|-----|-----|---------------|-------------------|
| c5.2xlarge | 8 | 16 GB | - | ~$0.10 | ~$0.34 |
| c5.4xlarge | 16 | 32 GB | - | ~$0.20 | ~$0.68 |
| g4dn.xlarge | 4 | 16 GB | T4 | ~$0.16 | ~$0.53 |
| g4dn.2xlarge | 8 | 32 GB | T4 | ~$0.23 | ~$0.75 |

## Cost Estimation

**Example Benchmark Run:**
- Setup time: ~5 minutes
- Benchmark time: ~20 minutes (depends on models/tests)
- Total time: ~25 minutes

**Estimated costs:**
- GCP n1-standard-4 (preemptible): **$0.02**
- GCP n1-standard-4 + T4 (preemptible): **$0.06**
- AWS g4dn.xlarge (spot): **$0.07**

**Tips for cost savings:**
- ✅ Use spot/preemptible instances
- ✅ Destroy immediately after benchmark (default behavior)
- ✅ Use smaller instances for simpler benchmarks
- ⚠️  Remember to destroy if using `--keep` flag

## Advanced Usage

### Custom Benchmark Scripts

```bash
llmbench run \
  --provider gcp \
  --project my-project \
  --benchmark-script my_custom_benchmark.py
```

### SSH into Running Instance

```bash
# Get IP from provision output
llmbench provision --provider gcp --project my-project
# Output: Instance IP: 34.123.45.67, Run ID: run-1234567890

# SSH
ssh -i ~/.ssh/id_rsa ubuntu@34.123.45.67

# On instance
cd /opt/llmbench/code
source /opt/llmbench/venv/bin/activate
python examples/run_benchmark.py
```

### Manual Terraform Operations

```bash
cd infrastructure/gcp  # or infrastructure/aws

# Initialize
terraform init

# Create tfvars
cat > my-run.tfvars << EOF
project_id = "my-project"
run_id = "manual-run-1"
ssh_public_key_path = "~/.ssh/id_rsa.pub"
models_to_pull = ["deepseek-coder:6.7b"]
EOF

# Apply
terraform apply -var-file=my-run.tfvars

# Destroy
terraform destroy -var-file=my-run.tfvars
```

## Troubleshooting

### Instance provisioning fails

**Problem:** Quota exceeded
```
Error: Error creating instance: googleapi: Error 403: Quota 'CPUS' exceeded
```

**Solution:** Request quota increase in cloud console

---

**Problem:** GPU not available in region
```
Error: Invalid value for field 'resource.guestAccelerators'
```

**Solution:** Check GPU availability: https://cloud.google.com/compute/docs/gpus/gpu-regions-zones

### SSH connection fails

**Problem:** Connection timeout

**Solution:**
1. Check firewall rules allow SSH from your IP
2. Wait longer - instance may still be initializing
3. Check cloud console for instance status

### Ollama not starting

**Problem:** Models not pulling

**Solution:**
1. SSH into instance
2. Check logs: `sudo journalctl -u ollama -f`
3. Check setup log: `cat /opt/llmbench/setup.log`
4. Manually pull: `ollama pull deepseek-coder:6.7b`

### Terraform state issues

**Problem:** State out of sync

**Solution:**
```bash
cd infrastructure/gcp
terraform refresh -var-file=run-1234567890.tfvars.json
```

## Security Best Practices

1. **Restrict SSH access:**
   ```bash
   # In variables.tf or CLI
   allowed_ssh_ips = ["YOUR_IP/32"]
   ```

2. **Use separate GCP project for benchmarks**

3. **Enable audit logging:**
   ```bash
   gcloud logging read "resource.type=gce_instance"
   ```

4. **Rotate SSH keys regularly**

5. **Monitor costs:**
   - Set up billing alerts
   - Use budget limits

## CI/CD Integration

### GitHub Actions Example

```yaml
name: LLM Benchmark

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly
  workflow_dispatch:

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -e .

      - name: Set up Terraform
        uses: hashicorp/setup-terraform@v2

      - name: Configure GCP credentials
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Run benchmark
        run: |
          llmbench run \
            --provider gcp \
            --project ${{ secrets.GCP_PROJECT_ID }} \
            --models deepseek-coder:6.7b

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: results/cloud/
```

## Next Steps

- See [README.md](README.md) for project overview
- Add custom capabilities in `src/llmbench/capabilities/`
- Customize machine types in `infrastructure/gcp/variables.tf`
- Set up monitoring and alerting for long-running benchmarks
