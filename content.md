好的，我们正式开始实施“阶段二：防线建设”。

这个阶段的核心是**提升开发者体验 (DX)**，通过静态分析主动识别并警告用户潜在的性能陷阱。我们将在 `cascade-graph` 的 AST 分析器中构建一个 Linter，用于检测会导致 TCO 性能骤降的“动态递归”反模式。

我将生成一个计划来实现这个功能。

## [WIP] feat(graph): 实现动态递归反模式的静态分析

### 用户需求
实施“阶段二：防线建设”，创建一个静态分析器，用于检测并警告开发者“动态递归”这一反模式。当一个递归任务的参数中包含对其他任务的调用时，就构成了此模式，它会强制 Cascade 引擎进入低性能的“Heavy Path”。

### 评论
这是一个极具价值的开发者体验改进。通过在图构建阶段就发出预警，我们可以引导用户从源头上写出更高效、更可预测的代码，避免他们在运行时才遭遇难以诊断的性能问题。这完全符合“在让引擎变快之前，先让用户变聪明”的战略原则。

### 目标
1.  **扩展 AST 分析器**: 增强 `ast_analyzer.py`，使其能够识别递归调用中包含其他任务调用的情况。
2.  **更新图模型**: 在 `cascade-graph` 的 `Node` 模型中增加一个标志位，用于记录静态分析的警告。
3.  **集成到图构建器**: 修改 `GraphBuilder`，使其在构建节点时，调用分析器并设置新标志位。
4.  **发出警告**: 修改 `GraphExecutionStrategy`，使其在图构建完成后检查节点的警告标志，并通过事件总线发布一个对开发者可见的警告。

### 基本原理
我们将采用一个职责分离的、事件驱动的架构来实现此功能：
1.  `TcoVisitor` (in `ast_analyzer.py`) 将被扩展，以检查递归 `ast.Call` 节点的参数。如果参数中存在解析为 `Task` 的 `ast.Call`，则认为检测到了反模式。
2.  `analyze_task_source` 的返回值将包含此检测结果。
3.  `GraphBuilder` 在创建 `Node` 时，将此结果存储在 `Node` 的一个新布尔字段 `warns_dynamic_recursion` 中，保持构建过程的纯粹性。
4.  `GraphExecutionStrategy` 在慢速路径中构建完图后，会遍历图中所有节点。如果发现 `warns_dynamic_recursion` 为 `True`，它将发布一个 `StaticAnalysisWarning` 事件。
5.  `HumanReadableLogSubscriber` 会监听此事件，并最终调用 `bus.warning`，将结构化的警告信息呈现给用户。

### 标签
#intent/build #flow/ready #priority/high #comp/graph #comp/engine #scope/dx #ai/instruct #task/domain/runtime #task/object/static-analysis #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: `cascade-graph` - 扩展模型与分析器

首先，我们在 `Node` 模型中添加一个字段来承载分析结果。然后，我们扩展 `ast_analyzer` 以检测反模式。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
    # (e.g., has Inject markers, complex nested structures, or runtime context needs)
    has_complex_inputs: bool = False

    def __hash__(self):
        return hash(self.structural_id)
~~~~~
~~~~~python
    # (e.g., has Inject markers, complex nested structures, or runtime context needs)
    has_complex_inputs: bool = False

    # Metadata from static analysis
    warns_dynamic_recursion: bool = False

    def __hash__(self):
        return hash(self.structural_id)
~~~~~

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/ast_analyzer.py
~~~~~
~~~~~python
import ast
import inspect
from typing import Any, List, Dict, Optional, Set, Callable
import logging
import textwrap
from dataclasses import dataclass

from cascade.spec.task import Task

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Holds the results of a static analysis of a task's source code."""

    targets: List[Task]
    has_dynamic_recursion: bool = False


class ReferenceResolver:
    """
    Helper class to resolve AST nodes (Name, Attribute) to runtime objects
    using the function's global and closure contexts.
    """

    def __init__(self, func: Callable):
        self.func = func
        self.globals = getattr(func, "__globals__", {})
        self.closure_vars = self._get_closure_vars(func)

    def _get_closure_vars(self, func: Callable) -> Dict[str, Any]:
        """Extracts variables from the function's closure."""
        closure_vars = {}
        if (
            hasattr(func, "__closure__")
            and func.__closure__
            and func.__code__.co_freevars
        ):
            for name, cell in zip(func.__code__.co_freevars, func.__closure__):
                try:
                    closure_vars[name] = cell.cell_contents
                except ValueError:
                    # Cell might be empty
                    pass
        return closure_vars

    def resolve(self, node: ast.AST) -> Optional[Any]:
        """Attempts to resolve an AST expression to a runtime object."""
        try:
            if isinstance(node, ast.Name):
                return self._resolve_name(node.id)
            elif isinstance(node, ast.Attribute):
                parent = self.resolve(node.value)
                if parent is not None:
                    return getattr(parent, node.attr, None)
        except Exception:
            # Resolution is best-effort; suppress errors during static analysis
            pass
        return None

    def _resolve_name(self, name: str) -> Optional[Any]:
        if name in self.closure_vars:
            return self.closure_vars[name]
        if name in self.globals:
            return self.globals[name]
        return None


class TcoVisitor(ast.NodeVisitor):
    """
    Visits the AST of a function to find 'return' statements that call other Tasks.
    """

    def __init__(self, resolver: ReferenceResolver, current_task: Task):
        self.resolver = resolver
        self.current_task = current_task
        self.potential_targets: Set[Task] = set()
        self.has_dynamic_recursion: bool = False

    def visit_Return(self, node: ast.Return):
        """
        Inspects return statements.
        Supported patterns:
          return my_task(...)
          return my_task.map(...)
        """
        if node.value and isinstance(node.value, ast.Call):
            self._analyze_call(node.value)
        self.generic_visit(node)

    def _analyze_call(self, call_node: ast.Call):
        # 1. Resolve the function being called
        func_obj = self.resolver.resolve(call_node.func)
        called_task = None

        if func_obj:
            if isinstance(func_obj, Task):
                called_task = func_obj
                self.potential_targets.add(func_obj)
            elif inspect.ismethod(func_obj) and func_obj.__name__ == "map":
                bound_self = getattr(func_obj, "__self__", None)
                if isinstance(bound_self, Task):
                    called_task = bound_self
                    self.potential_targets.add(bound_self)

        # 2. If it's a recursive call, check for the anti-pattern
        if called_task and (
            called_task == self.current_task
            or called_task.name == self.current_task.name
        ):
            all_args = call_node.args + [kw.value for kw in call_node.keywords]
            for arg_node in all_args:
                if isinstance(arg_node, ast.Call):
                    nested_call_obj = self.resolver.resolve(arg_node.func)
                    if isinstance(nested_call_obj, Task) or (
                        inspect.ismethod(nested_call_obj)
                        and nested_call_obj.__name__ == "map"
                    ):
                        self.has_dynamic_recursion = True
                        break


def analyze_task_source(task: Task) -> AnalysisResult:
    """
    Analyzes a task function's source code to find potential TCO targets
    and anti-patterns.
    Results are cached on the Task object.
    """
    if hasattr(task, "_analysis_result") and task._analysis_result is not None:
        return task._analysis_result

    task_func = task.func
    if not task_func:
        return AnalysisResult(targets=[])

    try:
        source = inspect.getsource(task_func)
        source = textwrap.dedent(source)
        tree = ast.parse(source)
    except (OSError, SyntaxError, TypeError) as e:
        logger.debug(f"Could not parse source for {task.name}: {e}")
        task._analysis_result = AnalysisResult(targets=[])
        return task._analysis_result

    resolver = ReferenceResolver(task_func)
    visitor = TcoVisitor(resolver, task)
    visitor.visit(tree)

    result = AnalysisResult(
        targets=list(visitor.potential_targets),
        has_dynamic_recursion=visitor.has_dynamic_recursion,
    )
    task._analysis_result = result
    return result


def assign_tco_cycle_ids(root_task: Task) -> None:
    """
    Performs a recursive static analysis starting from root_task to identify
    Strongly Connected Components (cycles) in the task call graph.
    """
    if getattr(root_task, "_tco_analysis_done", False):
        return

    visited = set()
    recursion_stack = set()
    path: List[Task] = []

    def _dfs(current_task: Task):
        visited.add(current_task)
        recursion_stack.add(current_task)
        path.append(current_task)

        analysis = analyze_task_source(current_task)
        targets = analysis.targets

        for target in targets:
            if target not in visited:
                _dfs(target)
            elif target in recursion_stack:
                try:
                    start_index = path.index(target)
                    cycle_members = path[start_index:]
                    member_names = sorted(t.name for t in cycle_members if t.name)
                    cycle_signature = "|".join(member_names)
                    import hashlib

                    cycle_id = hashlib.md5(cycle_signature.encode()).hexdigest()
                    for member in cycle_members:
                        member._tco_cycle_id = cycle_id
                except ValueError:
                    pass

        recursion_stack.remove(current_task)
        path.pop()
        current_task._tco_analysis_done = True

    _dfs(root_task)
~~~~~

#### Acts 2: `cascade-graph` - 集成到构建器

现在，`GraphBuilder` 将使用新的分析结果，并在创建 `Node` 时设置警告标志。

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
            )
            self.registry._registry[structural_hash] = node

        self._visited_instances[result._uuid] = node
        self._visited_instances[result._uuid] = node
~~~~~
~~~~~python
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
~~~~~
~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        if created_new:
            if result.task.func:
                if not getattr(result.task, "_tco_analysis_done", False):
                    assign_tco_cycle_ids(result.task)
                node.tco_cycle_id = getattr(result.task, "_tco_cycle_id", None)
                potential_targets = analyze_task_source(result.task)
                self._shadow_visited[result.task] = node
                for target_task in potential_targets:
                    self._visit_shadow_recursive(node, target_task)
~~~~~
~~~~~python
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
~~~~~

#### Acts 3: `cascade-engine` - 定义事件并更新订阅者

我们在 `cascade-engine` 中定义一个新的 `StaticAnalysisWarning` 事件，并教 `HumanReadableLogSubscriber` 如何处理它。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/events.py
~~~~~
~~~~~python
@dataclass(frozen=True)
class TaskBlocked(TaskEvent):
    """Fired when a task is deferred due to constraint violations."""

    reason: str = "Unknown"  # e.g. "RateLimit", "ConcurrencyLimit"
~~~~~
~~~~~python
@dataclass(frozen=True)
class TaskBlocked(TaskEvent):
    """Fired when a task is deferred due to constraint violations."""

    reason: str = "Unknown"  # e.g. "RateLimit", "ConcurrencyLimit"


@dataclass(frozen=True)
class StaticAnalysisWarning(TaskEvent):
    """Fired when static analysis detects a potential issue."""

    warning_code: str = ""  # e.g. "CS-W001"
    message: str = ""
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
    TaskRetrying,
    TaskBlocked,
    ConnectorConnected,
    ConnectorDisconnected,
    Event,
)
~~~~~
~~~~~python
    TaskRetrying,
    TaskBlocked,
    StaticAnalysisWarning,
    ConnectorConnected,
    ConnectorDisconnected,
    Event,
)
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
        event_bus.subscribe(TaskRetrying, self.on_task_retrying)
        event_bus.subscribe(ConnectorConnected, self.on_connector_connected)
        event_bus.subscribe(ConnectorDisconnected, self.on_connector_disconnected)

    def on_run_started(self, event: RunStarted):
        bus.info("run.started", target_tasks=event.target_tasks)
~~~~~
~~~~~python
        event_bus.subscribe(TaskRetrying, self.on_task_retrying)
        event_bus.subscribe(StaticAnalysisWarning, self.on_static_analysis_warning)
        event_bus.subscribe(ConnectorConnected, self.on_connector_connected)
        event_bus.subscribe(ConnectorDisconnected, self.on_connector_disconnected)

    def on_static_analysis_warning(self, event: StaticAnalysisWarning):
        bus.warning(
            "graph.analysis.warning",
            task_name=event.task_name,
            warning_code=event.warning_code,
            message=event.message,
        )

    def on_run_started(self, event: RunStarted):
        bus.info("run.started", target_tasks=event.target_tasks)
~~~~~

#### Acts 4: `cascade-engine` - 在执行策略中发布事件

最后，我们在 `GraphExecutionStrategy` 的慢速路径中添加逻辑，以检查标志并发布事件。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.events import TaskSkipped, TaskBlocked
from cascade.runtime.constraints.manager import ConstraintManager
~~~~~
~~~~~python
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.events import TaskSkipped, TaskBlocked, StaticAnalysisWarning
from cascade.runtime.constraints.manager import ConstraintManager
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                    if current_target._uuid not in instance_map:
                        raise RuntimeError(
                            f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                        )
                    target_node = instance_map[current_target._uuid]
                    cache_key = target_node.template_id or target_node.structural_id

                    # 2. Resolve Plan
                    if cache_key in self._template_plan_cache:
~~~~~
~~~~~python
                    if current_target._uuid not in instance_map:
                        raise RuntimeError(
                            f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                        )

                    # Post-build analysis checks
                    for node in graph.nodes:
                        if node.warns_dynamic_recursion:
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

                    target_node = instance_map[current_target._uuid]
                    cache_key = target_node.template_id or target_node.structural_id

                    # 2. Resolve Plan
                    if cache_key in self._template_plan_cache:
~~~~~

### 下一步建议
我们已经成功地将静态分析 Linter 集成到了图构建和执行流程中。下一步是验证它的有效性：
1.  **编写测试用例**: 在测试套件中，创建一个明确使用“动态递归”反模式的任务。
2.  **断言警告**: 运行该任务，并使用 `mock_messaging_bus` fixture 来断言 `bus.warning` 是否以正确的 `msg_id` (`graph.analysis.warning`) 和消息内容被调用。

这将确保我们的 Linter 能够按预期工作，为开发者提供及时的反馈。
