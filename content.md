## [WIP] refactor(engine): Split strategies.py and simplify GraphExecutionStrategy for correctness

### 用户需求
1.  执行路线图 1.3：适配 `GraphExecutionStrategy`。
    *   移除所有缓存逻辑（`_graph_cache`, `_task_templates`）。
    *   确保严格使用 `build_graph` 返回的 `InstanceMap` 来定位目标节点。
    *   每一轮 TCO 循环都进行完整的图构建和求解。
2.  将 `strategies.py` 拆分为模块：
    *   `strategies/base.py`: 定义 `ExecutionStrategy` 协议。
    *   `strategies/graph.py`: 实现 `GraphExecutionStrategy`。
    *   `strategies/vm.py`: 实现 `VMExecutionStrategy`。
    *   `strategies/__init__.py`: 导出策略类。

### 评论
这是一个结构性的清理和重构。通过拆分文件，我们提高了代码的可维护性。更重要的是，通过移除 `GraphExecutionStrategy` 中的过早优化（缓存），我们将其回归到了一个“绝对正确”的基线状态。这符合“先上锁（正确性），再加速（性能）”的战略原则。现在 `GraphExecutionStrategy` 将完全依赖我们在 1.1 和 1.2 中构建的坚固的 Merkle 哈希和 `InstanceMap`。

### 目标
1.  删除 `packages/cascade-engine/src/cascade/runtime/strategies.py`。
2.  创建 `packages/cascade-engine/src/cascade/runtime/strategies/` 目录。
3.  创建 `base.py`, `graph.py`, `vm.py` 和 `__init__.py`。
4.  在 `graph.py` 中实现简化版的 `GraphExecutionStrategy`。

### 基本原理
拆分大文件有助于关注点分离。简化策略逻辑是为了验证核心图模型的正确性，排除缓存逻辑引入的干扰。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/engine #scope/core
#ai/instruct
#task/domain/engine #task/object/execution-strategy #task/action/refactor
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Remove old file and create directory

首先，我们需要移除旧的单文件模块，并创建新的包目录。

~~~~~act
delete_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-engine/src/cascade/runtime/strategies
~~~~~

#### Acts 2: Create `base.py`

定义基础协议。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies/base.py
~~~~~
~~~~~python
from typing import Protocol, Any, Dict
from contextlib import ExitStack
from cascade.spec.protocols import StateBackend


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
    ) -> Any: ...
~~~~~

#### Acts 3: Create `vm.py`

迁移 `VMExecutionStrategy`，保持原有逻辑不变。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python
import asyncio
from contextlib import ExitStack
from typing import Any, Dict, List

from cascade.graph.compiler import BlueprintBuilder
from cascade.runtime.vm import VirtualMachine
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.constraints.manager import ConstraintManager
from cascade.spec.protocols import StateBackend


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

#### Acts 4: Create `graph.py`

这是核心修改。我们将实现一个**无缓存**、**基于 InstanceMap** 的执行策略。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
import asyncio
from contextlib import ExitStack
from typing import Any, Dict, Tuple, List

from cascade.graph.model import Graph, Node
from cascade.graph.build import build_graph
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.bus import MessageBus
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.flow import FlowManager
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.events import TaskSkipped, TaskBlocked
from cascade.runtime.constraints.manager import ConstraintManager


class GraphExecutionStrategy:
    """
    Executes tasks by dynamically building a dependency graph and running a TCO loop.
    This is the standard execution mode for Cascade.
    
    Refactored for v3.2 architecture:
    - Strictly relies on build_graph returning (Graph, DataTuple, InstanceMap).
    - Uses InstanceMap to locate the target node within the structural graph.
    - Caching is intentionally disabled in this phase to ensure correctness.
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
        # Caching removed for Correctness Phase (1.3)

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
                # 1. Build Graph (No Caching)
                # This constructs the structural graph and the instance map.
                graph, data_tuple, instance_map = build_graph(current_target)
                
                # 2. Resolve Plan
                # We resolve the plan every time.
                plan = self.solver.resolve(graph)

                # 3. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph, data_tuple)
                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )

                # 4. Execute Graph
                result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    data_tuple,
                    plan,
                    instance_map,
                )

            # 5. Check for Tail Call (LazyResult) - TCO Logic
            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
                # STATE GC
                if hasattr(state_backend, "clear"):
                    state_backend.clear()
                # Yield control
                await asyncio.sleep(0)
            else:
                return result

    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
        graph: Graph,
        data_tuple: Tuple[Any, ...],
        plan: Any,
        instance_map: Dict[str, Node],
    ) -> Any:
        # Locate the canonical node for the current target instance
        if target._uuid not in instance_map:
            raise RuntimeError(f"Critical: Target instance {target._uuid} not found in InstanceMap.")
        
        target_node = instance_map[target._uuid]
        
        flow_manager = FlowManager(graph, target_node.id, instance_map)
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
                        # Recursive call: must build new graph and data
                        sub_graph, sub_data, sub_instance_map = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        return await self._execute_graph(
                            target,
                            sub_params,
                            active_resources,
                            run_id,
                            parent_state,
                            graph=sub_graph,
                            data_tuple=sub_data,
                            plan=sub_plan,
                            instance_map=sub_instance_map,
                        )

                    tasks_to_run = [
                        self.node_processor.process(
                            node,
                            graph,
                            data_tuple,
                            state_backend,
                            active_resources,
                            run_id,
                            params,
                            sub_graph_runner,
                            instance_map,
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

        # Use the mapped canonical node ID to check for the final result
        if not state_backend.has_result(target_node.id):
            # For debugging, check if the instance was skipped
            if skip_reason := state_backend.get_skip_reason(target_node.id):
                if skip_reason == "UpstreamSkipped_Sequence":
                    return None
                raise DependencyMissingError(
                    task_id=target.task.name or "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target node '{target_node.name}' was skipped (Reason: {skip_reason})",
                )

            raise KeyError(
                f"Target task '{target.task.name if hasattr(target.task, 'name') else 'unknown'}' did not produce a result."
            )

        return state_backend.get_result(target_node.id)
~~~~~

#### Acts 5: Create `__init__.py`

导出策略，保持 API 兼容。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies/__init__.py
~~~~~
~~~~~python
from .base import ExecutionStrategy
from .graph import GraphExecutionStrategy
from .vm import VMExecutionStrategy

__all__ = ["ExecutionStrategy", "GraphExecutionStrategy", "VMExecutionStrategy"]
~~~~~

### 下一步建议
我们已经完成了 1.3 阶段的重构。代码现在应该更加清晰，并且 `GraphExecutionStrategy` 已经完全适配了新的图构建 API。

请运行测试套件 (`pytest`)。这是关键的一步，因为它将验证整个新架构（Merkle Hash + Hash Consing + No-Cache Execution）的端到端正确性。

如果测试全部通过，我们可以运行性能测试作为最终验证（预期是慢但正确）。
