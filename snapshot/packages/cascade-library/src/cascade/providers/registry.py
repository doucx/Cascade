from cascade.spec.protocols import LazyFactory, Provider
from .manager import ProviderRegistry, ProviderNamespace

__all__ = [
    "LazyFactory",
    "Provider",
    "registry",
    "ProviderRegistry",
    "ProviderNamespace",
]

# Global registry accessor
# Instantiated here to maintain singleton behavior for the module
registry = ProviderRegistry()