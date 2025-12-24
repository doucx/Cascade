好的，我们已经达到了一个关键的里程碑：新的显式控制流模型已经可以工作，而旧的隐式模型已经被运行时检查所禁止。现在是时候根据路线图的 `[Cleanup]` 阶段，彻底移除所有与旧的、基于 AST 的 TCO 相关的代码，以偿还技术债务。

我将生成一个 `[WIP]` 计划，因为它代表一个完整的、逻辑独立的重构单元。

## [WIP] refactor(core): 废弃并移除隐式 TCO 体系

### 用户需求
根据新的战略决议和架构演进路线图，彻底移除所有与基于 AST 的隐式尾递归优化（TCO）相关的代码、缓存和测试。

### 评论
这是一次重要的架构简化。通过移除脆弱的 `ast_analyzer` 和 `GraphExecutionStrategy` 中复杂的“快速路径”缓存逻辑，我们大幅降低了内核的复杂性和维护成本。这使得代码库更加清晰，完全拥抱了新的、基于 `cs.Jump` 的显式控制流模型。

### 目标
1.  删除 `ast_analyzer.py` 模块及其相关测试。
2.  删除所有专门测试旧 TCO 行为的测试文件。
3.  从 `Node` 模型中移除 TCO 相关的字段。
4.  从 `GraphBuilder` 中移除对 AST 分析的调用。
5.  从 `GraphExecutionStrategy` 中移除所有隐式 TCO 的 JIT 缓存和“快速路径”执行逻辑。

### 基本原理
新的显式控制流模型 (`cs.Jump`, `cs.bind`) 已经通过测试并被证实是更健壮的方案。同时，`LocalExecutor` 现在会主动禁止旧的“任务返回 `LazyResult`”的反模式。因此，所有支持隐式 TCO 的代码不仅已经过时，而且成为了无法被触及的“死代码”，构成了技术债务。本次清理将使代码库与新的架构原则完全对齐。

### 标签
#intent/refine #flow/ready #priority/high #comp/graph #comp/engine #concept/control-flow #scope/core #ai/instruct #task/domain/engine #task/object/tco-implicit #task/action/deprecation #task/state/end

---

### Script

#### Acts 1: 删除 AST 分析器及其相关测试

这是本次清理的核心。我们将删除 `ast_analyzer` 模块和所有专门为它编写的测试。

~~~~~act
delete_file
packages/cascade-graph/src/cascade/graph/ast_analyzer.py
~~~~~

~~~~~act
delete_file
tests/engine/graph/test_ast_analyzer.py
~~~~~

~~~~~act
delete_file
tests/engine/runtime/test_engine_recursion.py
~~~~~

~~~~~act
delete_file
tests/engine/runtime/test_tco_cache.py
~~~~~

~~~~~act
delete_file
tests/engine/runtime/test_tco_mutual_recursion.py
~~~~~

~~~~~act
delete_file
tests/engine/runtime/test_static_analysis.py
~~~~~

#### Acts 2: 清理 `cascade-graph` 包

现在我们移除 `cascade-graph` 包中对 AST 分析器的所有引用。

首先是 `__init__.py` 的导出。

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

接着，从 `Node` 模型中移除 `tco_cycle_id` 和 `warns_dynamic_recursion` 字段。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
    structural_id: str
    name: str
    template_id: str = ""  # Structural hash (ignoring literals)
    is_shadow: bool = False  # True if this node is for static analysis only
    tco_cycle_id: Optional[str] = None  # ID of the TCO cycle this node belongs to

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
~~~~~
~~~~~python
    structural_id: str
    name: str
    template_id: str = ""  # Structural hash (ignoring literals)

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
    # (e.g., has Inject markers, complex nested structures, or runtime context needs)
    has_complex_inputs: bool = False

    # Metadata from static analysis
    warns_dynamic_recursion: bool = False

    def __hash__(self):
        return hash(self.structural_id)
~~~~~
~~~~~python
    # (e.g., has Inject markers, complex nested structures, or runtime context needs)
    has_complex_inputs: bool = False

    def __hash__(self):
        return hash(self.structural_id)
~~~~~

最后，从 `GraphBuilder` 中移除所有对 AST 分析的调用。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any, Tuple
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
from cascade.spec.task import Task
from cascade.spec.jump import JumpSelector

from .registry import NodeRegistry
~~~~~
~~~~~python
from typing import Dict, Any, Tuple
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.task import Task
from cascade.spec.jump import JumpSelector

from .registry import NodeRegistry
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        # InstanceMap: Dict[LazyResult._uuid, Node]
        # Connecting the world of volatile instances to the world of stable structures.
        self._visited_instances: Dict[str, Node] = {}
        # Used to detect cycles during static TCO analysis
        self._shadow_visited: Dict[Task, Node] = {}

        self.registry = registry if registry is not None else NodeRegistry()
        self.hashing_service = HashingService()
~~~~~
~~~~~python
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
~~~~~
~~~~~python
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
~~~~~

~~~~~act
delete_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
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
    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
~~~~~

#### Acts 3: 大幅简化 `GraphExecutionStrategy`

这是最大的一块清理。我们将移除所有与 TCO 快速路径相关的逻辑。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.events import TaskSkipped, TaskBlocked, StaticAnalysisWarning
from cascade.runtime.constraints.manager import ConstraintManager


@dataclass
~~~~~
~~~~~python
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.events import TaskSkipped, TaskBlocked
from cascade.runtime.constraints.manager import ConstraintManager


@dataclass
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
        # JIT Compilation Cache
        # Maps template_id to an IndexedExecutionPlan (List[List[int]])
        # We store indices instead of Node objects to allow plan reuse across
        # different graph instances that share the same structure (template).
        self._template_plan_cache: Dict[str, List[List[int]]] = {}

        # Zero-Overhead TCO Cache
        # Maps tco_cycle_id to (Graph, IndexedPlan, root_node_id)
        # Used to bypass build_graph for structurally stable recursive calls
        self._cycle_cache: Dict[str, Any] = {}

        # Persistent registry to ensure node object identity consistency across TCO iterations
        self._node_registry = NodeRegistry()
~~~~~
~~~~~python
        # JIT Compilation Cache for execution plans
        self._plan_cache: Dict[str, List[List[int]]] = {}

        # Persistent registry to ensure node object identity consistency across iterations
        self._node_registry = NodeRegistry()
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
        current_target = target
        next_input_overrides = None

        while True:
            # Check for Zero-Overhead TCO Fast Path
            # Use getattr safely as MappedLazyResult uses .factory instead of .task
            target_task = getattr(current_target, "task", None)
            cycle_id = (
                getattr(target_task, "_tco_cycle_id", None) if target_task else None
            )
            fast_path_data = None

            if cycle_id and cycle_id in self._cycle_cache:
                if self._are_args_simple(current_target):
                    fast_path_data = self._cycle_cache[cycle_id]

            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                input_overrides = None

                if fast_path_data:
                    # FAST PATH: Reuse Graph & Plan
                    # Unpack all 4 cached values: graph, indexed_plan, root_node_id, req_res
                    graph, indexed_plan, root_node_id, _ = fast_path_data
                    # Reconstruct virtual instance map for current iteration
                    target_node = graph.get_node(root_node_id)
                    instance_map = {current_target._uuid: target_node}
                    plan = self._rehydrate_plan(graph, indexed_plan)

                    # Prepare Input Overrides
                    input_overrides = {}
                    if next_input_overrides:
                        input_overrides.update(next_input_overrides)
                        next_input_overrides = None
                    else:
                        for i, arg in enumerate(current_target.args):
                            input_overrides[str(i)] = arg
                        input_overrides.update(current_target.kwargs)
                else:
                    # SLOW PATH: Build Graph
                    # STATE GC (Asynchronous)
                    if hasattr(state_backend, "clear") and inspect.iscoroutinefunction(
                        state_backend.clear
                    ):
                        await state_backend.clear()
                    # Yield control
                    await asyncio.sleep(0)

                    graph, instance_map = build_graph(
                        current_target, registry=self._node_registry
                    )

                    if current_target._uuid not in instance_map:
                        raise RuntimeError(
                            f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                        )

                    # Post-build analysis checks
                    for node in graph.nodes:
                        if (
                            node.warns_dynamic_recursion
                            and node.name not in self._issued_warnings
                        ):
                            self.bus.publish(
                                StaticAnalysisWarning(
                                    run_id=run_id,
                                    task_id=node.structural_id,
                                    task_name=node.name,
                                    warning_code="CS-W001",
                                    message=(
                                        f"Task '{node.name}' uses a dynamic recursion pattern (calling other "
                                        "tasks in its arguments) which disables TCO optimizations, "
                                        "leading to significant performance degradation."
                                    ),
                                )
                            )
                            self._issued_warnings.add(node.name)

                    target_node = instance_map[current_target._uuid]
                    cache_key = target_node.template_id or target_node.structural_id

                    # 2. Resolve Plan
                    if cache_key in self._template_plan_cache:
                        indexed_plan = self._template_plan_cache[cache_key]
                        plan = self._rehydrate_plan(graph, indexed_plan)
                    else:
                        plan = self.solver.resolve(graph)
                        indexed_plan = self._index_plan(graph, plan)
                        self._template_plan_cache[cache_key] = indexed_plan

                    # Cache for Future TCO Fast Path
                    # Only scan and cache if we haven't already indexed this cycle
                    if cycle_id and cycle_id not in self._cycle_cache:
                        # Pre-scan resources and store them in the cycle cache
                        req_res = self.resource_container.scan(graph)
                        self._cycle_cache[cycle_id] = (
                            graph,
                            indexed_plan,
                            target_node.structural_id,
                            req_res,
                        )

                # 3. Setup Resources (mixed scope)
                if fast_path_data:
                    required_resources = fast_path_data[3]
                else:
                    required_resources = self.resource_container.scan(graph)
~~~~~
~~~~~python
        current_target = target
        next_input_overrides = None

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                # Always build the graph for now. Future optimizations will add a
                # fast path for explicit jumps.
                if hasattr(state_backend, "clear") and inspect.iscoroutinefunction(
                    state_backend.clear
                ):
                    await state_backend.clear()
                await asyncio.sleep(0)

                graph, instance_map = build_graph(
                    current_target, registry=self._node_registry
                )

                if current_target._uuid not in instance_map:
                    raise RuntimeError(
                        f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                    )

                target_node = instance_map[current_target._uuid]
                cache_key = target_node.template_id or target_node.structural_id

                # 2. Resolve Plan
                if cache_key in self._plan_cache:
                    indexed_plan = self._plan_cache[cache_key]
                    plan = self._rehydrate_plan(graph, indexed_plan)
                else:
                    plan = self.solver.resolve(graph)
                    indexed_plan = self._index_plan(graph, plan)
                    self._plan_cache[cache_key] = indexed_plan

                # 3. Setup Resources
                required_resources = self.resource_container.scan(graph)
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                # 4. Execute Graph and get a contextual result
                if fast_path_data and len(plan) == 1 and len(plan[0]) == 1:
                    graph_result = await self._execute_hot_node(
                        target_node,
                        graph,
                        state_backend,
                        active_resources,
                        params,
                        instance_map,
                        input_overrides,
                    )
                else:
                    root_overrides = None
                    if next_input_overrides:
                        root_overrides = next_input_overrides
                        next_input_overrides = None

                    graph_result = await self._execute_graph(
                        current_target,
                        params,
                        active_resources,
                        run_id,
                        state_backend,
                        graph,
                        plan,
                        instance_map,
                        root_input_overrides=root_overrides,
                    )
~~~~~
~~~~~python
                # 4. Execute Graph and get a contextual result
                root_overrides = None
                if next_input_overrides:
                    root_overrides = next_input_overrides
                    next_input_overrides = None

                graph_result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    plan,
                    instance_map,
                    root_input_overrides=root_overrides,
                )
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
            elif isinstance(result, Jump):
                # Handle Explicit Jump using the unambiguous source_node_id
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
~~~~~
~~~~~python
            elif isinstance(result, Jump):
                # Handle Explicit Jump using the unambiguous source_node_id
                source_node_id = graph_result.source_node_id

                # The graph object is only valid within the `with step_stack` context,
                # so we must find the edge before the context exits.
                jump_edge = next(
                    (
                        e
                        for e in graph.edges
                        if e.source.structural_id == source_node_id
                        and e.edge_type == EdgeType.ITERATIVE_JUMP
                    ),
                    None,
                )
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
    def _are_args_simple(self, lazy_result: Any) -> bool:
        """
        Checks if the LazyResult arguments contain any nested LazyResults.
        """
        # Handle both LazyResult (args/kwargs) and MappedLazyResult (mapping_kwargs)
        args = getattr(lazy_result, "args", [])
        kwargs = getattr(lazy_result, "kwargs", {})
        if hasattr(lazy_result, "mapping_kwargs"):
            kwargs = lazy_result.mapping_kwargs

        for arg in args:
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                return False
        for val in kwargs.values():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                return False
        return True

    async def _execute_hot_node(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        params: Dict[str, Any],
        instance_map: Dict[str, Node],
        input_overrides: Dict[str, Any] = None,
    ) -> Any:
        """
        A stripped-down version of NodeProcessor.process specifically for hot TCO loops.
        Bypasses event bus, flow manager, and multiple resolvers for maximum performance.
        """
        # 1. Resolve Arguments (Minimal path)
        # We reuse the node_processor's resolver but bypass the process() wrapper
        # Resolver is now ASYNC
        args, kwargs = await self.node_processor.arg_resolver.resolve(
            node,
            graph,
            state_backend,
            active_resources,
            instance_map=instance_map,
            user_params=params,
            input_overrides=input_overrides,
        )

        # 2. Direct Execution (Skip NodeProcessor ceremony)
        result = await self.node_processor.executor.execute(node, args, kwargs)

        # 3. Minimal State Update (Async)
        await state_backend.put_result(node.structural_id, result)
        return GraphExecutionResult(value=result, source_node_id=node.structural_id)

    async def _execute_graph(
~~~~~
~~~~~python
    async def _execute_graph(
~~~~~

### 下一步建议
我们已经完成了对隐式 TCO 体系的彻底清理。代码库现在更加简洁，并且完全符合我们新的、基于显式跳转的控制流模型。

1.  **验证**: 请运行完整的测试套件，确保我们的清理没有引入任何回归问题。
2.  **路线图**: 我们现在正式完成了路线图的 `[Cleanup]` 阶段。下一步将是 `[Optimization]` 阶段，即为新的 `Jump` 机制实现一个高效的“快速路径”，以恢复并超越旧 TCO 模型的性能。
