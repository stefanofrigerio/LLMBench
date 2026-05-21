"""
Cloud orchestrator for running benchmarks on remote infrastructure
"""

import asyncio
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional
import tempfile
import shutil


@dataclass
class CloudConfig:
    """Configuration for cloud infrastructure"""
    provider: Literal["gcp", "aws"]
    project_id: Optional[str] = None  # GCP only
    region: str = "us-central1"
    machine_type: str = "n1-standard-4"
    gpu_type: Optional[str] = None
    ssh_key_path: str = "~/.ssh/id_rsa"
    models_to_pull: list[str] = None
    use_spot: bool = True

    def __post_init__(self):
        if self.models_to_pull is None:
            self.models_to_pull = [
                "deepseek-coder:6.7b",
                "qwen2.5-coder:7b",
                "llama3.1:8b"
            ]


class TerraformRunner:
    """Manages Terraform operations"""

    def __init__(self, working_dir: Path):
        self.working_dir = working_dir

    def run_command(self, args: list[str], env: dict = None) -> subprocess.CompletedProcess:
        """Run terraform command"""
        cmd = ["terraform"] + args
        print(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            cwd=self.working_dir,
            capture_output=True,
            text=True,
            env=env
        )

        if result.returncode != 0:
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            raise RuntimeError(f"Terraform command failed: {' '.join(args)}")

        return result

    def init(self):
        """Initialize terraform"""
        print("Initializing Terraform...")
        self.run_command(["init"])

    def plan(self, var_file: Path):
        """Run terraform plan"""
        print("Planning infrastructure...")
        self.run_command(["plan", f"-var-file={var_file}"])

    def apply(self, var_file: Path):
        """Apply terraform configuration"""
        print("Creating infrastructure...")
        self.run_command(["apply", "-auto-approve", f"-var-file={var_file}"])

    def destroy(self, var_file: Path):
        """Destroy terraform infrastructure"""
        print("Destroying infrastructure...")
        self.run_command(["destroy", "-auto-approve", f"-var-file={var_file}"])

    def output(self, name: str) -> str:
        """Get terraform output value"""
        result = self.run_command(["output", "-raw", name])
        return result.stdout.strip()


class CloudOrchestrator:
    """Orchestrates cloud benchmark execution"""

    def __init__(self, config: CloudConfig, project_root: Path):
        self.config = config
        self.project_root = project_root
        self.run_id = f"run-{int(time.time())}"
        self.tf_dir = project_root / "infrastructure" / config.provider
        self.tf_runner = TerraformRunner(self.tf_dir)
        self.instance_ip: Optional[str] = None

    def _create_tfvars(self) -> Path:
        """Create terraform variables file"""
        tfvars = {
            "run_id": self.run_id,
            "ssh_public_key_path": str(Path(self.config.ssh_key_path).expanduser()) + ".pub",
            "models_to_pull": self.config.models_to_pull,
        }

        if self.config.provider == "gcp":
            tfvars.update({
                "project_id": self.config.project_id,
                "region": self.config.region,
                "machine_type": self.config.machine_type,
                "use_preemptible": self.config.use_spot,
            })
            if self.config.gpu_type:
                tfvars["gpu_type"] = self.config.gpu_type
        else:  # aws
            tfvars.update({
                "region": self.config.region,
                "instance_type": self.config.machine_type,
                "use_spot": self.config.use_spot,
            })

        # Write to temporary tfvars file
        tfvars_file = self.tf_dir / f"{self.run_id}.tfvars.json"
        with open(tfvars_file, "w") as f:
            json.dump(tfvars, f, indent=2)

        return tfvars_file

    def provision_infrastructure(self):
        """Provision cloud infrastructure"""
        print(f"\n{'='*60}")
        print(f"Provisioning {self.config.provider.upper()} infrastructure")
        print(f"Run ID: {self.run_id}")
        print(f"{'='*60}\n")

        # Create tfvars
        tfvars_file = self._create_tfvars()

        try:
            # Initialize and apply
            self.tf_runner.init()
            self.tf_runner.apply(tfvars_file)

            # Get instance IP
            self.instance_ip = self.tf_runner.output("instance_ip")
            print(f"\n✅ Infrastructure provisioned!")
            print(f"Instance IP: {self.instance_ip}")

        except Exception as e:
            print(f"\n❌ Failed to provision infrastructure: {e}")
            raise

        return self.instance_ip

    def deploy_and_run_benchmark(self, benchmark_script: str = "examples/run_benchmark.py"):
        """Deploy code and run benchmark on remote instance"""
        if not self.instance_ip:
            raise RuntimeError("No instance IP available. Provision infrastructure first.")

        print(f"\n{'='*60}")
        print(f"Deploying and running benchmark")
        print(f"{'='*60}\n")

        ssh_key = str(Path(self.config.ssh_key_path).expanduser())
        user = "ubuntu"

        # Deploy using script
        deploy_script = self.project_root / "infrastructure/scripts/deploy_benchmark.sh"
        subprocess.run(
            ["bash", str(deploy_script), user, self.instance_ip, ssh_key],
            check=True
        )

        # Run benchmark remotely
        print("\n🚀 Running benchmark...")
        ssh_cmd = [
            "ssh", "-i", ssh_key,
            "-o", "StrictHostKeyChecking=no",
            f"{user}@{self.instance_ip}",
            f"cd /opt/llmbench/code && source /opt/llmbench/venv/bin/activate && python {benchmark_script}"
        ]

        result = subprocess.run(ssh_cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        if result.returncode != 0:
            raise RuntimeError(f"Benchmark execution failed with code {result.returncode}")

        print("\n✅ Benchmark completed successfully!")

    def fetch_results(self, local_results_dir: Path):
        """Fetch benchmark results from remote instance"""
        if not self.instance_ip:
            raise RuntimeError("No instance IP available")

        print(f"\n📥 Fetching results from {self.instance_ip}...")

        ssh_key = str(Path(self.config.ssh_key_path).expanduser())
        user = "ubuntu"

        local_results_dir.mkdir(parents=True, exist_ok=True)

        # Use rsync to fetch results
        subprocess.run([
            "rsync", "-avz",
            "-e", f"ssh -i {ssh_key} -o StrictHostKeyChecking=no",
            f"{user}@{self.instance_ip}:/opt/llmbench/code/results/",
            str(local_results_dir / self.run_id)
        ], check=True)

        print(f"✅ Results saved to {local_results_dir / self.run_id}")

    def destroy_infrastructure(self):
        """Destroy cloud infrastructure"""
        print(f"\n{'='*60}")
        print(f"Destroying infrastructure")
        print(f"{'='*60}\n")

        tfvars_file = self.tf_dir / f"{self.run_id}.tfvars.json"

        try:
            self.tf_runner.destroy(tfvars_file)
            print("\n✅ Infrastructure destroyed!")

            # Clean up tfvars file
            if tfvars_file.exists():
                tfvars_file.unlink()

        except Exception as e:
            print(f"\n⚠️  Failed to destroy infrastructure: {e}")
            print(f"You may need to manually clean up resources with run_id: {self.run_id}")
            raise

    async def run_full_cycle(
        self,
        benchmark_script: str = "examples/run_benchmark.py",
        keep_instance: bool = False
    ):
        """Run full benchmark cycle: provision → run → fetch → destroy"""
        results_dir = self.project_root / "results" / "cloud"

        try:
            # Provision
            self.provision_infrastructure()

            # Deploy and run
            self.deploy_and_run_benchmark(benchmark_script)

            # Fetch results
            self.fetch_results(results_dir)

            print(f"\n{'='*60}")
            print(f"✅ Benchmark cycle completed successfully!")
            print(f"Run ID: {self.run_id}")
            print(f"Results: {results_dir / self.run_id}")
            print(f"{'='*60}\n")

        except Exception as e:
            print(f"\n❌ Benchmark cycle failed: {e}")
            raise

        finally:
            if not keep_instance:
                print("\n🧹 Cleaning up...")
                self.destroy_infrastructure()
            else:
                print(f"\n⚠️  Instance kept running at {self.instance_ip}")
                print(f"Remember to destroy manually: cd infrastructure/{self.config.provider} && terraform destroy")
