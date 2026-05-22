"""
CLI for LLMBench
"""

import asyncio
import argparse
from pathlib import Path
import sys
import os

from .cloud import CloudOrchestrator, CloudConfig


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="LLMBench - Benchmark open-source LLMs in the cloud",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run benchmark on GCP with GPU
  llmbench run --provider gcp --project my-project --gpu nvidia-tesla-t4

  # Run on AWS spot instance
  llmbench run --provider aws --region us-east-1 --machine g4dn.xlarge --spot

  # Keep instance running after benchmark
  llmbench run --provider gcp --project my-project --keep

  # Run with specific models
  llmbench run --provider gcp --project my-project --models deepseek-coder:6.7b qwen2.5-coder:7b

  # Just provision (no benchmark)
  llmbench provision --provider gcp --project my-project

  # Destroy by run ID
  llmbench destroy --provider gcp --run-id run-1234567890
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Controller command
    controller_parser = subparsers.add_parser("controller", help="Start controller server")
    controller_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)"
    )
    controller_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )

    # Worker command
    worker_parser = subparsers.add_parser("worker", help="Start worker agent")
    worker_parser.add_argument(
        "--controller-url",
        required=True,
        help="Controller URL (e.g., http://controller:8000)"
    )
    worker_parser.add_argument(
        "--worker-id",
        help="Unique worker ID (defaults to hostname)"
    )
    worker_parser.add_argument(
        "--api-key",
        help="API key for authentication"
    )

    # Dispatch command
    dispatch_parser = subparsers.add_parser("dispatch", help="Dispatch distributed benchmark")
    add_cloud_args(dispatch_parser)
    dispatch_parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Number of worker instances to provision (default: 2)"
    )
    dispatch_parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep workers running after benchmark"
    )
    dispatch_parser.add_argument(
        "--controller-port",
        type=int,
        default=8000,
        help="Port for controller server (default: 8000)"
    )

    # Status command
    status_parser = subparsers.add_parser("status", help="Check benchmark run status")
    status_parser.add_argument(
        "--run-id",
        required=True,
        help="Run ID to check"
    )
    status_parser.add_argument(
        "--controller-url",
        default="http://localhost:8000",
        help="Controller URL (default: http://localhost:8000)"
    )

    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Cleanup worker infrastructure")
    cleanup_parser.add_argument(
        "--provider",
        required=True,
        choices=["gcp", "aws"],
        help="Cloud provider"
    )
    cleanup_parser.add_argument(
        "--run-id",
        required=True,
        help="Run ID to cleanup"
    )

    # Run command (legacy single-VM mode)
    run_parser = subparsers.add_parser("run", help="Run full benchmark cycle (single VM)")
    add_cloud_args(run_parser)
    run_parser.add_argument(
        "--benchmark-script",
        default="examples/run_benchmark.py",
        help="Path to benchmark script to run"
    )
    run_parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep instance running after benchmark"
    )

    # Provision command
    provision_parser = subparsers.add_parser("provision", help="Provision infrastructure only")
    add_cloud_args(provision_parser)

    # Local command
    local_parser = subparsers.add_parser(
        "local",
        help="Run benchmark locally with Ollama (no cloud required)"
    )
    local_parser.add_argument(
        "--model",
        required=True,
        help="Ollama model tag to benchmark (e.g. qwen2.5:latest)"
    )
    local_parser.add_argument(
        "--capabilities",
        nargs="+",
        default=["invoice_extractor"],
        help="Capabilities to test (default: invoice_extractor)"
    )
    local_parser.add_argument(
        "--complexity-min",
        type=int,
        default=1,
        metavar="N",
        help="Minimum complexity to include (1-5, default: 1)"
    )
    local_parser.add_argument(
        "--complexity-max",
        type=int,
        default=5,
        metavar="N",
        help="Maximum complexity to include (1-5, default: 5)"
    )
    local_parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="Ollama base URL (default: http://localhost:11434)"
    )
    local_parser.add_argument(
        "--db",
        default="results/benchmarks.db",
        dest="db_path",
        help="SQLite database path (default: results/benchmarks.db)"
    )

    # Destroy command
    destroy_parser = subparsers.add_parser("destroy", help="Destroy infrastructure")
    destroy_parser.add_argument(
        "--provider",
        required=True,
        choices=["gcp", "aws"],
        help="Cloud provider"
    )
    destroy_parser.add_argument(
        "--run-id",
        required=True,
        help="Run ID to destroy"
    )

    return parser


def add_cloud_args(parser: argparse.ArgumentParser):
    """Add common cloud configuration arguments"""
    parser.add_argument(
        "--provider",
        required=True,
        choices=["gcp", "aws"],
        help="Cloud provider to use"
    )
    parser.add_argument(
        "--project",
        help="GCP project ID (required for GCP)"
    )
    parser.add_argument(
        "--region",
        default="us-central1",
        help="Cloud region (default: us-central1 for GCP, us-east-1 for AWS)"
    )
    parser.add_argument(
        "--machine",
        dest="machine_type",
        help="Machine/instance type (default: n1-standard-4 for GCP, g4dn.xlarge for AWS)"
    )
    parser.add_argument(
        "--gpu",
        dest="gpu_type",
        help="GPU type (e.g., nvidia-tesla-t4 for GCP)"
    )
    parser.add_argument(
        "--ssh-key",
        dest="ssh_key_path",
        default="~/.ssh/id_rsa",
        help="Path to SSH private key (default: ~/.ssh/id_rsa)"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        dest="models_to_pull",
        help="Models to pull and benchmark"
    )
    parser.add_argument(
        "--spot/--no-spot",
        dest="use_spot",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Use spot/preemptible instances (default: yes)"
    )


async def cmd_run(args):
    """Execute run command"""
    config = CloudConfig(
        provider=args.provider,
        project_id=args.project,
        region=args.region,
        machine_type=args.machine_type or ("n1-standard-4" if args.provider == "gcp" else "g4dn.xlarge"),
        gpu_type=args.gpu_type,
        ssh_key_path=args.ssh_key_path,
        models_to_pull=args.models_to_pull,
        use_spot=args.use_spot,
    )

    # Validate GCP requires project_id
    if config.provider == "gcp" and not config.project_id:
        print("❌ Error: --project is required for GCP")
        sys.exit(1)

    project_root = Path(__file__).parent.parent.parent
    orchestrator = CloudOrchestrator(config, project_root)

    await orchestrator.run_full_cycle(
        benchmark_script=args.benchmark_script,
        keep_instance=args.keep
    )


async def cmd_provision(args):
    """Execute provision command"""
    config = CloudConfig(
        provider=args.provider,
        project_id=args.project,
        region=args.region,
        machine_type=args.machine_type or ("n1-standard-4" if args.provider == "gcp" else "g4dn.xlarge"),
        gpu_type=args.gpu_type,
        ssh_key_path=args.ssh_key_path,
        models_to_pull=args.models_to_pull,
        use_spot=args.use_spot,
    )

    if config.provider == "gcp" and not config.project_id:
        print("❌ Error: --project is required for GCP")
        sys.exit(1)

    project_root = Path(__file__).parent.parent.parent
    orchestrator = CloudOrchestrator(config, project_root)

    instance_ip = orchestrator.provision_infrastructure()
    print(f"\n{'='*60}")
    print(f"✅ Infrastructure provisioned successfully!")
    print(f"Instance IP: {instance_ip}")
    print(f"Run ID: {orchestrator.run_id}")
    print(f"\nTo run benchmark manually:")
    print(f"  ssh -i {config.ssh_key_path} ubuntu@{instance_ip}")
    print(f"\nTo destroy:")
    print(f"  llmbench destroy --provider {config.provider} --run-id {orchestrator.run_id}")
    print(f"{'='*60}\n")


def cmd_destroy(args):
    """Execute destroy command"""
    project_root = Path(__file__).parent.parent.parent
    tf_dir = project_root / "infrastructure" / args.provider

    from .cloud.orchestrator import TerraformRunner

    runner = TerraformRunner(tf_dir)
    tfvars_file = tf_dir / f"{args.run_id}.tfvars.json"

    if not tfvars_file.exists():
        print(f"⚠️  Warning: tfvars file not found: {tfvars_file}")
        print("Attempting to destroy anyway...")

    try:
        runner.init()
        runner.destroy(tfvars_file)
        print(f"\n✅ Infrastructure destroyed: {args.run_id}")

        if tfvars_file.exists():
            tfvars_file.unlink()

    except Exception as e:
        print(f"\n❌ Failed to destroy infrastructure: {e}")
        print(f"You may need to manually destroy resources in the cloud console")
        sys.exit(1)


async def cmd_local(args):
    """Run benchmark locally using Ollama on this machine."""
    from .models.ollama import OllamaModel
    from .models.base import ModelConfig
    from .capabilities import get_capability_test, list_capabilities
    from .runners.benchmark import BenchmarkRunner
    from .storage.sqlite import SQLiteStorage
    from .cube import Capability

    print(f"Running local benchmark")
    print(f"  Model:        {args.model}")
    print(f"  Capabilities: {args.capabilities}")
    print(f"  Complexity:   {args.complexity_min}-{args.complexity_max}")
    print(f"  Ollama:       {args.ollama_url}")
    print()

    model_name = args.model.replace(":", "-")
    model = OllamaModel(
        ModelConfig(
            name=model_name,
            provider="ollama",
            model_id=args.model,
            temperature=0.2,
        ),
        base_url=args.ollama_url,
    )

    print("Checking Ollama health...")
    if not await model.health_check():
        print(f"ERROR: Ollama not reachable at {args.ollama_url} or model '{args.model}' not found.")
        print(f"Available local models: ollama list")
        sys.exit(1)
    print(f"  {args.model} is ready\n")

    capability_tests = {}
    available = list_capabilities()
    for cap_name in args.capabilities:
        if cap_name not in available:
            print(f"WARNING: Unknown capability '{cap_name}', skipping. Available: {available}")
            continue
        cap = Capability(cap_name)
        capability_tests[cap] = get_capability_test(cap)

    if not capability_tests:
        print("ERROR: No valid capabilities to run.")
        sys.exit(1)

    runner = BenchmarkRunner([model], capability_tests)
    storage = SQLiteStorage(args.db_path)

    total_tests = 0
    all_results = []

    for cap, cap_test in capability_tests.items():
        test_cases = [
            tc for tc in cap_test.get_test_cases()
            if args.complexity_min <= tc.complexity <= args.complexity_max
        ]
        print(f"Running {cap.value}: {len(test_cases)} test case(s)...")
        for tc in test_cases:
            result = await runner.run_single_test(model, cap, tc)
            all_results.append(result)
            total_tests += 1
            status = "PASS" if result.score == 1.0 else ("ERROR" if result.error else "FAIL")
            if result.error:
                print(f"  [{status}] complexity={tc.complexity} — {result.error}")
            else:
                print(f"  [{status}] complexity={tc.complexity} — score={result.score:.2f}  latency={result.latency_ms:.0f}ms")

    print()
    storage.save_results(all_results)
    print(f"Results saved to {args.db_path}")

    scores = [r.score for r in all_results if not r.error]
    if scores:
        avg = sum(scores) / len(scores)
        print(f"\nSummary: {total_tests} tests | avg score={avg:.2f} | "
              f"pass={sum(1 for s in scores if s == 1.0)}/{len(scores)}")


async def cmd_controller(args):
    """Execute controller command - start the controller server"""
    from .controller.api import create_app
    import uvicorn

    print(f"🚀 Starting LLMBench Controller")
    print(f"   Host: {args.host}")
    print(f"   Port: {args.port}")
    print(f"   Dashboard: http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}")
    print()

    app = create_app()

    config = uvicorn.Config(
        app,
        host=args.host,
        port=args.port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


async def cmd_worker(args):
    """Execute worker command - start a worker agent"""
    from .worker.agent import WorkerAgent

    api_key = args.api_key or os.getenv("LLMBENCH_API_KEY")

    print(f"🤖 Starting LLMBench Worker")
    print(f"   Worker ID: {args.worker_id or 'auto'}")
    print(f"   Controller: {args.controller_url}")
    print()

    agent = WorkerAgent(
        controller_url=args.controller_url,
        worker_id=args.worker_id,
        api_key=api_key
    )

    await agent.start()


async def cmd_dispatch(args):
    """Execute dispatch command - provision workers and dispatch benchmark"""
    import time
    import aiohttp

    config = CloudConfig(
        provider=args.provider,
        project_id=args.project,
        region=args.region,
        machine_type=args.machine_type or ("n1-standard-4" if args.provider == "gcp" else "g4dn.xlarge"),
        gpu_type=args.gpu_type,
        ssh_key_path=args.ssh_key_path,
        models_to_pull=args.models_to_pull,
        use_spot=args.use_spot,
    )

    if config.provider == "gcp" and not config.project_id:
        print("❌ Error: --project is required for GCP")
        sys.exit(1)

    from .controller.orchestrator import DistributedOrchestrator

    project_root = Path(__file__).parent.parent.parent
    orchestrator = DistributedOrchestrator(
        config=config,
        worker_count=args.workers,
        project_root=project_root,
        controller_port=args.controller_port
    )

    print(f"🚀 Dispatching distributed benchmark")
    print(f"   Provider: {config.provider}")
    print(f"   Workers: {args.workers}")
    print(f"   Region: {config.region}")
    print()

    try:
        # Start controller in background
        print("1️⃣  Starting controller...")
        controller_task = asyncio.create_task(orchestrator.start_controller())
        await asyncio.sleep(3)  # Give controller time to start

        # Provision workers
        print("\n2️⃣  Provisioning workers...")
        worker_ips = await orchestrator.provision_workers()
        print(f"✅ Provisioned {len(worker_ips)} workers")

        # Wait for workers to come online
        print("\n3️⃣  Waiting for workers to register...")
        await orchestrator.wait_for_workers(timeout=600)

        # Dispatch benchmark
        print("\n4️⃣  Dispatching benchmark tasks...")
        await orchestrator.dispatch_benchmark()

        # Monitor progress
        print("\n5️⃣  Running benchmark...")
        await orchestrator.wait_for_completion()

        print("\n✅ Benchmark complete!")
        print(f"   Results: results/benchmarks.db")
        print(f"   Run ID: {orchestrator.run_id}")

        if not args.keep:
            print("\n6️⃣  Cleaning up workers...")
            await orchestrator.destroy_workers()
            print("✅ Cleanup complete")
        else:
            print(f"\n⚠️  Workers kept running (run_id: {orchestrator.run_id})")
            print(f"   Cleanup with: llmbench cleanup --provider {config.provider} --run-id {orchestrator.run_id}")

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted - cleaning up...")
        await orchestrator.destroy_workers()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n⚠️  Attempting cleanup...")
        try:
            await orchestrator.destroy_workers()
        except:
            pass
        sys.exit(1)
    finally:
        if controller_task and not controller_task.done():
            controller_task.cancel()


async def cmd_status(args):
    """Execute status command - check benchmark run status"""
    import aiohttp

    url = f"{args.controller_url}/api/status"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    print(f"📊 Controller Status")
                    print(f"   Run ID: {data.get('run_id', 'N/A')}")
                    print()

                    queue = data.get('queue_status', {})
                    print(f"📋 Task Queue:")
                    print(f"   Total: {queue.get('total_enqueued', 0)}")
                    print(f"   Queued: {queue.get('queued', 0)}")
                    print(f"   Running: {queue.get('pending', 0)}")
                    print(f"   Completed: {queue.get('completed', 0)}")
                    print(f"   Failed: {queue.get('failed', 0)}")
                    print(f"   Progress: {queue.get('completion_rate', 0)*100:.1f}%")
                    print()

                    workers = data.get('worker_stats', {})
                    print(f"🤖 Workers:")
                    print(f"   Total: {workers.get('total_workers', 0)}")
                    print(f"   Idle: {workers.get('idle', 0)}")
                    print(f"   Busy: {workers.get('busy', 0)}")
                    print(f"   Offline: {workers.get('offline', 0)}")
                    print(f"   Tasks completed: {workers.get('total_tasks_completed', 0)}")
                    print(f"   Tasks failed: {workers.get('total_tasks_failed', 0)}")
                else:
                    print(f"❌ Failed to get status: {resp.status}")
                    sys.exit(1)
    except Exception as e:
        print(f"❌ Error connecting to controller: {e}")
        sys.exit(1)


def cmd_cleanup(args):
    """Execute cleanup command - same as destroy"""
    cmd_destroy(args)


def main():
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "local":
            asyncio.run(cmd_local(args))
        elif args.command == "controller":
            asyncio.run(cmd_controller(args))
        elif args.command == "worker":
            asyncio.run(cmd_worker(args))
        elif args.command == "dispatch":
            asyncio.run(cmd_dispatch(args))
        elif args.command == "status":
            asyncio.run(cmd_status(args))
        elif args.command == "cleanup":
            cmd_cleanup(args)
        elif args.command == "run":
            asyncio.run(cmd_run(args))
        elif args.command == "provision":
            asyncio.run(cmd_provision(args))
        elif args.command == "destroy":
            cmd_destroy(args)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
