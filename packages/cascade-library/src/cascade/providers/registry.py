from cascade.spec.runtime.interfaces import LazyFactory, Provider

from .manager import ProviderNamespace, ProviderRegistry

__all__ = [
    "LazyFactory",
    "Provider",
    "ProviderNamespace",
    "ProviderRegistry",
    "registry",
]

# Global registry accessor
# Instantiated here to maintain singleton behavior for the module
registry = ProviderRegistry()
