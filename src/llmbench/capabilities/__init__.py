"""
Central registry mapping Capability enum values to their test implementations.
Import get_capability_test() wherever you need to instantiate a capability by name.
"""

from ..cube import Capability
from .base import CapabilityTest


def get_capability_test(capability: Capability) -> CapabilityTest:
    """Return a fresh instance of the test class for the given capability."""
    from .code_generation import CodeGenerationTest
    from .invoice_extractor import InvoiceExtractorTest

    registry: dict[Capability, type[CapabilityTest]] = {
        Capability.CODE_GENERATION: CodeGenerationTest,
        Capability.INVOICE_EXTRACTOR: InvoiceExtractorTest,
    }

    if capability not in registry:
        raise ValueError(
            f"No test implementation for capability '{capability.value}'. "
            f"Available: {[c.value for c in registry]}"
        )

    return registry[capability]()


def list_capabilities() -> list[str]:
    """Return capability names that have a registered test implementation."""
    from .code_generation import CodeGenerationTest  # noqa: F401
    from .invoice_extractor import InvoiceExtractorTest  # noqa: F401

    return [
        Capability.CODE_GENERATION.value,
        Capability.INVOICE_EXTRACTOR.value,
    ]
