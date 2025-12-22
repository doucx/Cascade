# [WIP] refactor(engine): 实施策略模式以分离 Graph 和 VM 执行逻辑

### 用户需求
将 `Engine` 类中基于图的执行逻辑（TCO 循环、图构建、资源扫描）和基于 VM 的执行逻辑（Blueprints、VM 实例化）拆分为两个独立的策略类：`GraphExecutionStrategy` 和 `VMExecutionStrategy`。

### 评论
当前 `Engine` 通过 `if use_vm:` 分支硬编码了两种截然不同的执行路径。随着 VM 模式的演进，这种耦合会越来越难以维护。通过策略模式，我们可以将每种执行模型的复杂性封装在各自的类中，使 `Engine` 回归到“工作流协调者”的本位。

### 目标
1.  创建 `cascade.runtime.strategies` 模块。
2.  定义 `ExecutionStrategy` 协议。
3.  实现 `GraphExecutionStrategy`，迁移原 `Engine` 中的 TCO 循环、图缓存和 `_execute_graph` 逻辑。
4.  实现 `VMExecutionStrategy`，迁移原 `Engine` 中的 `_run_vm` 逻辑。
5.  重构 `Engine` 以根据参数选择策略并委托执行。

### 基本原理
`Engine` 负责通用的运行时环境设置（Run ID, Bus Events, Connector Connection, Global Resource Stack）。具体的执行流程（如何解析 Target，如何调度任务）委托给具体的 `ExecutionStrategy`。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/engine #scope/core #ai/instruct #task/domain/runtime #task/object/engine #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建策略模块与 `GraphExecutionStrategy`

我们将创建一个新文件 `packages/cascade-engine/src/cascade/runtime/strategies.py`。由于 `GraphExecutionStrategy` 需要引用 `Engine` 中的很多组件，我们需要理清依赖关系。它将依赖 `Solver`, `NodeProcessor`, `ResourceContainer` 等。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
import asyncio
from contextlib import ExitStack
from typing import Any, Dict, Protocol, Tuple, Optional, List, Callable

from cascade.graph.model import Graph
from cascade.graph.build import build_graph
from cascade.graph.hashing import StructuralHasher
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.bus import MessageBus
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.flow import FlowManager
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.events import TaskSkipped, TaskBlocked
from cascade.runtime.constraints.manager import ConstraintManager
from cascade.graph.compiler import BlueprintBuilder
from cascade.runtime.vm import VirtualMachine
from cascade.runtime.resource_manager import ResourceManager
from cascade.graph.model import Node


class ExecutionStrategy(Protocol):
    """
    Protocol defining a strategy for executing a workflow target.
    """

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        ...


class GraphExecutionStrategy:
    """
    Executes tasks by dynamically building a dependency graph and running a TCO loop.
    This is the standard execution mode for Cascade.
    """

    def __init__(
        self,
        solver: Solver,
        node_processor: NodeProcessor,
        resource_container: ResourceContainer,
        constraint_manager: ConstraintManager,
        bus: MessageBus,
        wakeup_event: asyncio.Event,
    ):
        self.solver = solver
        self.node_processor = node_processor
        self.resource_container = resource_container
        self.constraint_manager = constraint_manager
        self.bus = bus
        self.wakeup_event = wakeup_event
        self._graph_cache: Dict[str, Tuple[Graph, Any]] = {}

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        current_target = target

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                # 1. Get Graph and Plan, using Structural Hash Cache
                hasher = StructuralHasher()
                struct_hash, literals = hasher.hash(current_target)

                graph = None
                plan = None

                if struct_hash in self._graph_cache:
                    # CACHE HIT: Reuse graph and plan
                    cached_graph, cached_plan = self._graph_cache[struct_hash]
                    if len(cached_graph.nodes) > 1:
                        graph = build_graph(current_target)
                        plan = self.solver.resolve(graph)
                    else:
                        graph = cached_graph
                        plan = cached_plan
                        self._update_graph_literals(graph, current_target, literals)
                else:
                    # CACHE MISS: Build, solve, and cache
                    graph = build_graph(current_target)
                    plan = self.solver.resolve(graph)
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

                # 3. Execute Graph
                result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    plan,
                )

            # 4. Check for Tail Call (LazyResult)
            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
                # STATE GC
                if hasattr(state_backend, "clear"):
                    state_backend.clear()
                # Yield control
                await asyncio.sleep(0)
            else:
                return result

    def _update_graph_literals(
        self, graph: Graph, target: Any, literals: Dict[str, Any]
    ):
        # ... logic moved from Engine ...
        node_map = {node.id: node for node in graph.nodes}
        if graph.nodes:
            target_node = graph.nodes[-1]
            target_node.id = target._uuid
            if hasattr(target, "args") and hasattr(target, "kwargs"):
                target_node.literal_inputs = {
                    str(i): v for i, v in enumerate(target.args)
                }
                target_node.literal_inputs.update(target.kwargs)

    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
        graph: Graph,
        plan: Any,
    ) -> Any:
        flow_manager = FlowManager(graph, target._uuid)
        blocked_nodes = set()

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue

                    skip_reason = flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        state_backend.mark_skipped(node.id, skip_reason)
                        self.bus.publish(
                            TaskSkipped(
                                run_id=run_id,
                                task_id=node.id,
                                task_name=node.name,
                                reason=skip_reason,
                            )
                        )
                        continue

                    if self.constraint_manager.check_permission(node):
                        executable_this_pass.append(node)
                        if node.id in blocked_nodes:
                            blocked_nodes.remove(node.id)
                    else:
                        deferred_this_pass.append(node)
                        if node.id not in blocked_nodes:
                            self.bus.publish(
                                TaskBlocked(
                                    run_id=run_id,
                                    task_id=node.id,
                                    task_name=node.name,
                                    reason="ConstraintViolation",
                                )
                            )
                            blocked_nodes.add(node.id)

                if executable_this_pass:
                    # Callback for map nodes
                    async def sub_graph_runner(target, sub_params, parent_state):
                        sub_graph = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        return await self._execute_graph(
                            target,
                            sub_params,
                            active_resources,
                            run_id,
                            parent_state,
                            graph=sub_graph,
                            plan=sub_plan,
                        )

                    tasks_to_run = [
                        self.node_processor.process(
                            node,
                            graph,
                            state_backend,
                            active_resources,
                            run_id,
                            params,
                            sub_graph_runner,
                        )
                        for node in executable_this_pass
                    ]

                    pass_results = await asyncio.gather(*tasks_to_run)

                    for node, res in zip(executable_this_pass, pass_results):
                        state_backend.put_result(node.id, res)
                        if flow_manager:
                            flow_manager.register_result(node.id, res, state_backend)

                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
                    await self.wakeup_event.wait()
                    self.wakeup_event.clear()
                    self.constraint_manager.cleanup_expired_constraints()

        if not state_backend.has_result(target._uuid):
            if skip_reason := state_backend.get_skip_reason(target._uuid):
                raise DependencyMissingError(
                    task_id=target.task.name or "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target was skipped (Reason: {skip_reason})",
                )
            raise KeyError(
                f"Target task '{target.task.name if hasattr(target.task, 'name') else 'unknown'}' did not produce a result."
            )

        return state_backend.get_result(target._uuid)


class VMExecutionStrategy:
    """
    Executes tasks by compiling them into a Blueprint and running them on a Virtual Machine.
    """

    def __init__(
        self,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
    ):
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        # 1. Compile in template mode
        builder = BlueprintBuilder()
        blueprint = builder.build(target, template=True)

        # 2. Extract Initial Arguments
        initial_args = list(target.args)
        initial_kwargs = dict(target.kwargs)

        # 3. Execute
        vm = VirtualMachine(
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            wakeup_event=self.wakeup_event,
        )
        return await vm.execute(
            blueprint, initial_args=initial_args, initial_kwargs=initial_kwargs
        )
~~~~~

#### Acts 2: 重构 `Engine` 类以使用策略

现在我们将 `Engine` 中的复杂执行逻辑替换为对 Strategy 的委托。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.adapters.state import InMemoryStateBackend
from cascade.graph.compiler import BlueprintBuilder
from cascade.runtime.vm import VirtualMachine
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.resource_container import ResourceContainer


class Engine:
~~~~~
~~~~~python
from cascade.adapters.state import InMemoryStateBackend
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.strategies import GraphExecutionStrategy, VMExecutionStrategy


class Engine:
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        self.node_processor = NodeProcessor(
            executor=self.executor,
            bus=self.bus,
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            solver=self.solver,
        )
        
        self._managed_subscribers = []
        self._graph_cache: Dict[str, Tuple[Graph, Any]] = {}

    def add_subscriber(self, subscriber: Any):
~~~~~
~~~~~python
        self.node_processor = NodeProcessor(
            executor=self.executor,
            bus=self.bus,
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            solver=self.solver,
        )

        # Initialize Strategies
        self.graph_strategy = GraphExecutionStrategy(
            solver=self.solver,
            node_processor=self.node_processor,
            resource_container=self.resource_container,
            constraint_manager=self.constraint_manager,
            bus=self.bus,
            wakeup_event=self._wakeup_event,
        )

        self.vm_strategy = VMExecutionStrategy(
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            wakeup_event=self._wakeup_event,
        )
        
        self._managed_subscribers = []

    def add_subscriber(self, subscriber: Any):
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def run(
        self, target: Any, params: Optional[Dict[str, Any]] = None, use_vm: bool = False
    ) -> Any:
        # VM Fast Path
        if use_vm:
            return await self._run_vm(target)

        run_id = str(uuid4())
        start_time = time.time()
~~~~~
~~~~~python
    async def run(
        self, target: Any, params: Optional[Dict[str, Any]] = None, use_vm: bool = False
    ) -> Any:
        run_id = str(uuid4())
        start_time = time.time()
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
            # 2. Publish Lifecycle Event
            self.bus.publish(
                RunStarted(
                    run_id=run_id, target_tasks=[target_name], params=params or {}
                )
            )

            # TCO Loop: We keep executing as long as the result is a LazyResult
            current_target = target

            # The global stack holds "run" scoped resources
            with ExitStack() as run_stack:
                # Register the engine's connector as a special internal resource
                if self.connector:
                    from cascade.spec.resource import resource

                    @resource(name="_internal_connector", scope="run")
                    def _connector_provider():
                        yield self.connector

                    self.register(_connector_provider)

                active_resources: Dict[str, Any] = {}

                while True:
                    # The step stack holds "task" (step) scoped resources
                    with ExitStack() as step_stack:
                        # 1. Get Graph and Plan, using Structural Hash Cache
                        hasher = StructuralHasher()
                        struct_hash, literals = hasher.hash(current_target)

                        graph = None
                        plan = None

                        if struct_hash in self._graph_cache:
                            # CACHE HIT: Reuse graph and plan
                            cached_graph, cached_plan = self._graph_cache[struct_hash]

                            # LIMITATION: Current _update_graph_literals only supports single-node graphs correctly.
                            # For complex graphs, we must rebuild to ensure all UUIDs are correct.
                            if len(cached_graph.nodes) > 1:
                                graph = build_graph(current_target)
                                plan = self.solver.resolve(graph)
                            else:
                                graph = cached_graph
                                plan = cached_plan
                                self._update_graph_literals(
                                    graph, current_target, literals
                                )
                        else:
                            # CACHE MISS: Build, solve, and cache
                            graph = build_graph(current_target)
                            plan = self.solver.resolve(graph)
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
                            current_target,
                            params or {},
                            active_resources,
                            run_id,
                            state_backend,
                            graph=graph,
                            plan=plan,
                        )

                    # 4. Check for Tail Call (LazyResult)
                    if isinstance(result, (LazyResult, MappedLazyResult)):
                        current_target = result

                        # STATE GC: Since we are moving to a new generation (new graph),
                        # the transient state of the previous generation is no longer needed.
                        # We clear it to prevent memory leaks in infinite recursion.
                        if hasattr(state_backend, "clear"):
                            state_backend.clear()

                        # CRITICAL: Yield control to the event loop between TCO iterations.
                        # This allows other tasks (like the experiment timeout) to run.
                        await asyncio.sleep(0)
                    else:
                        final_result = result
                        break

            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(run_id=run_id, status="Succeeded", duration=duration)
            )
            return final_result

        except Exception as e:
~~~~~
~~~~~python
            # 2. Publish Lifecycle Event
            self.bus.publish(
                RunStarted(
                    run_id=run_id, target_tasks=[target_name], params=params or {}
                )
            )

            # 3. Select Strategy
            strategy = self.vm_strategy if use_vm else self.graph_strategy

            # 4. Execute
            # The global stack holds "run" scoped resources
            with ExitStack() as run_stack:
                # Register the engine's connector as a special internal resource
                if self.connector:
                    from cascade.spec.resource import resource

                    @resource(name="_internal_connector", scope="run")
                    def _connector_provider():
                        yield self.connector

                    self.register(_connector_provider)

                active_resources: Dict[str, Any] = {}

                final_result = await strategy.execute(
                    target=target,
                    run_id=run_id,
                    params=params or {},
                    state_backend=state_backend,
                    run_stack=run_stack,
                    active_resources=active_resources,
                )

            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(run_id=run_id, status="Succeeded", duration=duration)
            )
            return final_result

        except Exception as e:
~~~~~

#### Acts 3: 移除 `Engine` 中已废弃的代码

移除 `_run_vm`, `_update_graph_literals`, `_execute_graph` 等已迁移的方法。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def _run_vm(self, target: Any) -> Any:
        """
        Executes the target using the AOT Blueprint/VM path.
        """
        # 1. Compile in template mode
        builder = BlueprintBuilder()
        blueprint = builder.build(target, template=True)

        # 2. Extract Initial Arguments
        # The BlueprintBuilder treats the root LazyResult's args/kwargs as the
        # inputs for the blueprint.
        initial_args = list(target.args)
        initial_kwargs = dict(target.kwargs)

        # 3. Execute
        vm = VirtualMachine(
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            wakeup_event=self._wakeup_event,
        )
        return await vm.execute(
            blueprint, initial_args=initial_args, initial_kwargs=initial_kwargs
        )

    async def _on_constraint_update(self, topic: str, payload: Dict[str, Any]):
~~~~~
~~~~~python
    async def _on_constraint_update(self, topic: str, payload: Dict[str, Any]):
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        finally:
            # After any change (add, remove, or error), wake up the engine loop
            # if it's waiting.
            self._wakeup_event.set()

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
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
        graph: Graph,
        plan: Any,
    ) -> Any:
        flow_manager = FlowManager(graph, target._uuid)

        # Track blocked state locally to avoid spamming Blocked events every loop tick
        blocked_nodes = set()

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue  # Skip params, they don't execute

                    skip_reason = flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        state_backend.mark_skipped(node.id, skip_reason)
                        self.bus.publish(
                            TaskSkipped(
                                run_id=run_id,
                                task_id=node.id,
                                task_name=node.name,
                                reason=skip_reason,
                            )
                        )
                        # Node is resolved (skipped), so not pending for next pass
                        continue

                    if self.constraint_manager.check_permission(node):
                        executable_this_pass.append(node)
                        if node.id in blocked_nodes:
                            blocked_nodes.remove(node.id)
                    else:
                        deferred_this_pass.append(node)
                        if node.id not in blocked_nodes:
                            from cascade.runtime.events import TaskBlocked

                            self.bus.publish(
                                TaskBlocked(
                                    run_id=run_id,
                                    task_id=node.id,
                                    task_name=node.name,
                                    reason="ConstraintViolation",  # Detailed reason requires manager update
                                )
                            )
                            blocked_nodes.add(node.id)

                if executable_this_pass:
                    # Define a callback for map nodes to execute sub-workflows
                    async def sub_graph_runner(target, sub_params, parent_state):
                        sub_graph = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        return await self._execute_graph(
                            target,
                            sub_params,
                            active_resources,
                            run_id,
                            parent_state,
                            graph=sub_graph,
                            plan=sub_plan,
                        )

                    tasks_to_run = [
                        self.node_processor.process(
                            node,
                            graph,
                            state_backend,
                            active_resources,
                            run_id,
                            params,
                            sub_graph_runner,
                        )
                        for node in executable_this_pass
                    ]

                    pass_results = await asyncio.gather(*tasks_to_run)

                    for node, res in zip(executable_this_pass, pass_results):
                        state_backend.put_result(node.id, res)
                        if flow_manager:
                            flow_manager.register_result(node.id, res, state_backend)

                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
                    # All remaining nodes are blocked by constraints. Wait for a wakeup
                    # signal (e.g., from a constraint change or TTL expiration) before retrying.
                    await self._wakeup_event.wait()
                    self._wakeup_event.clear()
                    self.constraint_manager.cleanup_expired_constraints()

        if not state_backend.has_result(target._uuid):
            if skip_reason := state_backend.get_skip_reason(target._uuid):
                raise DependencyMissingError(
                    task_id=target.task.name,
                    arg_name="<Target Output>",
                    dependency_id=f"Target was skipped (Reason: {skip_reason})",
                )
            raise KeyError(
                f"Target task '{target.task.name}' did not produce a result."
            )

        return state_backend.get_result(target._uuid)
~~~~~
~~~~~python
        finally:
            # After any change (add, remove, or error), wake up the engine loop
            # if it's waiting.
            self._wakeup_event.set()
~~~~~

清理未使用的 import

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
import sys
import time
import inspect
import asyncio
from typing import Any, Dict, Optional, Generator, Callable, List, Union
from uuid import uuid4
from contextlib import ExitStack

from cascade.graph.build import build_graph
from cascade.graph.hashing import StructuralHasher
from cascade.graph.model import Node, Graph
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.constraint import GlobalConstraint
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    ResourceAcquired,
    ResourceReleased,
    ConnectorConnected,
    ConnectorDisconnected,
)
from cascade.spec.protocols import Solver, Executor, StateBackend, Connector
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.flow import FlowManager
from cascade.runtime.constraints import ConstraintManager
from cascade.runtime.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)
from cascade.adapters.state import InMemoryStateBackend
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.strategies import GraphExecutionStrategy, VMExecutionStrategy


class Engine:
~~~~~
~~~~~python
import sys
import time
import asyncio
from typing import Any, Dict, Optional, Callable, Union
from uuid import uuid4
from contextlib import ExitStack

from cascade.spec.resource import ResourceDefinition
from cascade.spec.constraint import GlobalConstraint
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
    RunStarted,
    RunFinished,
    ConnectorConnected,
    ConnectorDisconnected,
)
from cascade.spec.protocols import Solver, Executor, StateBackend, Connector
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.constraints import ConstraintManager
from cascade.runtime.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)
from cascade.adapters.state import InMemoryStateBackend
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.strategies import GraphExecutionStrategy, VMExecutionStrategy


class Engine:
~~~~~

### 下一步建议
我们已经完成了 `Engine` 的大重构。现在 `Engine` 是一个清晰的协调者，职责被干净地分配给了 `NodeProcessor`（节点执行）、`ResourceContainer`（资源管理）以及 `ExecutionStrategy`（执行流控制）。
