好的，我分析了新的测试失败报告。问题主要集中在两个方面：

1.  **`ValueError: too many values to unpack`**: 正如我上次预测的，`build_graph` 函数返回值的变更影响了 `tests/sdk/` 目录下的测试文件，这些文件在我之前的修复中被遗漏了。
2.  **核心逻辑错误**: 更深层次的问题是，在引入节点复用（interning）后，ID 的使用在几个关键的运行时组件中仍然不一致，导致了：
    *   `DependencyMissingError` in `test_resource_scheduling.py`: `ConstraintResolver` 无法解析作为约束值的 `LazyResult`，因为它不知道如何将实例 ID (`_uuid`) 映射到 `state_backend` 使用的结构化 ID。
    *   `AssertionError` in `test_router_pruning.py`: `FlowManager` 的剪枝逻辑失败，因为它在计算依赖需求时混淆了实例 ID 和结构化 ID，导致未被选择的路由分支没有被正确标记为跳过。
    *   `KeyError` in `test_state_backends.py`: 这是最终结果查询失败，是 ID 不一致问题的另一个典型症状。

我将生成一个全面的计划来一次性解决所有这些问题。

## [WIP] fix(engine): Stabilize runtime after node interning refactor

### 错误分析
测试失败的根源是节点复用（interning）重构后，系统未能统一处理两种不同语义的 ID：`LazyResult._uuid`（实例 ID）和 `Node.id`（结构化哈希 ID）。此问题在多个运行时组件中表现出来：
1.  **`ConstraintResolver`**: 无法解析动态约束值，因为它缺少从实例 ID 到结构化 ID 的映射。
2.  **`FlowManager`**: 路由剪枝逻辑失效，因为它内部的依赖需求计数器混用了两种 ID，导致计数错误。
3.  **SDK 工具**: `cs.visualize` 和 `cs.dry_run` 的测试用例在调用 `build_graph` 后未能正确解包其新的三元组返回值，导致 `ValueError`。

### 用户需求
修复所有因节点复用重构而引入的测试失败，使整个测试套件恢复稳定并通过。

### 评论
这是一个典型的、在重大架构重构后出现的深层集成问题。仅仅修复表层 bug 是不够的，必须将解决方案（即 `instance_map`）系统性地传递到所有受影响的子系统中。本次修复将把“实例ID -> 结构化ID”的转换能力注入到 `ConstraintResolver` 和 `FlowManager` 中，并完成对测试代码的机械性更新，从而彻底解决这一轮的稳定性问题。

### 目标
1.  将 `instance_map` 传递给 `ConstraintResolver` 和 `FlowManager`，并更新它们的内部逻辑以使用正确的 ID。
2.  更新 `tests/sdk/` 目录中所有对 `build_graph` 的调用，以正确处理其三元组返回值。
3.  确保所有 9 个失败的测试全部通过。

### 基本原理
我们将通过 `NodeProcessor` 将 `GraphBuilder` 生成的 `instance_map` 传递给 `ConstraintResolver` 和 `FlowManager` 的构造函数。这些组件将利用这个映射，在需要将 `LazyResult` 实例与其在图中的规范化 `Node` 关联起来时，进行正确的 ID 转换。这将确保无论是解析动态约束，还是计算路由分支的依赖需求，都能使用 `state_backend` 中一致的键。同时，我们将对 `tests/sdk/` 目录下的文件进行一次性修复，以解决 `ValueError`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #comp/graph #concept/interning #scope/core #ai/instruct #task/domain/testing #task/object/test-failures #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复运行时核心逻辑

我们将 `instance_map` 注入到 `FlowManager` 和 `ConstraintResolver` 中，以修复核心的 `DependencyMissingError` 和 `AssertionError`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/flow.py
~~~~~
~~~~~python
class FlowManager:
    """
    Manages the control flow of the execution, implementing logic for
    skipping tasks (Conditions) and pruning branches (Router).
    """

    def __init__(self, graph: Graph, target_node_id: str):
        self.graph = graph
        self.target_node_id = target_node_id

        self.in_edges: Dict[str, List[Edge]] = defaultdict(list)
~~~~~
~~~~~python
class FlowManager:
    """
    Manages the control flow of the execution, implementing logic for
    skipping tasks (Conditions) and pruning branches (Router).
    """

    def __init__(self, graph: Graph, target_node_id: str, instance_map: Dict[str, Node]):
        self.graph = graph
        self.target_node_id = target_node_id
        self.instance_map = instance_map

        self.in_edges: Dict[str, List[Edge]] = defaultdict(list)
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/flow.py
~~~~~
~~~~~python
    def _get_obj_id(self, obj: Any) -> str:
        if isinstance(obj, LazyResult):
            return obj._uuid
        elif isinstance(obj, Param):
            return obj.name
        return str(obj)
~~~~~
~~~~~python
    def _get_node_from_instance(self, instance: Any) -> Optional[Node]:
        """Gets the canonical Node from a LazyResult instance."""
        if isinstance(instance, (LazyResult, MappedLazyResult)):
            return self.instance_map.get(instance._uuid)
        return None
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/flow.py
~~~~~
~~~~~python
    def _process_router_decision(
        self, edge: Edge, selector_value: Any, state_backend: StateBackend
    ):
        router = edge.router
        selected_route_key = selector_value

        for route_key, route_lazy_result in router.routes.items():
            if route_key != selected_route_key:
                branch_root_id = self._get_obj_id(route_lazy_result)
                # This branch is NOT selected.
                # We decrement its demand. If it drops to 0, it gets pruned.
                # Note: In the Router model, the "edge" carrying the router implies a demand
~~~~~
~~~~~python
    def _process_router_decision(
        self, edge: Edge, selector_value: Any, state_backend: StateBackend
    ):
        router = edge.router
        selected_route_key = selector_value

        for route_key, route_lazy_result in router.routes.items():
            if route_key != selected_route_key:
                branch_root_node = self._get_node_from_instance(route_lazy_result)
                if not branch_root_node:
                    continue  # Should not happen in a well-formed graph
                branch_root_id = branch_root_node.id
                # This branch is NOT selected.
                # We decrement its demand. If it drops to 0, it gets pruned.
                # Note: In the Router model, the "edge" carrying the router implies a demand
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python
    def __init__(
        self,
        executor: Executor,
        bus: MessageBus,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        solver: Solver,  # Needed for map nodes
    ):
        self.executor = executor
        self.bus = bus
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.solver = solver

        # Resolvers are owned by the processor
        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()

    async def process(
        self,
~~~~~
~~~~~python
    def __init__(
        self,
        executor: Executor,
        bus: MessageBus,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        solver: Solver,  # Needed for map nodes
    ):
        self.executor = executor
        self.bus = bus
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.solver = solver

        # Resolvers are owned by the processor
        self.arg_resolver = ArgumentResolver()
        # ConstraintResolver now needs the instance map to resolve dynamic values
        self.constraint_resolver = ConstraintResolver()

    async def process(
        self,
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python
        # 1. Resolve Constraints & Resources
        requirements = self.constraint_resolver.resolve(
            node, graph, state_backend, self.constraint_manager
        )

        # Pre-check for blocking to improve observability
~~~~~
~~~~~python
        # 1. Resolve Constraints & Resources
        requirements = self.constraint_resolver.resolve(
            node, graph, state_backend, self.constraint_manager, instance_map
        )

        # Pre-check for blocking to improve observability
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
class ConstraintResolver:
    """
    Responsible for resolving dynamic resource constraints for a node.
    """

    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        constraint_manager: Any = None,
    ) -> Dict[str, Any]:
        resolved = {}

        # 1. Resolve Node-level constraints
        if node.constraints and not node.constraints.is_empty():
            for res, amount in node.constraints.requirements.items():
                if isinstance(amount, (LazyResult, MappedLazyResult)):
                    if state_backend.has_result(amount._uuid):
                        resolved[res] = state_backend.get_result(amount._uuid)
                    else:
                        raise DependencyMissingError(
                            node.id, f"constraint:{res}", amount._uuid
                        )
                else:
                    resolved[res] = amount

        # 2. Resolve Global constraints
        if constraint_manager:
~~~~~
~~~~~python
class ConstraintResolver:
    """
    Responsible for resolving dynamic resource constraints for a node.
    """

    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        constraint_manager: Any,
        instance_map: Dict[str, Node],
    ) -> Dict[str, Any]:
        resolved = {}

        # 1. Resolve Node-level constraints
        if node.constraints and not node.constraints.is_empty():
            for res, amount in node.constraints.requirements.items():
                if isinstance(amount, (LazyResult, MappedLazyResult)):
                    # Get the canonical node for the dynamic constraint value
                    constraint_node = instance_map.get(amount._uuid)
                    if not constraint_node:
                        raise DependencyMissingError(
                            node.id, f"constraint:{res}", amount._uuid
                        )

                    if state_backend.has_result(constraint_node.id):
                        resolved[res] = state_backend.get_result(constraint_node.id)
                    else:
                        raise DependencyMissingError(
                            node.id, f"constraint:{res}", constraint_node.id
                        )
                else:
                    resolved[res] = amount

        # 2. Resolve Global constraints
        if constraint_manager:
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
    ) -> Any:
        target_node = instance_map[target._uuid]
        flow_manager = FlowManager(graph, target_node.id)
        blocked_nodes = set()

        for stage in plan:
~~~~~
~~~~~python
    ) -> Any:
        target_node = instance_map[target._uuid]
        flow_manager = FlowManager(graph, target_node.id, instance_map)
        blocked_nodes = set()

        for stage in plan:
~~~~~

#### Acts 2: 修复 SDK 测试中的 `build_graph` 解包错误

现在，我们将修复 `tests/sdk/` 目录下所有因 `build_graph` API 变更导致的 `ValueError`。

~~~~~act
patch_file
tests/sdk/tools/test_preview.py
~~~~~
~~~~~python
    bus, spy = bus_and_spy

    @cs.task
    def step_a():
~~~~~
~~~~~python
    bus, spy = bus_and_spy

    @cs.task
    def step_a():
~~~~~
~~~~~act
patch_file
tests/sdk/tools/test_preview.py
~~~~~
~~~~~python
from cascade.tools.preview import _analyze_plan, DryRunConsoleSubscriber
from cascade.tools.events import (
    PlanNodeInspected,
    PlanAnalysisFinished,
    PlanAnalysisStarted,
)


def test_dry_run_emits_correct_events_linear(bus_and_spy):
~~~~~
~~~~~python
from cascade.tools.preview import _analyze_plan, DryRunConsoleSubscriber
from cascade.tools.events import (
    PlanNodeInspected,
    PlanAnalysisFinished,
    PlanAnalysisStarted,
)


def test_dry_run_emits_correct_events_linear(bus_and_spy):
~~~~~
~~~~~act
patch_file
tests/sdk/tools/test_preview.py
~~~~~
~~~~~python
from cascade.tools.preview import _analyze_plan, DryRunConsoleSubscriber
from cascade.tools.events import (
    PlanNodeInspected,
    PlanAnalysisFinished,
    PlanAnalysisStarted,
)


def test_dry_run_emits_correct_events_linear(bus_and_spy):
    bus, spy = bus_and_spy

    @cs.task
    def step_a():
        return 1

    @cs.task
    def step_b(x, y=10):
        return x + y

    result = step_b(step_a(), y=10)
    _analyze_plan(result, bus)

    # Assert basic sequence
    assert len(spy.events) == 4  # Start + NodeA + NodeB + Finish
~~~~~
~~~~~python
from cascade.tools.preview import _analyze_plan, DryRunConsoleSubscriber
from cascade.tools.events import (
    PlanNodeInspected,
    PlanAnalysisFinished,
    PlanAnalysisStarted,
)


def test_dry_run_emits_correct_events_linear(bus_and_spy):
    bus, spy = bus_and_spy

    @cs.task
    def step_a():
        return 1

    @cs.task
    def step_b(x, y=10):
        return x + y

    result = step_b(step_a(), y=10)
    _analyze_plan(result, bus)

    # Assert basic sequence
    assert len(spy.events) == 4  # Start + NodeA + NodeB + Finish
~~~~~
~~~~~act
patch_file
tests/sdk/tools/test_preview.py
~~~~~
~~~~~python
def test_dry_run_emits_correct_events_linear(bus_and_spy):
    bus, spy = bus_and_spy

    @cs.task
    def step_a():
        return 1
~~~~~
~~~~~python
def test_dry_run_emits_correct_events_linear(bus_and_spy):
    bus, spy = bus_and_spy

    @cs.task
    def step_a():
        return 1
~~~~~
~~~~~act
patch_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
import cascade as cs
from cascade.spec.task import task


def test_visualize_diamond_graph():
    """
    Tests that visualize() produces a correct DOT string for a diamond graph with standard data edges.
    """
~~~~~
~~~~~python
import cascade as cs
from cascade.spec.task import task


def test_visualize_diamond_graph():
    """
    Tests that visualize() produces a correct DOT string for a diamond graph with standard data edges.
    """
~~~~~
~~~~~act
patch_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
import cascade as cs
from cascade.spec.task import task


def test_visualize_diamond_graph():
    """
    Tests that visualize() produces a correct DOT string for a diamond graph with standard data edges.
    """

    @cs.task
~~~~~
~~~~~python
import cascade as cs
from cascade.spec.task import task


def test_visualize_diamond_graph():
    """
    Tests that visualize() produces a correct DOT string for a diamond graph with standard data edges.
    """

    @cs.task
~~~~~
~~~~~act
patch_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
def test_visualize_diamond_graph():
    """
    Tests that visualize() produces a correct DOT string for a diamond graph with standard data edges.
    """

    @cs.task
    def t_a():
~~~~~
~~~~~python
def test_visualize_diamond_graph():
    """
    Tests that visualize() produces a correct DOT string for a diamond graph with standard data edges.
    """

    @cs.task
    def t_a():
~~~~~

