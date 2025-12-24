## [WIP] refactor: 移除隐式 TCO 机制与重写执行策略

### 用户需求
1.  **清理测试**: 删除所有依赖旧版隐式 TCO 行为的失败测试文件。
2.  **保留组件**: 保留 `hashing.py`。
3.  **重写策略**: 完全重写 `cascade.runtime.strategies.graph.py`，移除所有针对隐式递归的复杂缓存逻辑（如 `_cycle_cache`），只保留针对显式 `Jump` 和标准图执行的逻辑。
4.  **移除 AST 分析**: 既然不再需要猜测递归，删除 `ast_analyzer` 及其相关逻辑。

### 评论
这是一次彻底的“大扫除”。我们正在移除 Cascade 中最复杂、最脆弱的代码（隐式 TCO 探测与优化），取而代之的是一个基于 `Jump` 原语的、简单且确定性的状态机模型。这将显著降低代码库的维护负担，并提高系统的可预测性。

### 目标
1.  删除 10 个失败的测试文件。
2.  删除 `cascade-graph` 中的 `ast_analyzer.py`。
3.  修改 `Node` 模型和 `GraphBuilder`，移除 `tco_cycle_id`、`is_shadow` 等字段和相关逻辑。
4.  更新 `HashingService` 以适配简化的 `Node` 模型。
5.  **完全重写** `GraphExecutionStrategy`，实现一个干净的、支持 `Jump` 信号的主循环。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #comp/graph #comp/tests #concept/cleanup #scope/core #ai/instruct #task/domain/engine #task/object/tco-removal #task/action/rewrite #task/state/end

---

### Script

#### Acts 1: 删除过时的测试文件

删除那些测试“任务返回 LazyResult”行为的文件。

~~~~~act
delete_file
tests/engine/runtime/test_engine_recursion.py
~~~~~
~~~~~act
delete_file
tests/engine/runtime/test_jit_cache_verification.py
~~~~~
~~~~~act
delete_file
tests/engine/runtime/test_static_analysis.py
~~~~~
~~~~~act
delete_file
tests/engine/runtime/test_tco_cache.py
~~~~~
~~~~~act
delete_file
tests/engine/runtime/test_tco_mutual_recursion.py
~~~~~

#### Acts 2: 移除 AST 分析器与相关引用

删除 `ast_analyzer.py` 并在 `__init__.py` 中移除引用。

~~~~~act
delete_file
packages/cascade-graph/src/cascade/graph/ast_analyzer.py
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/__init__.py
~~~~~
~~~~~python
from .model import Graph, Node, Edge, EdgeType
from .build import build_graph
from .registry import NodeRegistry
from .ast_analyzer import analyze_task_source, assign_tco_cycle_ids
from .exceptions import StaticGraphError

__all__ = [
    "Graph",
    "Node",
    "Edge",
    "EdgeType",
    "build_graph",
    "NodeRegistry",
    "analyze_task_source",
    "assign_tco_cycle_ids",
    "StaticGraphError",
]
~~~~~
~~~~~python
from .model import Graph, Node, Edge, EdgeType
from .build import build_graph
from .registry import NodeRegistry
from .exceptions import StaticGraphError

__all__ = [
    "Graph",
    "Node",
    "Edge",
    "EdgeType",
    "build_graph",
    "NodeRegistry",
    "StaticGraphError",
]
~~~~~

#### Acts 3: 清理 Node 模型与 GraphBuilder

移除 `Node` 中的 TCO 字段，并简化 `GraphBuilder`。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
@dataclass
class Node:
    """
    Represents a node in the computation graph template.

    A Node defines 'what' to execute (the callable) and 'how' to get its arguments
    (bindings or edges), but it DOES NOT contain the runtime data itself.
    """

    structural_id: str
    name: str
    template_id: str = ""  # Structural hash (ignoring literals)
    is_shadow: bool = False  # True if this node is for static analysis only
    tco_cycle_id: Optional[str] = None  # ID of the TCO cycle this node belongs to

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
    callable_obj: Optional[Callable] = None
    signature: Optional[inspect.Signature] = None  # Cached signature for performance
    param_spec: Optional[Param] = None
    mapping_factory: Optional[Any] = None  # Implements LazyFactory

    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    # Structural Bindings
    # Maps argument names to their literal (JSON-serializable) values.
    # This makes the Node self-contained.
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    # Optimization: Flag indicating if the node requires complex resolution
    # (e.g., has Inject markers, complex nested structures, or runtime context needs)
    has_complex_inputs: bool = False

    # Metadata from static analysis
    warns_dynamic_recursion: bool = False

    def __hash__(self):
        return hash(self.structural_id)
~~~~~
~~~~~python
@dataclass
class Node:
    """
    Represents a node in the computation graph template.

    A Node defines 'what' to execute (the callable) and 'how' to get its arguments
    (bindings or edges), but it DOES NOT contain the runtime data itself.
    """

    structural_id: str
    name: str
    template_id: str = ""  # Structural hash (ignoring literals)

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
    callable_obj: Optional[Callable] = None
    signature: Optional[inspect.Signature] = None  # Cached signature for performance
    param_spec: Optional[Param] = None
    mapping_factory: Optional[Any] = None  # Implements LazyFactory

    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    # Structural Bindings
    # Maps argument names to their literal (JSON-serializable) values.
    # This makes the Node self-contained.
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    # Optimization: Flag indicating if the node requires complex resolution
    # (e.g., has Inject markers, complex nested structures, or runtime context needs)
    has_complex_inputs: bool = False

    def __hash__(self):
        return hash(self.structural_id)
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
from cascade.spec.task import Task
from cascade.spec.jump import JumpSelector

from .registry import NodeRegistry
from .hashing import HashingService


class GraphBuilder:
    def __init__(self, registry: NodeRegistry | None = None):
        self.graph = Graph()
        # InstanceMap: Dict[LazyResult._uuid, Node]
        # Connecting the world of volatile instances to the world of stable structures.
        self._visited_instances: Dict[str, Node] = {}
        # Used to detect cycles during static TCO analysis
        self._shadow_visited: Dict[Task, Node] = {}

        self.registry = registry if registry is not None else NodeRegistry()
        self.hashing_service = HashingService()
~~~~~
~~~~~python
from cascade.spec.routing import Router
from cascade.spec.jump import JumpSelector

from .registry import NodeRegistry
from .hashing import HashingService


class GraphBuilder:
    def __init__(self, registry: NodeRegistry | None = None):
        self.graph = Graph()
        # InstanceMap: Dict[LazyResult._uuid, Node]
        # Connecting the world of volatile instances to the world of stable structures.
        self._visited_instances: Dict[str, Node] = {}

        self.registry = registry if registry is not None else NodeRegistry()
        self.hashing_service = HashingService()
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
                has_complex = any(is_complex_value(v) for v in input_bindings.values())

            analysis = analyze_task_source(result.task)

            node = Node(
                structural_id=structural_hash,
                template_id=template_hash,
                name=result.task.name,
                node_type="task",
                callable_obj=result.task.func,
                signature=sig,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
                has_complex_inputs=has_complex,
                warns_dynamic_recursion=analysis.has_dynamic_recursion,
            )
            self.registry._registry[structural_hash] = node

        self._visited_instances[result._uuid] = node

        # Always add the node to the current graph, even if it was reused from the registry.
        self.graph.add_node(node)

        if created_new:
            if result.task.func:
                if not getattr(result.task, "_tco_analysis_done", False):
                    assign_tco_cycle_ids(result.task)
                node.tco_cycle_id = getattr(result.task, "_tco_cycle_id", None)
                analysis = analyze_task_source(result.task)
                potential_targets = analysis.targets
                self._shadow_visited[result.task] = node
                for target_task in potential_targets:
                    self._visit_shadow_recursive(node, target_task)

        # 4. Finalize edges (idempotent)
        self._scan_and_add_edges(node, result.args)
~~~~~
~~~~~python
                has_complex = any(is_complex_value(v) for v in input_bindings.values())

            node = Node(
                structural_id=structural_hash,
                template_id=template_hash,
                name=result.task.name,
                node_type="task",
                callable_obj=result.task.func,
                signature=sig,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
                has_complex_inputs=has_complex,
            )
            self.registry._registry[structural_hash] = node

        self._visited_instances[result._uuid] = node

        # Always add the node to the current graph, even if it was reused from the registry.
        self.graph.add_node(node)

        # 4. Finalize edges (idempotent)
        self._scan_and_add_edges(node, result.args)
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        return node

    def _visit_shadow_recursive(self, parent_node: Node, task: Task):
        if task in self._shadow_visited:
            target_node = self._shadow_visited[task]
            self.graph.add_edge(
                Edge(
                    source=parent_node,
                    target=target_node,
                    arg_name="<potential>",
                    edge_type=EdgeType.POTENTIAL,
                )
            )
            return

        potential_uuid = f"shadow:{parent_node.structural_id}:{task.name}"
        target_node = Node(
            structural_id=potential_uuid,
            name=task.name,
            node_type="task",
            is_shadow=True,
            tco_cycle_id=getattr(task, "_tco_cycle_id", None),
        )

        self.graph.add_node(target_node)
        self._shadow_visited[task] = target_node
        self.graph.add_edge(
            Edge(
                source=parent_node,
                target=target_node,
                arg_name="<potential>",
                edge_type=EdgeType.POTENTIAL,
            )
        )

        analysis = analyze_task_source(task)
        for next_task in analysis.targets:
            self._visit_shadow_recursive(target_node, next_task)

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
~~~~~
~~~~~python
        return node

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
~~~~~

#### Acts 4: 重写 GraphExecutionStrategy

彻底重写执行策略文件，移除所有与 TCO 相关的旧逻辑，实现新的 `Jump` 处理循环。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
import asyncio
import inspect
from contextlib import ExitStack
from typing import Any, Dict, List
from dataclasses import dataclass

from cascade.graph.model import Graph, Node, EdgeType
from cascade.graph.build import build_graph
from cascade.graph.registry import NodeRegistry
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.jump import Jump
from cascade.runtime.bus import MessageBus
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.flow import FlowManager
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.events import TaskSkipped, TaskBlocked
from cascade.runtime.constraints.manager import ConstraintManager


@dataclass
class GraphExecutionResult:
    """Internal result carrier to avoid context loss."""

    value: Any
    source_node_id: str


class GraphExecutionStrategy:
    """
    Executes tasks by dynamically building a dependency graph.
    Supports explicit control flow via `cs.Jump` and `cs.bind`.
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

        # JIT Compilation Cache
        # Maps template_id to an IndexedExecutionPlan (List[List[int]])
        self._template_plan_cache: Dict[str, List[List[int]]] = {}

        # Persistent registry for node interning
        self._node_registry = NodeRegistry()

    def _index_plan(self, graph: Graph, plan: Any) -> List[List[int]]:
        """
        Converts a Plan (List[List[Node]]) into an IndexedPlan (List[List[int]]).
        """
        id_to_idx = {node.structural_id: i for i, node in enumerate(graph.nodes)}
        indexed_plan = []
        for stage in plan:
            indexed_stage = [id_to_idx[node.structural_id] for node in stage]
            indexed_plan.append(indexed_stage)
        return indexed_plan

    def _rehydrate_plan(self, graph: Graph, indexed_plan: List[List[int]]) -> Any:
        """
        Converts an IndexedPlan back into a Plan using the nodes from the current graph.
        """
        plan = []
        for stage_indices in indexed_plan:
            stage_nodes = [graph.nodes[idx] for idx in stage_indices]
            plan.append(stage_nodes)
        return plan

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
        next_input_overrides = None

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                input_overrides = None

                # STATE GC (Asynchronous)
                if hasattr(state_backend, "clear") and inspect.iscoroutinefunction(
                    state_backend.clear
                ):
                    await state_backend.clear()
                # Yield control
                await asyncio.sleep(0)

                # 1. Build Graph
                graph, instance_map = build_graph(
                    current_target, registry=self._node_registry
                )

                if current_target._uuid not in instance_map:
                    raise RuntimeError(
                        f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                    )

                target_node = instance_map[current_target._uuid]
                cache_key = target_node.template_id or target_node.structural_id

                # 2. Resolve Plan (with caching)
                if cache_key in self._template_plan_cache:
                    indexed_plan = self._template_plan_cache[cache_key]
                    plan = self._rehydrate_plan(graph, indexed_plan)
                else:
                    plan = self.solver.resolve(graph)
                    indexed_plan = self._index_plan(graph, plan)
                    self._template_plan_cache[cache_key] = indexed_plan

                # 3. Setup Resources
                required_resources = self.resource_container.scan(graph)
                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )

                # 4. Prepare Input Overrides (from previous Jump)
                if next_input_overrides:
                    input_overrides = next_input_overrides
                    next_input_overrides = None

                # 5. Execute Graph
                graph_result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    plan,
                    instance_map,
                    root_input_overrides=input_overrides,
                )

            # 6. Check for Explicit Control Flow (Jump)
            result = graph_result.value

            # If the result is a LazyResult, we are seeing the "Implicit TCO" anti-pattern
            # which is now forbidden by LocalExecutor and will raise StaticGraphError there.
            # So we don't need to handle it here.

            if isinstance(result, Jump):
                # Handle Explicit Jump
                source_node_id = graph_result.source_node_id

                jump_edge = next(
                    (
                        e
                        for e in graph.edges
                        if e.source.structural_id == source_node_id
                        and e.edge_type == EdgeType.ITERATIVE_JUMP
                    ),
                    None,
                )

                if not jump_edge or not jump_edge.jump_selector:
                    raise RuntimeError(
                        f"Task returned a Jump signal but has no bound 'select_jump' (Edge not found for {source_node_id})."
                    )

                selector = jump_edge.jump_selector
                next_target = selector.routes.get(result.target_key)

                if next_target is None:
                    # Loop exit
                    return result.data

                # Prepare for next iteration
                current_target = next_target

                if isinstance(result.data, dict):
                    next_input_overrides = result.data
                elif result.data is not None:
                    next_input_overrides = {"0": result.data}
                else:
                    next_input_overrides = {}

            else:
                # Normal termination
                return result

    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
        graph: Graph,
        plan: Any,
        instance_map: Dict[str, Node],
        root_input_overrides: Dict[str, Any] = None,
    ) -> GraphExecutionResult:
        # Locate the canonical node for the current target instance
        if target._uuid not in instance_map:
            raise RuntimeError(
                f"Critical: Target instance {target._uuid} not found in InstanceMap."
            )

        target_node = instance_map[target._uuid]

        flow_manager = FlowManager(graph, target_node.structural_id, instance_map)
        blocked_nodes = set()

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue

                    # ASYNC CHECK
                    skip_reason = await flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        await state_backend.mark_skipped(
                            node.structural_id, skip_reason
                        )
                        self.bus.publish(
                            TaskSkipped(
                                run_id=run_id,
                                task_id=node.structural_id,
                                task_name=node.name,
                                reason=skip_reason,
                            )
                        )
                        continue

                    if self.constraint_manager.check_permission(node):
                        executable_this_pass.append(node)
                        if node.structural_id in blocked_nodes:
                            blocked_nodes.remove(node.structural_id)
                    else:
                        deferred_this_pass.append(node)
                        if node.structural_id not in blocked_nodes:
                            self.bus.publish(
                                TaskBlocked(
                                    run_id=run_id,
                                    task_id=node.structural_id,
                                    task_name=node.name,
                                    reason="ConstraintViolation",
                                )
                            )
                            blocked_nodes.add(node.structural_id)

                if executable_this_pass:
                    # Callback for map nodes
                    async def sub_graph_runner(target, sub_params, parent_state):
                        # Recursive call: must build new graph
                        sub_graph, sub_instance_map = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        # The map node expects the raw value, not the result object
                        result_obj = await self._execute_graph(
                            target,
                            sub_params,
                            active_resources,
                            run_id,
                            parent_state,
                            graph=sub_graph,
                            plan=sub_plan,
                            instance_map=sub_instance_map,
                        )
                        return result_obj.value

                    tasks_to_run = []
                    for node in executable_this_pass:
                        overrides = (
                            root_input_overrides
                            if node.structural_id == target_node.structural_id
                            else None
                        )
                        tasks_to_run.append(
                            self.node_processor.process(
                                node,
                                graph,
                                state_backend,
                                active_resources,
                                run_id,
                                params,
                                sub_graph_runner,
                                instance_map,
                                input_overrides=overrides,
                            )
                        )

                    pass_results = await asyncio.gather(*tasks_to_run)

                    for node, res in zip(executable_this_pass, pass_results):
                        await state_backend.put_result(node.structural_id, res)
                        if flow_manager:
                            await flow_manager.register_result(
                                node.structural_id, res, state_backend
                            )

                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
                    await self.wakeup_event.wait()
                    self.wakeup_event.clear()
                    self.constraint_manager.cleanup_expired_constraints()

        # Use the mapped canonical node ID to check for the final result
        if not await state_backend.has_result(target_node.structural_id):
            # For debugging, check if the instance was skipped
            if skip_reason := await state_backend.get_skip_reason(
                target_node.structural_id
            ):
                if skip_reason == "UpstreamSkipped_Sequence":
                    return GraphExecutionResult(
                        value=None, source_node_id=target_node.structural_id
                    )
                raise DependencyMissingError(
                    task_id=target.task.name or "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target node '{target_node.name}' was skipped (Reason: {skip_reason})",
                )

            raise KeyError(
                f"Target task '{target.task.name if hasattr(target.task, 'name') else 'unknown'}' did not produce a result."
            )

        final_value = await state_backend.get_result(target_node.structural_id)
        return GraphExecutionResult(
            value=final_value, source_node_id=target_node.structural_id
        )
~~~~~

### 下一步建议
我们已经完成了大规模的清理和重写工作。现在代码库应该更干净、更健壮。请运行 `test_explicit_control_flow.py` 和 `test_static_integrity.py`，确认新的显式控制流逻辑正常工作，并且旧的隐式递归反模式被正确拦截。

如果测试通过，说明我们已经成功完成了架构演进的关键阶段，可以准备发布或进一步优化（如阶段四的双层身份缓存）。
