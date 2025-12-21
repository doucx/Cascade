import sys
import importlib.metadata
from typing import Any, Dict, Protocol


class LazyFactory(Protocol):
    """
    Protocol for objects that can serve as task factories (must support .map).
    """

    def map(self, **kwargs) -> Any: ...
    def __call__(self, *args, **kwargs) -> Any: ...


class Provider(Protocol):
    """
    Interface that all Cascade providers must implement.
    """

    @property
    def name(self) -> str:
        """The name of the provider, used as the accessor (e.g., 'shell' -> cs.shell)."""
        ...

    def create_factory(self) -> LazyFactory:
        """Returns the factory function/object to be exposed to the user."""
        ...


class ProviderNamespace:
    """
    A proxy object to handle nested provider names (e.g. cs.read.text).
    """

    def __init__(self, registry: "ProviderRegistry", prefix: str):
        self._registry = registry
        self._prefix = prefix

    def __getattr__(self, name: str) -> Any:
        full_name = f"{self._prefix}.{name}"
        return self._registry.get(full_name)


class ProviderRegistry:
    """
    Manages the discovery and loading of Cascade providers.
    """

    _instance = None

    def __init__(self):
        self._providers: Dict[str, LazyFactory] = {}
        self._loaded = False

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get(self, name: str) -> Any:
        """
        Retrieves a provider factory by name. Loads from entry points if not yet loaded.
        Raises AttributeError if not found (to conform with __getattr__ semantics).
        """
        if not self._loaded:
            self._discover_entry_points()
            self._loaded = True

        if name in self._providers:
            return self._providers[name]

        # Check for namespace match (e.g. asking for 'read' when 'read.text' exists)
        prefix = name + "."
        if any(key.startswith(prefix) for key in self._providers):
            return ProviderNamespace(self, name)

        raise AttributeError(f"Cascade provider '{name}' not found.")

    def register(self, name: str, factory: LazyFactory):
        """Manually register a factory (mostly for testing or internal use)."""
        self._providers[name] = factory

    def _discover_entry_points(self):
        """Scans the 'cascade.providers' entry point group."""
        if sys.version_info >= (3, 10):
            entry_points = importlib.metadata.entry_points(group="cascade.providers")
        else:
            entry_points = importlib.metadata.entry_points().get(
                "cascade.providers", []
            )

        for ep in entry_points:
            try:
                # Load the provider class
                provider_cls = ep.load()
                # Instantiate it
                provider_instance = provider_cls()
                # Validate interface
                if not hasattr(provider_instance, "create_factory") or not hasattr(
                    provider_instance, "name"
                ):
                    print(
                        f"Warning: Plugin {ep.name} does not implement Provider protocol. Skipping."
                    )
                    continue

                # Register
                self._providers[provider_instance.name] = (
                    provider_instance.create_factory()
                )
            except Exception as e:
                print(f"Error loading plugin {ep.name}: {e}")


# Global registry accessor
registry = ProviderRegistry.instance()
