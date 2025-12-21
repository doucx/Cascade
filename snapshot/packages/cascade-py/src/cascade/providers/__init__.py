# This allows 'cascade.providers' to be a namespace package,
# extended by other installed packages (like cascade-provider-ipfs).
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# We expose the core protocols for convenience, but implementation lives in registry.py
from .registry import LazyFactory, Provider, registry

__all__ = ["LazyFactory", "Provider", "registry"]