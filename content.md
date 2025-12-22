# [WIP] refactor(engine): 提取 `ResourceContainer` 以分离资源管理职责

### 用户需求
将 `cascade.runtime.engine.Engine` 类中负责资源定义管理、依赖扫描、实例化及生命周期管理的逻辑，提取到一个独立的 `ResourceContainer` 类中，以减轻 `Engine` 的职责负担。

### 评论
资源管理是一个具有独立状态（资源定义表）和复杂行为（递归依赖解析、基于作用域的生命周期管理）的子系统。将其从 `Engine` 中剥离不仅符合单一职责原则，还能显著简化 `Engine` 的核心调度循环。

### 目标
1.  创建 `cascade.runtime.resource_container.ResourceContainer` 类。
2.  将以下功能从 `Engine` 迁移至新类：
    *   资源定义的注册与存储 (`_resource_providers`)。
    *   依赖扫描 (`_scan_for_resources`)。
    *   资源实例化与堆栈管理 (`_setup_resources`)。
    *   资源销毁 (`_teardown_resource`)。
3.  重构 `Engine` 以使用 `ResourceContainer`。

### 基本原理
`ResourceContainer` 将接管所有与 `@cs.resource` 相关的操作。`Engine` 仅保留对 `ResourceContainer` 的引用，并在 `run` 方法的适当生命周期点（如初始化前、步骤执行前）委托其进行资源的准备工作。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/engine #scope/core #ai/instruct #task/domain/runtime #task/object/engine #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建 `ResourceContainer` 类

我们将创建一个新的模块 `cascade.runtime.resource_container`，并将资源管理逻辑封装其中。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/resource_container.py
~~~~~
~~~~~python
import inspect
from contextlib import ExitStack
from typing import Any, Dict, Callable, Union, Generator, Set, Optional

from cascade.graph.model import Graph
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import ResourceAcquired, ResourceReleased


class ResourceContainer:
    """
    Manages the lifecycle, registration, and dependency injection of resources.
    """

    def __init__(self, bus: MessageBus):
        self.bus = bus
        self._resource_providers: Dict[str, Union[Callable, ResourceDefinition]] = {}

    def register(self, resource_def: ResourceDefinition):
        """Registers a resource definition."""
        self._resource_providers[resource_def.name] = resource_def

    def get_provider(self, name: str) -> Callable:
        """Retrieves the raw provider function for a resource."""
        provider = self._resource_providers[name]
        if isinstance(provider, ResourceDefinition):
            return provider.func
        return provider

    def override_provider(self, name: str, new_provider: Any):
        """Overrides a resource provider (useful for testing)."""
        self._resource_providers[name] = new_provider

    def scan(self, graph: Graph) -> Set[str]:
        """
        Scans the graph to identify all resources required by the nodes.
        """
        required = set()
        for node in graph.nodes:
            for value in node.literal_inputs.values():
                if isinstance(value, Inject):
                    required.add(value.resource_name)

            if node.signature:
                for param in node.signature.parameters.values():
                    if isinstance(param.default, Inject):
                        required.add(param.default.resource_name)
            elif node.callable_obj:
                sig = inspect.signature(node.callable_obj)
                for param in sig.parameters.values():
                    if isinstance(param.default, Inject):
                        required.add(param.default.resource_name)
        return required

    def setup(
        self,
        required_names: Set[str],
        active_resources: Dict[str, Any],
        run_stack: ExitStack,
        step_stack: ExitStack,
        run_id: str,
    ) -> None:
        """
        Initializes required resources that are not yet active.
        Decides whether to put them in run_stack or step_stack based on scope.
        Updates active_resources in-place.
        """

        def get_or_create(name: str):
            if name in active_resources:
                return active_resources[name]

            provider_entry = self._resource_providers.get(name)
            if not provider_entry:
                raise NameError(f"Resource '{name}' is required but not registered.")

            # Determine scope and func
            scope = "run"
            func = provider_entry
            if isinstance(provider_entry, ResourceDefinition):
                scope = provider_entry.scope
                func = provider_entry.func

            # Recursive dependency resolution
            sig = inspect.signature(func)
            deps = {
                p_name: get_or_create(p.default.resource_name)
                for p_name, p in sig.parameters.items()
                if isinstance(p.default, Inject)
            }

            # Instantiate
            gen = func(**deps)
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
~~~~~

#### Acts 2: 重构 `Engine` 类

移除 `Engine` 中相应的代码，并转而调用 `ResourceContainer`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.adapters.state import InMemoryStateBackend
from cascade.graph.compiler import BlueprintBuilder
from cascade.runtime.vm import VirtualMachine
from cascade.runtime.processor import NodeProcessor


class Engine:
~~~~~
~~~~~python
from cascade.adapters.state import InMemoryStateBackend
from cascade.graph.compiler import BlueprintBuilder
from cascade.runtime.vm import VirtualMachine
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.resource_container import ResourceContainer


class Engine:
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        self._wakeup_event = asyncio.Event()
        self.constraint_manager.set_wakeup_callback(self._wakeup_event.set)

        self._resource_providers: Dict[str, Union[Callable, ResourceDefinition]] = {}

        # Delegate node execution logic to NodeProcessor
        self.node_processor = NodeProcessor(
~~~~~
~~~~~python
        self._wakeup_event = asyncio.Event()
        self.constraint_manager.set_wakeup_callback(self._wakeup_event.set)

        self.resource_container = ResourceContainer(self.bus)

        # Delegate node execution logic to NodeProcessor
        self.node_processor = NodeProcessor(
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def register(self, resource_def: ResourceDefinition):
        # We store the full ResourceDefinition to preserve metadata like scope.
        self._resource_providers[resource_def.name] = resource_def

    def _is_simple_task(self, lr: Any) -> bool:
        """
        Checks if the LazyResult is a simple, flat task (no nested dependencies).
        This allows for the Zero-Overhead TCO fast path.
        """
~~~~~
~~~~~python
    def register(self, resource_def: ResourceDefinition):
        self.resource_container.register(resource_def)

    def _is_simple_task(self, lr: Any) -> bool:
        """
        Checks if the LazyResult is a simple, flat task (no nested dependencies).
        This allows for the Zero-Overhead TCO fast path.
        """
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def get_resource_provider(self, name: str) -> Callable:
        provider = self._resource_providers[name]
        if isinstance(provider, ResourceDefinition):
            return provider.func
        return provider

    def override_resource_provider(self, name: str, new_provider: Any):
        # When overriding, we might lose metadata if a raw function is passed,
        # but that's acceptable for testing overrides.
        self._resource_providers[name] = new_provider

    async def run(
        self, target: Any, params: Optional[Dict[str, Any]] = None, use_vm: bool = False
    ) -> Any:
~~~~~
~~~~~python
    def get_resource_provider(self, name: str) -> Callable:
        return self.resource_container.get_provider(name)

    def override_resource_provider(self, name: str, new_provider: Any):
        self.resource_container.override_provider(name, new_provider)

    async def run(
        self, target: Any, params: Optional[Dict[str, Any]] = None, use_vm: bool = False
    ) -> Any:
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                        self._graph_cache[struct_hash] = (graph, plan)

                        # 2. Setup Resources (mixed scope)
                        required_resources = self._scan_for_resources(graph)
                        self._setup_resources(
                            required_resources,
                            active_resources,
                            run_stack,
                            step_stack,
                            run_id,
                        )

                        # 3. Execute
                        result = await self._execute_graph(
~~~~~
~~~~~python
                        self._graph_cache[struct_hash] = (graph, plan)

                        # 2. Setup Resources (mixed scope)
                        required_resources = self.resource_container.scan(graph)
                        self.resource_container.setup(
                            required_resources,
                            active_resources,
                            run_stack,
                            step_stack,
                            run_id,
                        )

                        # 3. Execute
                        result = await self._execute_graph(
~~~~~

#### Acts 3: 移除 `Engine` 中已废弃的资源管理方法

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def _update_graph_literals(
        self, graph: Graph, target: Any, literals: Dict[str, Any]
    ):
        """Injects new literal values and UUID into a cached graph."""
        # A simple graph has a predictable structure we can update directly.
        # This assumes a single root node for the target.
        node_map = {node.id: node for node in graph.nodes}

        # This is a bit of a simplification. A full implementation would need to
        # traverse the target structure and map literals back to the graph nodes.
        # For now, let's assume the root node gets the new literals.
        # The most important part is updating the target's UUID.

        # Find the node corresponding to the target LazyResult
        # In a cached graph, the ID is stale, so we find it by name or type.
        # For now, we assume the last node is the target node.
        if graph.nodes:
            target_node = graph.nodes[-1]
            target_node.id = target._uuid
            # This is a simplification; a robust solution would traverse and update.
            # For firefly, the structure is so simple this may be sufficient.
            if hasattr(target, "args") and hasattr(target, "kwargs"):
                target_node.literal_inputs = {
                    str(i): v for i, v in enumerate(target.args)
                }
                target_node.literal_inputs.update(target.kwargs)

    async def _execute_graph(
~~~~~
~~~~~python
    def _update_graph_literals(
        self, graph: Graph, target: Any, literals: Dict[str, Any]
    ):
        """Injects new literal values and UUID into a cached graph."""
        # A simple graph has a predictable structure we can update directly.
        # This assumes a single root node for the target.
        node_map = {node.id: node for node in graph.nodes}

        # This is a bit of a simplification. A full implementation would need to
        # traverse the target structure and map literals back to the graph nodes.
        # For now, let's assume the root node gets the new literals.
        # The most important part is updating the target's UUID.

        # Find the node corresponding to the target LazyResult
        # In a cached graph, the ID is stale, so we find it by name or type.
        # For now, we assume the last node is the target node.
        if graph.nodes:
            target_node = graph.nodes[-1]
            target_node.id = target._uuid
            # This is a simplification; a robust solution would traverse and update.
            # For firefly, the structure is so simple this may be sufficient.
            if hasattr(target, "args") and hasattr(target, "kwargs"):
                target_node.literal_inputs = {
                    str(i): v for i, v in enumerate(target.args)
                }
                target_node.literal_inputs.update(target.kwargs)

    async def _execute_graph(
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        return state_backend.get_result(target._uuid)

    def _scan_for_resources(self, graph: Graph) -> set[str]:
        required = set()
        for node in graph.nodes:
            for value in node.literal_inputs.values():
                if isinstance(value, Inject):
                    required.add(value.resource_name)

            if node.signature:
                for param in node.signature.parameters.values():
                    if isinstance(param.default, Inject):
                        required.add(param.default.resource_name)
            elif node.callable_obj:
                sig = inspect.signature(node.callable_obj)
                for param in sig.parameters.values():
                    if isinstance(param.default, Inject):
                        required.add(param.default.resource_name)
        return required

    def _setup_resources(
        self,
        required_names: set[str],
        active_resources: Dict[str, Any],
        run_stack: ExitStack,
        step_stack: ExitStack,
        run_id: str,
    ) -> None:
        """
        Initializes required resources that are not yet active.
        Decides whether to put them in run_stack or step_stack based on scope.
        Updates active_resources in-place.
        """

        def get_or_create(name: str):
            if name in active_resources:
                return active_resources[name]

            provider_entry = self._resource_providers.get(name)
            if not provider_entry:
                raise NameError(f"Resource '{name}' is required but not registered.")

            # Determine scope and func
            scope = "run"
            func = provider_entry
            if isinstance(provider_entry, ResourceDefinition):
                scope = provider_entry.scope
                func = provider_entry.func

            # Recursive dependency resolution
            sig = inspect.signature(func)
            deps = {
                p_name: get_or_create(p.default.resource_name)
                for p_name, p in sig.parameters.items()
                if isinstance(p.default, Inject)
            }

            # Instantiate
            gen = func(**deps)
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
~~~~~
~~~~~python
        return state_backend.get_result(target._uuid)
~~~~~

### 下一步建议
通过提取 `ResourceContainer`，`Engine` 的代码行数进一步减少，职责更加聚焦于调度。
接下来，我们可以开始执行 **路线 3: VM 与图执行分离**。我们将定义一个 `ExecutionStrategy` 协议，并实现 `GraphExecutionStrategy` 和 `VMExecutionStrategy`，彻底清理 `Engine` 中的 `if use_vm:` 分支。
