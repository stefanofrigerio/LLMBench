"""
Main benchmark runner
"""

import json
import time
from typing import List
from ..cube import BenchmarkPoint, BenchmarkResult, Capability
from ..models.base import BaseModel
from ..capabilities.base import CapabilityTest, TestCase


class BenchmarkRunner:
    """Runs benchmarks across the capability × complexity space"""

    def __init__(self, models: List[BaseModel], capability_tests: dict[Capability, CapabilityTest]):
        self.models = models
        self.capability_tests = capability_tests

    async def run_single_test(
        self,
        model: BaseModel,
        capability: Capability,
        test_case: TestCase,
    ) -> BenchmarkResult:
        """Run a single test case on a model"""

        point = BenchmarkPoint(
            capability=capability,
            complexity=test_case.complexity,
        )

        capability_test = self.capability_tests[capability]
        prompt = capability_test.build_prompt(test_case)

        try:
            start_time = time.perf_counter()
            # Use capability-level run() if defined (e.g. for vision/image inputs),
            # otherwise fall back to model.generate(prompt).
            if hasattr(capability_test, "run"):
                output = await capability_test.run(model, test_case)
            else:
                output = await model.generate(prompt)
            latency_ms = (time.perf_counter() - start_time) * 1000

            score = capability_test.evaluate(output, test_case.expected_output, test_case)

            # Serialise expected_output to string for storage (may be dict for JSON cases)
            expected_str = (
                json.dumps(test_case.expected_output, ensure_ascii=False)
                if isinstance(test_case.expected_output, (dict, list))
                else str(test_case.expected_output)
            )

            return BenchmarkResult(
                point=point,
                model_name=model.name,
                score=score,
                latency_ms=latency_ms,
                cost_estimate=self._estimate_cost(latency_ms, len(output)),
                raw_output=output,
                expected_output=expected_str,
                metadata=test_case.metadata,
            )

        except Exception as e:
            return BenchmarkResult(
                point=point,
                model_name=model.name,
                score=0.0,
                latency_ms=0.0,
                cost_estimate=0.0,
                error=str(e),
            )

    async def run_capability(
        self,
        model: BaseModel,
        capability: Capability,
    ) -> List[BenchmarkResult]:
        """Run all test cases for a capability on a model"""
        capability_test = self.capability_tests[capability]
        results = []
        for test_case in capability_test.get_test_cases():
            result = await self.run_single_test(model, capability, test_case)
            results.append(result)
        return results

    async def run_full_benchmark(self) -> List[BenchmarkResult]:
        """Run all benchmarks for all models and capabilities"""
        all_results = []

        for model in self.models:
            print(f"Benchmarking model: {model.name}")

            if not await model.health_check():
                print(f"  Model {model.name} failed health check, skipping")
                continue

            for capability in self.capability_tests.keys():
                print(f"  Running {capability.value} tests...")
                results = await self.run_capability(model, capability)
                all_results.extend(results)

        return all_results

    def _estimate_cost(self, latency_ms: float, output_length: int) -> float:
        return (latency_ms / 1000) * (output_length / 1000)
