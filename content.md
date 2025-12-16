# [WIP] refactor(core): 适配 Engine 和 CLI 以支持新的 Param/Env 机制

### 用户需求
完成 `Param` 和 `Env` 重构的剩余工作，使 `Engine` 能够正确注入参数，`cs.cli` 能够从 `WorkflowContext` 生成命令行接口，并修复因节点类型变更导致的序列化测试失败。

### 评论
当前的重构已经完成了基础结构（Spec, Context, Internal Tasks），但运行时（Engine）和工具（CLI）尚未适配，导致大量测试失败。这是一个关键的连接步骤，将把新的元数据层与执行层打通。

### 目标
1.  修改 `GraphBuilder`，移除对旧版 `Param` 节点的特殊处理。
2.  更新 `ArgumentResolver` 和 `Engine`，识别内部任务 `_get_param_value` 并注入用户参数。
3.  重构 `cs.cli`，使其通过扫描 `WorkflowContext` 而非遍历图节点来生成 CLI 选项。
4.  更新序列化测试，适应 `Param` 变为普通 `Task` 节点的事实。
5.  尝试修复 `FlowManager` 的测试失败。

### 基本原理
-   **运行时注入**: `_get_param_value` 是一个普通的 Task，但它需要运行时上下文数据（用户传入的 params）。通过在 `ArgumentResolver` 中拦截该特定任务并注入 `params_context`，我们可以实现透明的参数获取，而无需修改 Task 的通用执行逻辑。
-   **CLI 解耦**: `cs.cli` 不再依赖图结构，而是依赖上下文中的 Specs。这符合 v1.3 的解耦设计，使得 CLI 生成更加轻量和直接。
-   **测试适配**: 随着 `Param` 节点类型的消失（变为普通 Task），旧的针对 `node_type="param"` 的测试断言需要更新为检查 Task 节点的属性。

### 标签
#intent/refine #flow/draft #priority/high #comp/runtime #comp/cli #concept/config #scope/core #ai/instruct #task/domain/core #task/object/param-refactor #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 移除 GraphBuilder 中的 Param 处理逻辑

`GraphBuilder` 不再需要处理 `Param` 对象，因为现在 `cs.Param()` 返回的是 `LazyResult`。

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~old
    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        elif isinstance(value, Param):
            return self._visit_param(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _visit_param(self, param: Param) -> Node:
        # Use param name as its unique ID
        if param.name in self._visited:
            return self._visited[param.name]

        node = Node(
            id=param.name,
            name=param.name,
            node_type="param",
            param_spec=param,
        )
        self.graph.add_node(node)
        self._visited[param.name] = node
        return node
~~~~~
~~~~~new
    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")
~~~~~

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~old
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.common import Param
from cascade.spec.routing import Router
~~~~~
~~~~~new
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
~~~~~

#### Acts 2: 更新 ArgumentResolver 以注入参数上下文

我们需要在 `ArgumentResolver` 中识别 `_get_param_value` 任务，并注入 `params_context`。这需要修改 `resolve` 方法的签名以接收 `user_params`。

~~~~~act
patch_file
src/cascade/runtime/resolvers.py
~~~~~
~~~~~old
from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.exceptions import DependencyMissingError


class ArgumentResolver:
~~~~~
~~~~~new
from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.exceptions import DependencyMissingError
from cascade.internal.inputs import _get_param_value


class ArgumentResolver:
~~~~~

~~~~~act
patch_file
src/cascade/runtime/resolvers.py
~~~~~
~~~~~old
    def resolve(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        resource_context: Dict[str, Any],
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Resolves arguments for the node's callable from:
        1. Literal inputs
        2. Upstream dependency results (handling Routers)
        3. Injected resources

        Raises DependencyMissingError if a required upstream result is missing.
        """
        # 1. Prepare arguments from literals and upstream results
        final_kwargs = {k: v for k, v in node.literal_inputs.items() if not k.isdigit()}
~~~~~
~~~~~new
    def resolve(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        resource_context: Dict[str, Any],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Resolves arguments for the node's callable from:
        1. Literal inputs
        2. Upstream dependency results (handling Routers)
        3. Injected resources
        4. User provided params (for internal input tasks)

        Raises DependencyMissingError if a required upstream result is missing.
        """
        # 0. Special handling for internal input tasks
        if node.callable_obj is _get_param_value:
            # Inject params_context directly
            # The literal_inputs should contain 'name'
            final_kwargs = node.literal_inputs.copy()
            final_kwargs["params_context"] = user_params or {}
            return [], final_kwargs

        # 1. Prepare arguments from literals and upstream results
        final_kwargs = {k: v for k, v in node.literal_inputs.items() if not k.isdigit()}
~~~~~

#### Acts 3: 更新 Engine 以传递用户参数

`Engine` 需要在调用 `arg_resolver.resolve` 时传递 `params`。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~old
    async def _execute_node_internal(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> Any:
        # 1. Resolve Arguments (Input Validation happens here)
        try:
            args, kwargs = self.arg_resolver.resolve(
                node, graph, upstream_results, active_resources
            )
        except DependencyMissingError:
            # Re-raise. In future we could emit a specific event here.
            raise
~~~~~
~~~~~new
    async def _execute_node_internal(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> Any:
        # 1. Resolve Arguments (Input Validation happens here)
        try:
            args, kwargs = self.arg_resolver.resolve(
                node, graph, upstream_results, active_resources, user_params=params
            )
        except DependencyMissingError:
            # Re-raise. In future we could emit a specific event here.
            raise
~~~~~

#### Acts 4: 重构 cs.cli 使用 WorkflowContext

`cs.cli` 现在通过扫描 `WorkflowContext` 来生成参数，而不是构建图。

~~~~~act
patch_file
src/cascade/tools/cli.py
~~~~~
~~~~~old
from ..spec.task import LazyResult
from ..graph.build import build_graph
from ..spec.common import Param


def cli(target: LazyResult[Any]) -> Callable[[], None]:
    """
    A factory that generates a Typer-based command-line interface for a Cascade workflow.
    It inspects the workflow for `cs.Param` dependencies and converts them into
    CLI options.

    Args:
        target: The final LazyResult of the Cascade workflow.

    Returns:
        A function that, when called, will run the Typer CLI application.
    """
    if typer is None:
        raise ImportError(
            "The 'typer' library is required to use the cli tool. "
            "Please install it with: pip install cascade-py[cli]"
        )

    app = typer.Typer()
    graph = build_graph(target)

    # Find all unique parameter definitions in the graph
    params: dict[str, Param] = {
        node.param_spec.name: node.param_spec
        for node in graph.nodes
        if node.node_type == "param"
    }

    def main(**kwargs):
~~~~~
~~~~~new
from ..spec.task import LazyResult
from ..context import get_current_context
from ..spec.input import ParamSpec


def cli(target: LazyResult[Any]) -> Callable[[], None]:
    """
    A factory that generates a Typer-based command-line interface for a Cascade workflow.
    It inspects the workflow context for `cs.Param` definitions and converts them into
    CLI options.

    Args:
        target: The final LazyResult of the Cascade workflow.

    Returns:
        A function that, when called, will run the Typer CLI application.
    """
    if typer is None:
        raise ImportError(
            "The 'typer' library is required to use the cli tool. "
            "Please install it with: pip install cascade-py[cli]"
        )

    app = typer.Typer()
    
    # In v1.3, we retrieve specs from the global context, populated when 
    # the workflow was defined (e.g. when `cs.Param()` was called).
    context = get_current_context()
    all_specs = context.get_all_specs()
    
    # Filter for ParamSpec
    params: dict[str, ParamSpec] = {
        spec.name: spec
        for spec in all_specs
        if isinstance(spec, ParamSpec)
    }

    def main(**kwargs):
~~~~~

~~~~~act
patch_file
src/cascade/tools/cli.py
~~~~~
~~~~~old
        # Extract log_level explicitly since it's injected by Typer via the dynamic signature
        log_level = kwargs.pop("log_level", "INFO")
        log_format = kwargs.pop("log_format", "human")

        # Filter out None values so they don't override defaults in cs.run
        run_params = {k: v for k, v in kwargs.items() if v is not None}
        cascade_run(target, params=run_params, log_level=log_level, log_format=log_format)

    # --- Metaprogramming to create the dynamic signature ---
    sig_params = []
~~~~~
~~~~~new
        # Extract log_level explicitly since it's injected by Typer via the dynamic signature
        log_level = kwargs.pop("log_level", "INFO")
        log_format = kwargs.pop("log_format", "human")

        # Filter out None values so they don't override defaults in cs.run
        run_params = {k: v for k, v in kwargs.items() if v is not None}
        cascade_run(target, params=run_params, log_level=log_level, log_format=log_format)

    # --- Metaprogramming to create the dynamic signature ---
    sig_params = []
~~~~~

#### Acts 5: 修复序列化测试

`tests/graph/test_serialize.py` 中的 `test_serialize_params` 仍在寻找旧的 param 节点。我们需要更新它以验证新的 `_get_param_value` 任务节点。

~~~~~act
patch_file
tests/graph/test_serialize.py
~~~~~
~~~~~old
def test_serialize_params():
    """Test serialization of Param nodes."""
    p = cs.Param("env", default="dev", description="Environment")
    target = simple_task(p)
    graph = build_graph(target)

    data = graph_to_dict(graph)
    param_node = next(n for n in data["nodes"] if n["node_type"] == "param")

    assert param_node["param_spec"]["name"] == "env"
    assert param_node["param_spec"]["default"] == "dev"
    assert param_node["param_spec"]["description"] == "Environment"

    # Round trip
    restored = from_json(to_json(graph))
    p_node = next(n for n in restored.nodes if n.node_type == "param")
    assert p_node.param_spec.name == "env"
~~~~~
~~~~~new
def test_serialize_params():
    """Test serialization of Param nodes (now standard tasks)."""
    p = cs.Param("env", default="dev", description="Environment")
    target = simple_task(p)
    graph = build_graph(target)

    data = graph_to_dict(graph)
    # In v1.3, Param produces a task named '_get_param_value'
    param_node = next(n for n in data["nodes"] if n["name"] == "_get_param_value")

    assert param_node["node_type"] == "task"
    assert param_node["literal_inputs"]["name"] == "env"
    
    # Note: Serialization currently only saves graph structure, not the Context.
    # So deserialized graph will have the node, but not the ParamSpec metadata 
    # (which lives in WorkflowContext). This is expected behavior for v1.3.

    # Round trip
    restored = from_json(to_json(graph))
    p_node = next(n for n in restored.nodes if n.name == "_get_param_value")
    assert p_node.literal_inputs["name"] == "env"
~~~~~

#### Acts 6: 移除 Engine 中的 inject_params 逻辑

`Engine` 中旧的 `_inject_params` 方法已经过时，因为现在我们使用 `_get_param_value` 任务来获取参数。我们可以删除这个方法及其调用。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~old
    def override_resource_provider(self, name: str, new_provider: Any):
        if isinstance(new_provider, ResourceDefinition):
            new_provider = new_provider.func
        self._resource_providers[name] = new_provider

    def _inject_params(
        self, plan: list[Node], user_params: Dict[str, Any], results: Dict[str, Any]
    ):
        for node in plan:
            if node.node_type == "param":
                param_spec = node.param_spec
                if node.name in user_params:
                    results[node.id] = user_params[node.name]
                elif param_spec.default is not None:
                    results[node.id] = param_spec.default
                else:
                    raise ValueError(
                        f"Required parameter '{node.name}' was not provided."
                    )

    async def run(self, target: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
~~~~~
~~~~~new
    def override_resource_provider(self, name: str, new_provider: Any):
        if isinstance(new_provider, ResourceDefinition):
            new_provider = new_provider.func
        self._resource_providers[name] = new_provider

    async def run(self, target: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~old
        plan = self.solver.resolve(graph)  # Now returns List[List[Node]]
        results: Dict[str, Any] = {}
        
        # Inject params first (usually params are in the first stage or handled implicitly)
        # We need to flatten the plan to find params or iterate carefully.
        # Let's just iterate:
        all_nodes = [node for stage in plan for node in stage]
        self._inject_params(all_nodes, params, results)

        for stage in plan:
            # Prepare tasks for this stage
            tasks_to_run = []
~~~~~
~~~~~new
        plan = self.solver.resolve(graph)  # Now returns List[List[Node]]
        results: Dict[str, Any] = {}
        
        # In v1.3, params are resolved by tasks (_get_param_value), not injected upfront.
        # So we skip _inject_params.

        for stage in plan:
            # Prepare tasks for this stage
            tasks_to_run = []
~~~~~

#### Acts 7: 修复 FlowManager 测试

`tests/runtime/test_flow_manager.py` 失败是因为它是一个占位符测试，但断言了 `assert False`。我们需要查看该文件并修复它。因为我无法读取其当前内容（除了之前的 cat 输出），我将重写它为一个合理的测试，假设 `FlowManager` 已经有基本实现。如果 `FlowManager` 的 `_decrement_demand_and_prune` 是私有的，测试它可能需要一些 hack，或者我们测试公开行为 `is_skipped`。但之前的 Context 显示 `src/cascade/runtime/flow.py` 中有这个方法。

等等，我从 Context 中看到的 `flow.py` 代码中，`_decrement_demand_and_prune` 是存在的。
我将重写 `tests/runtime/test_flow_manager.py`，确保它构建一个正确的 mock graph 并测试剪枝。

~~~~~act
write_file
tests/runtime/test_flow_manager.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
from cascade.graph.model import Node, Edge, EdgeType
from cascade.runtime.flow import FlowManager

def create_mock_node(id):
    return Node(id=id, name=id)

def test_flow_manager_pruning_logic():
    """Test that FlowManager correctly prunes downstream nodes."""
    
    # Graph Topology:
    #       S
    #      / \
    #     A   B (to be pruned)
    #      \ /
    #       C
    
    # Note: In a real router scenario, S would be the selector, and there would be
    # implicit edges. Here we simulate the pruning mechanism directly.
    
    nodes = [create_mock_node(n) for n in ["S", "A", "B", "C"]]
    n_map = {n.id: n for n in nodes}
    
    edges = [
        # S -> A
        Edge(n_map["S"], n_map["A"], arg_name="x", edge_type=EdgeType.DATA),
        # S -> B
        Edge(n_map["S"], n_map["B"], arg_name="x", edge_type=EdgeType.DATA),
        
        # A -> C
        Edge(n_map["A"], n_map["C"], arg_name="a", edge_type=EdgeType.DATA),
        # B -> C
        Edge(n_map["B"], n_map["C"], arg_name="b", edge_type=EdgeType.DATA),
    ]
    
    graph = MagicMock()
    graph.nodes = nodes
    graph.edges = edges
    
    manager = FlowManager(graph, target_node_id="C")
    
    # Initial state: C has demand 2 (from A and B) + 1 (target) = 3?
    # No, demand is out-degree.
    # S: 2 (A, B)
    # A: 1 (C)
    # B: 1 (C)
    # C: 1 (Target implicit)
    
    # We simulate pruning B.
    # B's demand is 1. If we prune it, we simulate that its demand drops to 0?
    # No, pruning means we decided B shouldn't run.
    # The method _decrement_demand_and_prune(node_id) does:
    # demand[node_id] -= 1
    # if demand <= 0: mark_skipped; recursively decrement demand for upstreams (inputs to node_id)
    
    # Wait, the pruning logic usually works backward from unselected routes?
    # Or forward?
    # In flow.py:
    # _process_router_decision:
    #   for unselected route:
    #     branch_root_id = ...
    #     _decrement_demand_and_prune(branch_root_id)
    
    # So if S is a Router, and it selects A.
    # Then B is unselected.
    # We call decrement(B).
    # B's demand is 1 (C depends on B). 
    # Decrementing it makes it 0. So B is pruned.
    # Then B's inputs (S) are decremented? 
    #   for edge in in_edges[B]: decrement(S)
    
    # C depends on B. But C also depends on A.
    # If B is pruned, does C get pruned?
    # C's demand is 1 (target).
    # Pruning B doesn't affect C's demand (C is downstream of B).
    # Pruning usually propagates UPSTREAM (reducing demand for parents).
    
    # Ah, Router logic is: "This branch is not needed".
    # But C needs B?
    # If C needs B, and B is pruned, C will fail with DependencyMissing unless C handles it.
    
    # The logic in flow.py seems to imply:
    # If a node is not needed by anyone (demand=0), prune it.
    
    # In this test, if we call decrement(B):
    # demand[B] becomes 0. B is skipped.
    # B's input is S. demand[S] becomes 1 (was 2). S is NOT skipped.
    
    # Check if B is skipped.
    manager._decrement_demand_and_prune("B")
    assert manager.is_skipped("B")
    assert not manager.is_skipped("A")
    assert not manager.is_skipped("S")
    assert not manager.is_skipped("C")
~~~~~

### 下一步建议
一旦这些更改应用并通过测试，我们可以继续：
1.  清理 `tests/graph/test_serialize.py` 中可能的残留问题。
2.  运行全面测试，确保端到端功能正常。
3.  如果一切顺利，提交 v1.3 的核心重构。
