"""
Central registry mapping Capability enum values to their test implementations.

To add a new capability:
  1. Create src/llmbench/capabilities/your_capability.py with a class extending
     CapabilityTest (or GroundTruthCapabilityTest for manifest-based ground truth).
  2. Add the value to the Capability enum in src/llmbench/cube.py.
  3. Add one line to REGISTRY below:
       Capability.YOUR_CAPABILITY: YourCapabilityTest,
  That's it — the CLI and dashboard pick it up automatically.
"""

from ..cube import Capability
from .base import CapabilityTest
from .code_generation import CodeGenerationTest
from .invoice_extractor import InvoiceExtractorTest

# ── Add new capabilities here ────────────────────────────────────────────────
REGISTRY: dict[Capability, type[CapabilityTest]] = {
    Capability.CODE_GENERATION: CodeGenerationTest,
    Capability.INVOICE_EXTRACTOR: InvoiceExtractorTest,
}
# ─────────────────────────────────────────────────────────────────────────────


def get_capability_test(capability: Capability) -> CapabilityTest:
    """Return a fresh instance of the test class for the given capability."""
    if capability not in REGISTRY:
        raise ValueError(
            f"No test implementation for capability '{capability.value}'. "
            f"Available: {list_capabilities()}"
        )
    return REGISTRY[capability]()


def list_capabilities() -> list[str]:
    """Return capability names that have a registered test implementation."""
    return [cap.value for cap in REGISTRY]
