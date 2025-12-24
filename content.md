## [WIP] feat: 实现显式控制流原语 (Jump/Bind/Select)

### 用户需求
实现 `cs.Jump`、`cs.select_jump` 和 `cs.bind` 原语，以及底层的图构建和运行时支持，以通过 `tests/engine/runtime/test_explicit_control_flow.py` 测试。

### 评论
这是架构演进的第一步。通过引入显式跳转，我们开始摆脱对隐式递归和 AST 分析的依赖。设计上，我们通过 `bind` 在构建时注入结构信息，利用 `Jump` 信号在运行时驱动状态转移。

### 目标
1.  在 `cascade-spec` 中定义 `Jump` 和 `JumpSelector`。
2.  在 `cascade-graph` 中扩展 `EdgeType` 和 `Edge` 模型，支持 `ITERATIVE_JUMP`。
3.  在 `cascade-graph` 中实现 `binding` 上下文管理，并更新 `GraphBuilder` 以消费绑定。
4.  在 `cascade-sdk` 中暴露用户 API。
5.  在 `cascade-engine` 中实现 `Jump` 信号的处理逻辑。

### 标签
#intent/build #flow/ready #priority/high #comp/spec #comp/graph #comp/engine #comp/sdk #concept/control-flow #scope/core #ai/instruct #task/domain/engine #task/object/control-flow #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 定义 Spec (Jump & JumpSelector)

在 `cascade-spec` 中定义核心数据结构。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/jump.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from uuid import uuid4
from .lazy_types import LazyResult


@dataclass
class Jump:
    """
    A signal returned by a task to indicate a transfer of control flow.
    """

    target_key: str
    data: Any = None


@dataclass
class JumpSelector:
    """
    A routing table for explicit jumps. Maps keys to LazyResults.
    """

    routes: Dict[str, Optional[LazyResult]]
    _uuid: str = field(default_factory=lambda: str(uuid4()))

    def __hash__(self):
        return hash(self._uuid)
~~~~~

#### Acts 2: 更新 Graph Model

扩展 `EdgeType` 和 `Edge` 以支持新的跳转类型。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
    SEQUENCE = auto()  # An explicit execution order dependency (no data transfer)
    ROUTER_ROUTE = auto()  # A potential dependency branch for a Router
    POTENTIAL = auto()  # A potential flow path inferred via static analysis (e.g. TCO)


@dataclass
~~~~~
~~~~~python
    SEQUENCE = auto()  # An explicit execution order dependency (no data transfer)
    ROUTER_ROUTE = auto()  # A potential dependency branch for a Router
    POTENTIAL = auto()  # A potential flow path inferred via static analysis (e.g. TCO)
    ITERATIVE_JUMP = auto()  # An explicit state transition (Jump)


@dataclass
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
    # If set, implies this edge is the selector for a dynamic router
    router: Optional[Any] = None


@dataclass
~~~~~
~~~~~python
    # If set, implies this edge is the selector for a dynamic router
    router: Optional[Any] = None

    # If set, implies this edge is an explicit jump transition
    jump_selector: Optional[Any] = None


@dataclass
~~~~~

#### Acts 3: 实现 Binding 机制

在 `cascade-graph` 中添加绑定注册表。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/binding.py
~~~~~
~~~~~python
from contextvars import ContextVar
from typing import Dict, Any, List, Tuple

# Stores a list of (source_uuid, target_selector) tuples
_pending_bindings: ContextVar[List[Tuple[str, Any]]] = ContextVar(
    "pending_bindings", default=[]
)


def bind(source_uuid: str, target: Any):
    """Registers a binding intent in the current context."""
    bindings = _pending_bindings.get().copy()
    bindings.append((source_uuid, target))
    _pending_bindings.set(bindings)


def consume_bindings() -> List[Tuple[str, Any]]:
    """Retrieves and clears the pending bindings."""
    b = _pending_bindings.get()
    _pending_bindings.set([])
    return b
~~~~~

#### Acts 4: 更新 GraphBuilder

修改 `GraphBuilder` 以处理绑定并创建 `ITERATIVE_JUMP` 边。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
from cascade.spec.task import Task

from .registry import NodeRegistry
~~~~~
~~~~~python
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import assign_tco_cycle_ids, analyze_task_source
from cascade.spec.task import Task
from cascade.spec.jump import JumpSelector

from .registry import NodeRegistry
from .hashing import HashingService
from .binding import consume_bindings
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
    def build(self, target: Any) -> Tuple[Graph, Dict[str, Node]]:
        self._visit(target)
        return self.graph, self._visited_instances

    def _visit(self, value: Any) -> Node:
~~~~~
~~~~~python
    def build(self, target: Any) -> Tuple[Graph, Dict[str, Node]]:
        self._visit(target)
        self._process_bindings()
        return self.graph, self._visited_instances

    def _process_bindings(self):
        """Applies any pending bindings to the graph."""
        bindings = consume_bindings()
        for source_uuid, selector in bindings:
            if source_uuid in self._visited_instances:
                source_node = self._visited_instances[source_uuid]

                if isinstance(selector, JumpSelector):
                    # Ensure all potential targets in the selector are built/visited
                    for route_target in selector.routes.values():
                        if route_target is not None:
                            self._visit(route_target)

                    # Create the ITERATIVE_JUMP edge
                    self.graph.add_edge(
                        Edge(
                            source=source_node,
                            target=source_node,  # Placeholder, engine uses jump_selector
                            arg_name="<jump>",
                            edge_type=EdgeType.ITERATIVE_JUMP,
                            jump_selector=selector,
                        )
                    )

    def _visit(self, value: Any) -> Node:
~~~~~

#### Acts 5: 暴露 SDK API

在 `cascade-sdk` 中实现用户接口。

~~~~~act
write_file
packages/cascade-sdk/src/cascade/control_flow.py
~~~~~
~~~~~python
from typing import Dict, Optional, Any
from cascade.spec.lazy_types import LazyResult
from cascade.spec.jump import Jump, JumpSelector
from cascade.graph.binding import bind as _register_bind


def select_jump(routes: Dict[str, Optional[LazyResult]]) -> JumpSelector:
    """
    Creates a JumpSelector for explicit control flow.
    """
    return JumpSelector(routes=routes)


def bind(source: LazyResult, target: Any):
    """
    Statically binds a source task to a control flow target (e.g. JumpSelector).
    This creates a structural edge in the graph.
    """
    _register_bind(source._uuid, target)
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python
from cascade.spec.resource import resource, inject
from cascade.spec.constraint import with_constraints

# V1.3 New Core Components
from .context import get_current_context
from cascade.spec.input import ParamSpec, EnvSpec
from .internal.inputs import _get_param_value, _get_env_var
~~~~~
~~~~~python
from cascade.spec.resource import resource, inject
from cascade.spec.constraint import with_constraints

# V1.3 New Core Components
from .context import get_current_context
from cascade.spec.input import ParamSpec, EnvSpec
from .internal.inputs import _get_param_value, _get_env_var
from .control_flow import select_jump, bind
from cascade.spec.jump import Jump
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python
    "with_constraints",
    "LazyResult",
    "Router",
    "resource",
    "inject",
    "Engine",
~~~~~
~~~~~python
    "with_constraints",
    "LazyResult",
    "Router",
    "Jump",
    "select_jump",
    "bind",
    "resource",
    "inject",
    "Engine",
~~~~~

#### Acts 6: 更新 Engine 策略

修改 `GraphExecutionStrategy` 以处理 `Jump` 信号并执行循环。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.bus import MessageBus
~~~~~
~~~~~python
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.jump import Jump
from cascade.runtime.bus import MessageBus
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
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
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                    # Reconstruct virtual instance map for current iteration
                    target_node = graph.get_node(root_node_id)
                    instance_map = {current_target._uuid: target_node}
                    plan = self._rehydrate_plan(graph, indexed_plan)

                    # Prepare Input Overrides
                    input_overrides = {}
                    for i, arg in enumerate(current_target.args):
                        input_overrides[str(i)] = arg
                    input_overrides.update(current_target.kwargs)
                else:
                    # SLOW PATH: Build Graph
~~~~~
~~~~~python
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
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                # 4. Execute Graph
                # CHECK FOR HOT-LOOP BYPASS
                # If it's a fast path and it's a simple single-node plan, bypass the orchestrator
                if fast_path_data and len(plan) == 1 and len(plan[0]) == 1:
                    result = await self._execute_hot_node(
                        target_node,
                        graph,
                        state_backend,
                        active_resources,
                        params,
                        instance_map,
                        input_overrides,
                    )
                else:
                    result = await self._execute_graph(
                        current_target,
                        params,
                        active_resources,
                        run_id,
                        state_backend,
                        graph,
                        plan,
                        instance_map,
                        input_overrides,
                    )

            # 5. Check for Tail Call (LazyResult) - TCO Logic
            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
            else:
                return result
~~~~~
~~~~~python
                # 4. Execute Graph
                # CHECK FOR HOT-LOOP BYPASS
                # If it's a fast path and it's a simple single-node plan, bypass the orchestrator
                if fast_path_data and len(plan) == 1 and len(plan[0]) == 1:
                    result = await self._execute_hot_node(
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

                    result = await self._execute_graph(
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

            # 5. Check for Tail Call (LazyResult) - TCO Logic
            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
            elif isinstance(result, Jump):
                # Handle Explicit Jump
                source_node_id = None
                if target_node := instance_map.get(current_target._uuid):
                    source_node_id = target_node.structural_id

                if not source_node_id and fast_path_data:
                    source_node_id = fast_path_data[2]

                if not source_node_id:
                    raise RuntimeError("Could not locate source node for Jump.")

                # Find outgoing ITERATIVE_JUMP edge
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
                return result
~~~~~

### 下一步建议
我们已经实现了基础设施，现在应该可以尝试再次运行测试。

如果测试通过，说明我们已经成功完成了阶段一的核心任务。下一步，我建议：
1.  **完善测试用例**: 添加一个多分支跳转的测试（例如根据状态跳转到重试逻辑或错误处理），验证 `JumpSelector` 的动态路由能力。
2.  **性能验证**: 观察并在 `GraphExecutionStrategy` 中引入对显式跳转的 `fast_path` 支持（即跳转到已缓存的图结构），从而实现真正的“零图构建开销”循环。
