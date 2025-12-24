## [WIP] refactor: 将 Bind 状态迁移至 LazyResult 对象

### 用户需求
修复 `test_explicit_jump_loop` 失败的问题。将 `cs.bind` 的实现从基于 `ContextVar` 的全局注册表模式，迁移为直接修改 `LazyResult` 对象状态的模式。这能确保绑定信息与任务定义紧密耦合，避免上下文丢失导致图构建时丢失 `ITERATIVE_JUMP` 边。

### 评论
你的直觉非常敏锐。使用 `ContextVar` 来传递绑定信息确实引入了不必要的隐式状态和时序依赖。将绑定信息直接作为元数据（如 `_jump_selector`）附加在 `LazyResult` 上，不仅符合现有的 `_retry_policy` 等设计模式，而且更加健壮和直观。

### 目标
1.  修改 `LazyResult`，增加 `_jump_selector` 字段。
2.  修改 `cs.bind`，使其直接操作 `LazyResult` 实例。
3.  重构 `GraphBuilder`，移除 `binding.py` 依赖，改为在遍历 `LazyResult` 时直接处理跳转绑定。
4.  删除多余的 `cascade-graph/src/cascade/graph/binding.py`。

### 标签
#intent/refine #flow/ready #priority/high #comp/spec #comp/graph #comp/sdk #concept/control-flow #scope/core #ai/instruct #task/domain/engine #task/object/control-flow #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 LazyResult Spec

在 `LazyResult` 中添加 `_jump_selector` 字段。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/lazy_types.py
~~~~~
~~~~~python
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[Any] = None  # CachePolicy
    _condition: Optional["LazyResult"] = None
    _constraints: Optional[Any] = None  # ResourceConstraint
    _dependencies: List["LazyResult"] = field(
        default_factory=list
    )  # Explicit sequencing
~~~~~
~~~~~python
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[Any] = None  # CachePolicy
    _condition: Optional["LazyResult"] = None
    _constraints: Optional[Any] = None  # ResourceConstraint
    _dependencies: List["LazyResult"] = field(
        default_factory=list
    )  # Explicit sequencing
    _jump_selector: Optional[Any] = None  # Explicit Control Flow (JumpSelector)
~~~~~

#### Acts 2: 更新 SDK Bind 实现

修改 `bind` 函数，使其直接修改对象的 `_jump_selector` 属性。

~~~~~act
patch_file
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
~~~~~python
from typing import Dict, Optional, Any
from cascade.spec.lazy_types import LazyResult
from cascade.spec.jump import JumpSelector


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
    source._jump_selector = target
~~~~~

#### Acts 3: 重构 GraphBuilder

移除 `binding` 相关的引用，并在 `_visit_lazy_result` 中直接处理跳转逻辑。

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
from .binding import consume_bindings
from .hashing import HashingService


class GraphBuilder:
    def __init__(self, registry: NodeRegistry | None = None):
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
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
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
~~~~~python
    def build(self, target: Any) -> Tuple[Graph, Dict[str, Node]]:
        self._visit(target)
        return self.graph, self._visited_instances

    def _visit(self, value: Any) -> Node:
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
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
        self._scan_and_add_edges(node, result.kwargs)
        if result._condition:
            source_node = self._visited_instances[result._condition._uuid]
            self.graph.add_edge(
                Edge(
                    source=source_node,
                    target=node,
                    arg_name="_condition",
                    edge_type=EdgeType.CONDITION,
                )
            )
~~~~~
~~~~~python
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
        self._scan_and_add_edges(node, result.kwargs)

        # 4.1 Handle Explicit Jump Binding
        if result._jump_selector:
            selector = result._jump_selector
            if isinstance(selector, JumpSelector):
                # Ensure all potential targets in the selector are built/visited
                for route_target in selector.routes.values():
                    if route_target is not None:
                        self._visit(route_target)

                # Create the ITERATIVE_JUMP edge
                self.graph.add_edge(
                    Edge(
                        source=node,
                        target=node,  # Placeholder, engine uses jump_selector
                        arg_name="<jump>",
                        edge_type=EdgeType.ITERATIVE_JUMP,
                        jump_selector=selector,
                    )
                )

        if result._condition:
            source_node = self._visited_instances[result._condition._uuid]
            self.graph.add_edge(
                Edge(
                    source=source_node,
                    target=node,
                    arg_name="_condition",
                    edge_type=EdgeType.CONDITION,
                )
            )
~~~~~

#### Acts 4: 清理文件

删除 `binding.py`。

~~~~~act
delete_file
packages/cascade-graph/src/cascade/graph/binding.py
~~~~~

### 下一步建议
现在架构更加清晰了。请重新运行测试 `tests/engine/runtime/test_explicit_control_flow.py`。

如果测试通过，我们将正式完成阶段一。
如果失败，请检查 `Jump` 信号在 Engine 中的处理逻辑是否正确获取了 `EdgeType.ITERATIVE_JUMP` 边。
