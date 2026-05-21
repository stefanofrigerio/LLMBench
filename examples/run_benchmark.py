"""
Example script to run a full benchmark
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llmbench.models.ollama import OllamaModel
from llmbench.models.base import ModelConfig
from llmbench.capabilities.code_generation import CodeGenerationTest
from llmbench.runners.benchmark import BenchmarkRunner
from llmbench.storage.sqlite import SQLiteStorage
from llmbench.cube import Capability


async def main():
    print("🚀 LLMBench - Starting benchmark run\n")

    # Configure models to test
    models = [
        OllamaModel(
            ModelConfig(
                name="deepseek-coder-6.7b",
                provider="ollama",
                model_id="deepseek-coder:6.7b",
                temperature=0.2,
            )
        ),
        OllamaModel(
            ModelConfig(
                name="qwen2.5-coder-7b",
                provider="ollama",
                model_id="qwen2.5-coder:7b",
                temperature=0.2,
            )
        ),
        OllamaModel(
            ModelConfig(
                name="codellama-7b",
                provider="ollama",
                model_id="codellama:7b",
                temperature=0.2,
            )
        ),
    ]

    print("📋 Models configured:")
    for model in models:
        print(f"  - {model.name}")
    print()

    # Health check
    print("🏥 Running health checks...")
    for model in models:
        healthy = await model.health_check()
        status = "✅" if healthy else "❌"
        print(f"  {status} {model.name}")
    print()

    # Set up capability tests
    capability_tests = {
        Capability.CODE_GENERATION: CodeGenerationTest(),
    }

    print("🎯 Capabilities to test:")
    for cap in capability_tests.keys():
        print(f"  - {cap.value}")
    print()

    # Initialize storage
    storage = SQLiteStorage("results/benchmarks.db")

    # Run benchmarks
    print("⚡ Running benchmarks...\n")
    runner = BenchmarkRunner(models, capability_tests)
    results = await runner.run_full_benchmark()

    # Save results
    print("\n💾 Saving results to database...")
    storage.save_results(results)

    # Print summary
    print("\n📊 Benchmark Summary")
    print("=" * 60)

    for model in models:
        summary = storage.get_model_summary(model.name)
        if summary:
            print(f"\n{model.name}:")
            for row in summary:
                print(f"  {row['capability']:20} | "
                      f"Score: {row['avg_score']:.2f} | "
                      f"Latency: {row['avg_latency']:.0f}ms | "
                      f"Tests: {row['test_count']} | "
                      f"Errors: {row['error_count']}")

    # Test model selection
    print("\n\n🎯 Model Recommendations")
    print("=" * 60)

    test_points = [
        ("Simple code task", "code_generation", 2, 2),
        ("Complex code task", "code_generation", 4, 4),
        ("Critical code task", "code_generation", 3, 5),
    ]

    for label, cap, complexity, sensitivity in test_points:
        best = storage.get_best_model(cap, complexity, sensitivity, min_score=0.7)
        if best:
            print(f"\n{label} (complexity={complexity}, sensitivity={sensitivity}):")
            print(f"  ✅ Use: {best['model_name']}")
            print(f"     Score: {best['avg_score']:.2f} | "
                  f"Latency: {best['avg_latency']:.0f}ms | "
                  f"Samples: {best['sample_count']}")
        else:
            print(f"\n{label} (complexity={complexity}, sensitivity={sensitivity}):")
            print(f"  ⚠️  No model meets threshold - consider proprietary API")

    print("\n✅ Benchmark complete!")


if __name__ == "__main__":
    asyncio.run(main())
