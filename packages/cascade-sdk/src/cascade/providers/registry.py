import sys
import importlib.metadata
from typing import Any, Dict, Protocol


class LazyFactory(Protocol):
    def map(self, **kwargs) -> Any: ...
    def __call__(self, *args, **kwargs) -> Any: ...


class Provider(Protocol):
    @property
    def name(self) -> str: ...

    def create_factory(self) -> LazyFactory: ...


class ProviderNamespace:
    def __init__(self, registry: "ProviderRegistry", prefix: str):
        self._registry = registry
        self._prefix = prefix

    def __getattr__(self, name: str) -> Any:
        full_name = f"{self._prefix}.{name}"
        return self._registry.get(full_name)


class ProviderRegistry:
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
        self._providers[name] = factory

    def _discover_entry_points(self):
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
