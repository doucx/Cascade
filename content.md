这是针对 **[架构建议：引入基于 AST 的 TCO 静态分析以增强图透明度.md]** 的修正实施计划。

我已更正 `patch_file` 的参数，并将测试文件移动到符合项目结构的 `tests/engine/graph/` 目录下。

## [WIP] feat(graph): 引入基于 AST 的静态 TCO 分析器与 POTENTIAL 边类型

### 摘要头
**[WIP] feat(graph): 引入基于 AST 的静态 TCO 分析器与 POTENTIAL 边类型**

### 用户需求
用户希望提高 Cascade 图的透明度，特别是对于使用了 TCO (Tail Call Optimization) 模式的动态任务。当前，如果不实际运行代码，无法知道一个任务 (`return another_task()`) 可能会跳转到哪里。用户建议通过静态分析 Python 源代码 (AST) 来预测这些潜在的跳转路径，并在图中显式展示。

### 评论
这是一个极具价值的高级功能，它将 Cascade 的可观测性提升到了一个新的维度——“预测性观测”。实现它的难点在于如何从静态的 AST 中准确地解析出运行时的对象（如 Task 实例）。第一步我们先建立核心的基础设施：AST 分析器和新的边类型定义。

### 目标
1.  在 `cascade.graph.model.EdgeType` 中引入新的枚举值 `POTENTIAL`，用于表示通过静态分析推断出的、非确定性的依赖关系。
2.  创建 `cascade.graph.ast_analyzer` 模块，实现 `StaticTcoAnalyzer`。
3.  编写单元测试验证分析器能正确识别简单的 TCO 跳转。

### 基本原理
我们将使用 Python 标准库 `ast` 和 `inspect`。通过解析函数源码并遍历 `ast.Return` 节点，尝试解析其返回的调用对象。解析过程是“尽力而为”的，利用函数的 `__globals__` 和 `__closure__` 将 AST 中的符号映射回内存中的 Task 对象。

### 标签
#intent/build #flow/ready #priority/high #comp/graph #concept/ast #task/domain/core #task/object/ast-analyzer #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 扩展图模型定义

在 `EdgeType` 枚举中增加 `POTENTIAL` 类型。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/graph/model.py
~~~~~
~~~~~python
    IMPLICIT = auto()  # An implicit structural dependency
    SEQUENCE = auto()  # An explicit execution order dependency (no data transfer)
    ROUTER_ROUTE = auto()  # A potential dependency branch for a Router


@dataclass
~~~~~
~~~~~python
    IMPLICIT = auto()  # An implicit structural dependency
    SEQUENCE = auto()  # An explicit execution order dependency (no data transfer)
    ROUTER_ROUTE = auto()  # A potential dependency branch for a Router
    POTENTIAL = auto()  # A potential flow path inferred via static analysis (e.g. TCO)


@dataclass
~~~~~

#### Acts 2: 实现静态 TCO 分析器逻辑

创建 `packages/cascade-graph/src/cascade/graph/ast_analyzer.py`，包含符号解析器和 AST 访问器。

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

from cascade.spec.task import Task

logger = logging.getLogger(__name__)


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
        if hasattr(func, "__closure__") and func.__closure__ and func.__code__.co_freevars:
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

    def __init__(self, resolver: ReferenceResolver):
        self.resolver = resolver
        self.potential_targets: Set[Any] = set()

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

        if func_obj:
            # Check if it is a Task
            if isinstance(func_obj, Task):
                self.potential_targets.add(func_obj)
            
            # Check for .map calls: Task.map(...)
            if inspect.ismethod(func_obj) and func_obj.__name__ == "map":
                # Check if the bound self is a Task
                bound_self = getattr(func_obj, "__self__", None)
                if isinstance(bound_self, Task):
                    self.potential_targets.add(bound_self)


def analyze_task_source(task_func: Callable) -> List[Task]:
    """
    Analyzes a task function's source code to find potential TCO targets.
    """
    try:
        source = inspect.getsource(task_func)
        source = textwrap.dedent(source)
        tree = ast.parse(source)
    except (OSError, SyntaxError) as e:
        logger.warning(f"Could not parse source for {task_func.__name__}: {e}")
        return []

    resolver = ReferenceResolver(task_func)
    visitor = TcoVisitor(resolver)
    visitor.visit(tree)

    return list(visitor.potential_targets)
~~~~~

#### Acts 3: 添加单元测试

在 `tests/engine/graph/test_ast_analyzer.py` 中添加针对各种 TCO 返回模式的测试。

~~~~~act
write_file
tests/engine/graph/test_ast_analyzer.py
~~~~~
~~~~~python
import pytest
from cascade.spec.task import task
from cascade.graph.ast_analyzer import analyze_task_source

# --- Setup Dummy Tasks ---

@task
def downstream_a(x):
    return x

@task
def downstream_b(x):
    return x * 2

# --- Scenarios ---

def test_analyze_direct_return():
    """Test standard 'return task(...)' pattern with branching."""
    
    @task
    def orchestrator(x):
        if x > 5:
            return downstream_a(x)
        else:
            return downstream_b(x)

    targets = analyze_task_source(orchestrator.func)
    
    target_names = {t.name for t in targets}
    assert "downstream_a" in target_names
    assert "downstream_b" in target_names
    assert len(targets) == 2

def test_analyze_map_return():
    """Test 'return task.map(...)' pattern."""
    
    @task
    def mapper_orchestrator(items):
        return downstream_a.map(x=items)

    targets = analyze_task_source(mapper_orchestrator.func)
    target_names = {t.name for t in targets}
    assert "downstream_a" in target_names

def test_analyze_with_alias_in_globals():
    """Test when tasks are aliased in global scope."""
    alias_task = downstream_a

    @task
    def alias_user():
        return alias_task(1)

    targets = analyze_task_source(alias_user.func)
    target_names = {t.name for t in targets}
    assert "downstream_a" in target_names

def test_analyze_no_tco():
    """Test that regular returns are ignored."""
    @task
    def simple_calc():
        return 42

    targets = analyze_task_source(simple_calc.func)
    assert len(targets) == 0

def test_analyze_complex_attribute_access():
    """Test resolving tasks within namespaces."""
    class Actions:
        op = downstream_b
    
    actions = Actions()
    
    @task
    def namespace_user():
        return actions.op(10)
        
    targets = analyze_task_source(namespace_user.func)
    target_names = {t.name for t in targets}
    assert "downstream_b" in target_names
~~~~~

### 下一步建议
1.  **集成到 GraphBuilder**: 修改 `packages/cascade-graph/src/cascade/graph/build.py`，在构建节点时自动调用分析器。
2.  **可视化支持**: 更新 `packages/cascade-sdk/src/cascade/tools/visualize.py`，将 `POTENTIAL` 边渲染为虚线，并为这些推断出的目标创建“虚影节点”。
