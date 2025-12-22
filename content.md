简要回答：
这是一个非常核心的改进。为了支持 `cs.sequence` 所需的“无数据依赖的执行顺序”，我们需要首先在底层的 `LazyResult` 和 `Graph` 模型中引入对“显式依赖（Explicit Dependencies）”的支持。

目前的 Cascade 仅通过数据流（inputs）来隐式推导依赖。我们需要：
1.  在 `LazyResult` 中添加 `_dependencies` 字段。
2.  在 `Graph` 模型中添加 `EdgeType.SEQUENCE`。
3.  更新构建器、哈希器、序列化器和引擎来处理这种新关系。
4.  在此基础上实现 `cs.sequence` 和 `cs.pipeline` 语法糖。

以下是完整的实施计划。

## [WIP] feat: 引入 cs.sequence 与 cs.pipeline 流式编排原语

### 用户需求
用户希望获得 `cs.sequence`（顺序执行）和 `cs.pipeline`（管道执行）这两个高级编排原语，以简化线性逻辑的表达，减少中间变量，并支持更直观的脚本式写法。

### 评论
目前的 Cascade DSL 强依赖于通过函数参数传递来建立依赖关系（数据驱动）。虽然这很纯粹，但在处理仅需副作用顺序（如 `先打印日志 -> 再执行任务`）或长链式处理时，代码会变得冗长且碎片化。引入这两个原语将显著提升 DX（开发者体验）。

### 目标
1.  **底层增强**: 扩展 `LazyResult` 和 `Graph` 模型，支持不传递数据的显式依赖关系 (`EdgeType.SEQUENCE`)。
2.  **引擎适配**: 确保 `Engine` 和 `FlowManager` 能正确处理这种新依赖（例如，上游跳过导致下游跳过）。
3.  **上层实现**: 在 `cascade-library` 中实现 `cs.sequence` 和 `cs.pipeline` 及其配套的 `.after()` 链式方法。
4.  **工具适配**: 更新 `cs.visualize` 以区分显示数据边（实线）和顺序边（虚线）。

### 基本原理
我们不将 `cs.sequence` 实现为一个运行时容器（那样会破坏图的扁平性和可观测性），而是将其作为**图构建时的宏**。
*   `cs.sequence([a, b])` 本质上是将 `b` 标记为依赖于 `a`（通过新的 `_dependencies` 字段），然后返回 `b`。
*   `cs.pipeline(data, [f, g])` 本质上是自动执行 `g(f(data))` 的语法糖。

这种设计使得底层的 `Engine` 依然只看到一个扁平的、由原子任务构成的图，从而保持了架构的简洁和一致性。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/library #concept/graph #scope/api #ai/instruct #task/domain/core #task/object/flow-primitives #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 扩展核心规范 (Spec)
我们需要在图模型中定义新的边类型，并在 `LazyResult` 中添加存储显式依赖的字段。同时为 `LazyResult` 添加 `.after()` 方法，这是 `cs.sequence` 的底层原语。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/graph/model.py
~~~~~
~~~~~python
    DATA = (
        auto()
    )  # A standard data dependency (the output of Source is an input to Target)
    CONDITION = auto()  # A control dependency for the run_if condition
    CONSTRAINT = auto()  # An implicit dependency for resolving dynamic constraints
    IMPLICIT = auto()  # An implicit structural dependency
    ROUTER_ROUTE = auto()  # A potential dependency branch for a Router
~~~~~
~~~~~python
    DATA = (
        auto()
    )  # A standard data dependency (the output of Source is an input to Target)
    CONDITION = auto()  # A control dependency for the run_if condition
    CONSTRAINT = auto()  # An implicit dependency for resolving dynamic constraints
    IMPLICIT = auto()  # An implicit structural dependency
    SEQUENCE = auto()  # An explicit execution order dependency (no data transfer)
    ROUTER_ROUTE = auto()  # A potential dependency branch for a Router
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/lazy_types.py
~~~~~
~~~~~python
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[Any] = None  # CachePolicy
    _condition: Optional["LazyResult"] = None
    _constraints: Optional[Any] = None  # ResourceConstraint

    def __hash__(self):
        return hash(self._uuid)
~~~~~
~~~~~python
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[Any] = None  # CachePolicy
    _condition: Optional["LazyResult"] = None
    _constraints: Optional[Any] = None  # ResourceConstraint
    _dependencies: List["LazyResult"] = field(default_factory=list)  # Explicit sequencing

    def __hash__(self):
        return hash(self._uuid)
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/lazy_types.py
~~~~~
~~~~~python
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _condition: Optional[LazyResult] = None
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[Any] = None  # CachePolicy
    _constraints: Optional[Any] = None  # ResourceConstraint

    def __hash__(self):
        return hash(self._uuid)
~~~~~
~~~~~python
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _condition: Optional[LazyResult] = None
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[Any] = None  # CachePolicy
    _constraints: Optional[Any] = None  # ResourceConstraint
    _dependencies: List[LazyResult] = field(default_factory=list)

    def __hash__(self):
        return hash(self._uuid)
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/task.py
~~~~~
~~~~~python
LazyResult.with_constraints = _with_constraints


# --- MappedLazyResult Mixins ---


def _mapped_run_if(self: MappedLazyResult, condition: LazyResult) -> MappedLazyResult:
    self._condition = condition
    return self


MappedLazyResult.run_if = _mapped_run_if
MappedLazyResult.with_retry = _with_retry
MappedLazyResult.with_cache = _with_cache
MappedLazyResult.with_constraints = _with_constraints
~~~~~
~~~~~python
LazyResult.with_constraints = _with_constraints


def _after(self: LazyResult, *predecessors: LazyResult) -> LazyResult:
    """
    Explicitly schedules this task to run after the given predecessor tasks,
    without taking their output as input.
    """
    self._dependencies.extend(predecessors)
    return self


LazyResult.after = _after


# --- MappedLazyResult Mixins ---


def _mapped_run_if(self: MappedLazyResult, condition: LazyResult) -> MappedLazyResult:
    self._condition = condition
    return self


def _mapped_after(self: MappedLazyResult, *predecessors: LazyResult) -> MappedLazyResult:
    self._dependencies.extend(predecessors)
    return self


MappedLazyResult.run_if = _mapped_run_if
MappedLazyResult.after = _mapped_after
MappedLazyResult.with_retry = _with_retry
MappedLazyResult.with_cache = _with_cache
MappedLazyResult.with_constraints = _with_constraints
~~~~~

#### Acts 2: 更新图构建与序列化逻辑 (Graph)
我们需要更新 `GraphBuilder` 以识别 `_dependencies` 并创建 `SEQUENCE` 边。同时更新 `StructuralHasher` 和序列化逻辑以包含这些新信息。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
                        edge_type=EdgeType.CONSTRAINT,
                    )
                    self.graph.add_edge(edge)

        return node

    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
~~~~~
~~~~~python
                        edge_type=EdgeType.CONSTRAINT,
                    )
                    self.graph.add_edge(edge)

        # 5. Handle explicit sequence dependencies
        for dep in result._dependencies:
            source_node = self._visit(dep)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="<sequence>",
                edge_type=EdgeType.SEQUENCE,
            )
            self.graph.add_edge(edge)

        return node

    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
            )
            self.graph.add_edge(edge)

        return node

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
~~~~~
~~~~~python
            )
            self.graph.add_edge(edge)

        # Handle explicit sequence dependencies for Mapped nodes
        for dep in result._dependencies:
            source_node = self._visit(dep)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="<sequence>",
                edge_type=EdgeType.SEQUENCE,
            )
            self.graph.add_edge(edge)

        return node

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
        if lr._condition:
            self._hash_components.append("Condition:")
            self._visit(lr._condition, f"{path}.condition")

    def _visit_mapped(self, mlr: MappedLazyResult, path: str):
~~~~~
~~~~~python
        if lr._condition:
            self._hash_components.append("Condition:")
            self._visit(lr._condition, f"{path}.condition")

        if lr._dependencies:
            self._hash_components.append("Deps:")
            for i, dep in enumerate(lr._dependencies):
                self._visit(dep, f"{path}.deps.{i}")

    def _visit_mapped(self, mlr: MappedLazyResult, path: str):
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
        if mlr._condition:
            self._hash_components.append("Condition:")
            self._visit(mlr._condition, f"{path}.condition")

    def _visit_router(self, router: Router, path: str):
~~~~~
~~~~~python
        if mlr._condition:
            self._hash_components.append("Condition:")
            self._visit(mlr._condition, f"{path}.condition")

        if mlr._dependencies:
            self._hash_components.append("Deps:")
            for i, dep in enumerate(mlr._dependencies):
                self._visit(dep, f"{path}.deps.{i}")

    def _visit_router(self, router: Router, path: str):
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python
                # Store the UUID reference as a JSON serializable dict.
                serialized_reqs[res] = {"__lazy_ref": amount._uuid}
            else:
                serialized_reqs[res] = amount
        data["constraints"] = serialized_reqs

    return data
~~~~~
~~~~~python
                # Store the UUID reference as a JSON serializable dict.
                serialized_reqs[res] = {"__lazy_ref": amount._uuid}
            else:
                serialized_reqs[res] = amount
        data["constraints"] = serialized_reqs

    # Note: Explicit dependencies (SEQUENCE edges) are implicitly handled
    # by _edge_to_dict iterating over all graph edges. We don't need to store
    # them on the node dict itself for graph reconstruction, as graph_from_dict
    # rebuilds edges from the 'edges' list.

    return data
~~~~~

#### Acts 3: 更新引擎执行逻辑 (Engine)
`FlowManager` 需要知道当一个 `SEQUENCE` 类型的上游节点被跳过时，当前节点也应该被跳过（因为顺序依赖意味着“在...成功之后”）。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/flow.py
~~~~~
~~~~~python
            elif edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT):
                if state_backend.get_skip_reason(edge.source.id):
                    return "UpstreamSkipped_Data"

        return None
~~~~~
~~~~~python
            elif edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT):
                if state_backend.get_skip_reason(edge.source.id):
                    return "UpstreamSkipped_Data"

            elif edge.edge_type == EdgeType.SEQUENCE:
                if state_backend.get_skip_reason(edge.source.id):
                    return "UpstreamSkipped_Sequence"

        return None
~~~~~

#### Acts 4: 实现 Sequence 和 Pipeline 原语 (Library)
在 `cascade-library` 中实现这两个函数。

~~~~~act
write_file
packages/cascade-library/src/cascade/flow.py
~~~~~
~~~~~python
from typing import List, Union, Callable, Any, Sequence
from cascade.spec.lazy_types import LazyResult


def sequence(tasks: Sequence[LazyResult]) -> LazyResult:
    """
    Enforces a sequential execution order for the provided list of tasks:
    tasks[0] -> tasks[1] -> ... -> tasks[N].

    Returns the last task in the sequence.
    """
    if not tasks:
        raise ValueError("cs.sequence requires at least one task.")

    # Chain dependencies: B.after(A), C.after(B), etc.
    for i in range(len(tasks) - 1):
        tasks[i + 1].after(tasks[i])

    return tasks[-1]


def pipeline(
    initial: Any, steps: Sequence[Union[Callable[[Any], Any], LazyResult]]
) -> LazyResult:
    """
    Constructs a data processing pipeline where the output of one step
    is passed as the input to the next.

    Args:
        initial: The initial input data (or LazyResult).
        steps: A list of callables (functions, tasks) or LazyResults to apply in order.

    Returns:
        The LazyResult of the final step.
    """
    current_result = initial

    for step in steps:
        if isinstance(step, LazyResult):
            # If a LazyResult is passed directly, it's ambiguous how to pass input.
            # We assume it implies a dependency but cannot verify data flow.
            # For a proper pipeline, steps should be Callables (factories).
            # However, to be robust, if it IS a LazyResult, we just sequence it?
            # No, 'pipeline' implies data flow.
            raise TypeError(
                f"Pipeline steps must be callables (Task factories), got {type(step)}. "
                "Did you call the task (e.g. 'my_task()') instead of passing the function 'my_task'?"
            )
        elif callable(step):
            # Apply the factory to the current result
            current_result = step(current_result)
        else:
            raise TypeError(f"Invalid pipeline step type: {type(step)}")

    # Ensure the result is a LazyResult (if initial was a literal and no steps were run)
    # But pipeline usually implies at least one step or initial is Lazy.
    # If initial is literal and steps empty, it returns literal.
    # The caller expects a LazyResult usually, but returning literal is valid for Cascade (it will just resolve).
    # But to be safe in DSL usage, let's allow it.

    return current_result
~~~~~

#### Acts 5: 更新可视化工具 (Tools)
让 `cs.visualize` 能够区分显示新的顺序边。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/visualize.py
~~~~~
~~~~~python
        elif edge.edge_type == EdgeType.CONSTRAINT:
            style = (
                f' [style=dotted, color=purple, label="constraint: {edge.arg_name}"]'
            )
        else:
            style = f' [label="{edge.arg_name}"]'

        dot_parts.append(f'  "{edge.source.id}" -> "{edge.target.id}"{style};')
~~~~~
~~~~~python
        elif edge.edge_type == EdgeType.CONSTRAINT:
            style = (
                f' [style=dotted, color=purple, label="constraint: {edge.arg_name}"]'
            )
        elif edge.edge_type == EdgeType.SEQUENCE:
            style = ' [style=dashed, color=darkgray, arrowhead=open, label="next"]'
        else:
            style = f' [label="{edge.arg_name}"]'

        dot_parts.append(f'  "{edge.source.id}" -> "{edge.target.id}"{style};')
~~~~~

#### Acts 6: 导出新原语 (SDK)
最后，将新功能导出到用户可见的命名空间。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python
from cascade.runtime.exceptions import DependencyMissingError
from cascade.spec.protocols import Connector, StateBackend
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

# Tools
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import create_cli
from cascade.graph.serialize import to_json, from_json


# --- V1.3 Factory Functions ---
~~~~~
~~~~~python
from cascade.runtime.exceptions import DependencyMissingError
from cascade.spec.protocols import Connector, StateBackend
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.flow import sequence, pipeline

# Tools
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import create_cli
from cascade.graph.serialize import to_json, from_json


# --- V1.3 Factory Functions ---
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python
    "Param",  # Now the factory function
    "Env",  # New factory function
    "run",
    "dry_run",
    "visualize",
    "to_json",
    "from_json",
    "with_constraints",
    "LazyResult",
~~~~~
~~~~~python
    "Param",  # Now the factory function
    "Env",  # New factory function
    "run",
    "dry_run",
    "visualize",
    "sequence",
    "pipeline",
    "to_json",
    "from_json",
    "with_constraints",
    "LazyResult",
~~~~~

### 下一步建议
我们已经完成了核心原语的实现。下一步建议编写一个集成测试，验证 `cs.sequence` 确实强制了执行顺序，并且当序列中间的任务失败或被跳过时，后续任务能够正确地中止。同样验证 `cs.pipeline` 的数据流传递是否符合预期。
