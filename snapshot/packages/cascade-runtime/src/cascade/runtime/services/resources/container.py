import inspect
from contextlib import ExitStack
from typing import Any, Dict, Callable, Union, Generator, Set

from cascade.graph.model import Graph
from cascade.spec.resource import ResourceDefinition, Inject
from contextlib import contextmanager

from cascade.runtime.services.observability.bus import EventBus
from cascade.runtime.services.observability.events import ResourceAcquired, ResourceReleased


class ResourceContainer:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self._resource_providers: Dict[str, Union[Callable, ResourceDefinition]] = {}

    def register(self, resource_def: ResourceDefinition):
        self._resource_providers[resource_def.name] = resource_def

    def get_provider(self, name: str) -> Callable:
        provider = self._resource_providers[name]
        if isinstance(provider, ResourceDefinition):
            return provider.func
        return provider

    def override_provider(self, name: str, new_provider: Any):
        self._resource_providers[name] = new_provider

    @contextmanager
    def override(self, name: str, new_provider: Any) -> Generator[None, None, None]:
        original = self._resource_providers.get(name)
        self.override_provider(name, new_provider)
        try:
            yield
        finally:
            if original is not None:
                self.override_provider(name, original)
            else:
                self._resource_providers.pop(name, None)

    def scan(self, graph: Graph, executable_registry: Dict[str, Callable]) -> Set[str]:
        required = set()

        # 1. Scan Node Input Bindings for explicit Inject objects
        for node in graph.nodes:
            for value in node.input_bindings.values():
                self._scan_item(value, required)

        # 2. Scan Node Signatures for Inject defaults
        for node in graph.nodes:
            callable_obj = executable_registry.get(node.current_node_instance_hash)
            if callable_obj:
                try:
                    # Inspect the callable object directly
                    obj_to_inspect: Any = callable_obj
                    sig = inspect.signature(obj_to_inspect)
                    for param in sig.parameters.values():
                        if isinstance(param.default, Inject):
                            required.add(param.default.resource_name)
                except (ValueError, TypeError):
                    pass
        return required

    def _scan_item(self, item: Any, required: Set[str]):
        if isinstance(item, Inject):
            required.add(item.resource_name)
        elif isinstance(item, (list, tuple)):
            for sub in item:
                self._scan_item(sub, required)
        elif isinstance(item, dict):
            for sub in item.values():
                self._scan_item(sub, required)

    def setup(
        self,
        required_names: Set[str],
        active_resources: Dict[str, Any],
        run_stack: ExitStack,
        step_stack: ExitStack,
        run_id: str,
    ) -> None:
        def get_or_create(name: str):
            if name in active_resources:
                return active_resources[name]

            provider_entry = self._resource_providers.get(name)
            if not provider_entry:
                raise NameError(f"Resource '{name}' is required but not registered.")

            # Determine scope and the actual provider function
            scope = "run"
            provider_func: Callable
            if isinstance(provider_entry, ResourceDefinition):
                scope = provider_entry.scope
                provider_func = provider_entry.func
            else:
                # It's a raw callable, likely for testing or simple cases
                provider_func = provider_entry

            # Recursive dependency resolution
            sig = inspect.signature(provider_func)
            deps = {
                p_name: get_or_create(p.default.resource_name)
                for p_name, p in sig.parameters.items()
                if isinstance(p.default, Inject)
            }

            # Instantiate using the explicitly resolved function
            gen = provider_func(**deps)
            instance = next(gen)

            # Register in active dict
            active_resources[name] = instance
            self.bus.publish(ResourceAcquired(run_id=run_id, resource_name=name))

            # Register teardown in appropriate stack
            target_stack = step_stack if scope == "task" else run_stack

            def cleanup():
                self._teardown_resource(gen, run_id, name)
                # Important: remove from active_resources so it can be re-created if needed later
                active_resources.pop(name, None)

            target_stack.callback(cleanup)
            return instance

        for name in required_names:
            get_or_create(name)

    def _teardown_resource(self, gen: Generator, run_id: str, resource_name: str):
        try:
            next(gen)
        except StopIteration:
            self.bus.publish(
                ResourceReleased(run_id=run_id, resource_name=resource_name)
            )
