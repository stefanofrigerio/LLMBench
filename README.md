# LLMBench

A comprehensive benchmarking system for evaluating open-source LLMs across three dimensions: **Capability**, **Complexity**, and **Sensitivity**.

## The Cube Model

LLMBench uses a 3D cube model to map which open-source model is suitable for replacing proprietary models (Claude, GPT-4, Gemini) for specific tasks:

```
        Sensitivity (1-5)
              ↑
              |
              |
        5 ----+---- Critical
        4     |     High
        3     |     Medium
        2     |     Minor  
        1     |     Low
              |
              +------------→ Complexity (1-5)
             /              1:Trivial → 5:Expert
            /
           /
    Capability
    (code_generation, ocr, reasoning, etc.)
```

### The Three Dimensions

#### 1. Capability (What to do)
- **code_generation**: Generate functional code from descriptions
- **unit_test_writing**: Write comprehensive test suites
- **ocr**: Extract text from images
- **text_summarization**: Create concise summaries
- **data_transformation**: Convert between data formats
- **reasoning**: Multi-step logical problem solving
- **structured_output**: Generate valid JSON/YAML/etc
- **translation**: Translate between languages

#### 2. Complexity (How hard)
- **1 - Trivial**: Simple, obvious tasks (e.g., reverse a string)
- **2 - Simple**: Basic knowledge required (e.g., check if prime)
- **3 - Moderate**: Multiple steps needed (e.g., merge sort)
- **4 - Complex**: Advanced understanding (e.g., LRU cache)
- **5 - Expert**: Deep expertise required (e.g., TSP solver)

#### 3. Sensitivity (How critical)
- **1 - Low**: Minimal impact if wrong (e.g., log typo)
- **2 - Minor**: Noticeable but not critical (e.g., UI text)
- **3 - Medium**: Affects functionality (e.g., report generation)
- **4 - High**: Could cause significant issues (e.g., auth logic)
- **5 - Critical**: Severe consequences if wrong (e.g., financial transactions)

### Example Use Cases

| Task | Capability | Complexity | Sensitivity | Example |
|------|-----------|-----------|------------|---------|
| Fold a t-shirt (robot) | physical_manipulation | 4 | 1 | Complex task, but low risk |
| Launch a missile | button_pressing | 1 | 5 | Simple task, but critical consequences |
| Generate invoice | data_transformation | 3 | 5 | Moderate complexity, high sensitivity |
| Write tests for utils | unit_test_writing | 2 | 2 | Simple and low risk |

## Installation

```bash
# Clone the repository
git clone git@github.com:stefanofrigerio/LLMBench.git
cd LLMBench

# Install dependencies
pip install -e .

# For development
pip install -e ".[dev]"
```

## Prerequisites

### Ollama Setup
LLMBench uses Ollama to run local open-source models:

```bash
# Install Ollama
# Visit https://ollama.ai for installation instructions

# Pull some models
ollama pull deepseek-coder:6.7b
ollama pull qwen2.5-coder:7b
ollama pull llama3.1:8b
ollama pull mistral:7b
```

## Usage

### Running Benchmarks

```python
import asyncio
from llmbench.models.ollama import OllamaModel
from llmbench.models.base import ModelConfig
from llmbench.capabilities.code_generation import CodeGenerationTest
from llmbench.runners.benchmark import BenchmarkRunner
from llmbench.storage.sqlite import SQLiteStorage
from llmbench.cube import Capability

# Configure models
models = [
    OllamaModel(ModelConfig(
        name="deepseek-coder",
        provider="ollama",
        model_id="deepseek-coder:6.7b",
        temperature=0.2
    )),
    OllamaModel(ModelConfig(
        name="qwen2.5-coder",
        provider="ollama",
        model_id="qwen2.5-coder:7b",
        temperature=0.2
    )),
]

# Set up capability tests
capability_tests = {
    Capability.CODE_GENERATION: CodeGenerationTest(),
}

# Run benchmarks
runner = BenchmarkRunner(models, capability_tests)
results = await runner.run_full_benchmark()

# Store results
storage = SQLiteStorage()
storage.save_results(results)

# Query best model for specific task
best = storage.get_best_model(
    capability="code_generation",
    complexity=3,
    sensitivity=4,
    min_score=0.8
)
print(f"Best model: {best['model_name']} (score: {best['avg_score']:.2f})")
```

### Finding the Right Model

```python
from llmbench.storage.sqlite import SQLiteStorage

storage = SQLiteStorage()

# Find best model for: moderate complexity, high sensitivity code generation
best = storage.get_best_model(
    capability="code_generation",
    complexity=3,
    sensitivity=4,
    min_score=0.8
)

if best:
    print(f"Use {best['model_name']}")
    print(f"  Score: {best['avg_score']:.2f}")
    print(f"  Latency: {best['avg_latency']:.0f}ms")
    print(f"  Cost: {best['avg_cost']:.4f}")
else:
    print("No model meets threshold - use proprietary API")
```

## Configuration

### Models (`config/models.yaml`)
Define which models to benchmark:

```yaml
models:
  - name: "deepseek-coder"
    provider: "ollama"
    model_id: "deepseek-coder:6.7b"
    temperature: 0.2
    max_tokens: 2048
```

### Capabilities (`config/capabilities.yaml`)
Define evaluation criteria and thresholds for each capability.

## Project Structure

```
LLMBench/
├── src/llmbench/
│   ├── cube.py              # Core 3D model definitions
│   ├── models/
│   │   ├── base.py          # Model interface
│   │   └── ollama.py        # Ollama implementation
│   ├── capabilities/
│   │   ├── base.py          # Capability test interface
│   │   └── code_generation.py
│   ├── runners/
│   │   └── benchmark.py     # Main benchmark runner
│   └── storage/
│       └── sqlite.py        # Results storage
├── config/
│   ├── models.yaml          # Model configurations
│   └── capabilities.yaml    # Capability definitions
├── tests/                   # Unit tests
├── data/                    # Test datasets
└── results/                 # Benchmark results (SQLite DB)
```

## Extending

### Adding a New Capability

1. Create a new test class in `src/llmbench/capabilities/`:

```python
from .base import CapabilityTest, TestCase

class MyCapabilityTest(CapabilityTest):
    def get_test_cases(self) -> list[TestCase]:
        return [...]
    
    def evaluate(self, output: str, expected: Any, test_case: TestCase) -> float:
        # Return score 0-1
        return score
    
    def build_prompt(self, test_case: TestCase) -> str:
        return f"..."
```

2. Add to `Capability` enum in `cube.py`
3. Register in your runner

### Adding a New Model Provider

Implement the `BaseModel` interface:

```python
from llmbench.models.base import BaseModel, ModelConfig

class MyProviderModel(BaseModel):
    async def generate(self, prompt: str, **kwargs) -> str:
        # Call your API
        pass
    
    async def health_check(self) -> bool:
        # Check availability
        pass
```

## Roadmap

- [ ] Add more capability tests (OCR, reasoning, translation)
- [ ] Web dashboard for visualizing the cube
- [ ] Cost tracking (actual vs proprietary APIs)
- [ ] Support for more providers (OpenAI, Anthropic for comparison)
- [ ] Automated threshold tuning
- [ ] Model recommendation engine
- [ ] Export results to various formats

## Contributing

Contributions welcome! Especially:
- New capability tests
- Better evaluation metrics
- Model provider integrations
- Visualization tools

## License

MIT
