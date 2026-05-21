"""
Example: Run benchmark on cloud infrastructure
"""

import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llmbench.cloud import CloudOrchestrator, CloudConfig


async def main():
    # Configure cloud environment
    config = CloudConfig(
        provider="gcp",  # or "aws"
        project_id="your-gcp-project-id",  # Required for GCP
        region="us-central1",
        machine_type="n1-standard-4",  # or "g4dn.xlarge" for AWS with GPU
        gpu_type="nvidia-tesla-t4",  # Optional: add GPU
        ssh_key_path="~/.ssh/id_rsa",
        models_to_pull=[
            "deepseek-coder:6.7b",
            "qwen2.5-coder:7b",
            "llama3.1:8b"
        ],
        use_spot=True  # Use spot/preemptible instances for cost savings
    )

    # Create orchestrator
    project_root = Path(__file__).parent.parent
    orchestrator = CloudOrchestrator(config, project_root)

    # Run full cycle: provision → benchmark → fetch results → destroy
    await orchestrator.run_full_cycle(
        benchmark_script="examples/run_benchmark.py",
        keep_instance=False  # Set to True to keep instance running
    )

    print(f"\n✅ Benchmark complete! Results in: results/cloud/{orchestrator.run_id}")


if __name__ == "__main__":
    asyncio.run(main())
