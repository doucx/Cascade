简要回答
收到。我们将执行 `[WIP]` 计划来实现 `cs.dry_run`。

关于“遵循 MessageBus 规范”的提示：`cs.dry_run` 作为一个静态分析与预览工具，其核心产出是直接面向用户的文本计划（通过 `stdout`），这符合 CLI 工具的标准行为。它并不触发运行时的 `Engine.run` 循环，因此不产生运行时事件。测试将通过捕获 `stdout` 来验证其输出，这符合测试原则中关于“断言核心数据输出”的指导。

我们将按顺序创建工具模块、实现逻辑、暴露 API 并添加测试。

## [WIP] feat(tools): Implement cs.dry_run for execution plan preview

### 用户需求
1.  实现 `cs.dry_run(target)` 函数，用于打印执行计划。
2.  确保该工具能正确处理线性图和菱形依赖图。
3.  遵循现有的架构和测试规范。

### 评论
这是一个纯新增的功能模块，不影响现有的运行时逻辑。

### 目标
1.  创建 `src/cascade/tools/preview.py`。
2.  更新 `src/cascade/__init__.py`。
3.  创建 `tests/test_tools.py`。

### 基本原理
复用 `Engine` 中的 `Solver` 来确保预览的执行顺序与实际运行完全一致。

### 标签
#intent/build #flow/ready #priority/high
#comp/cli #scope/dx
#ai/instruct
#task/domain/core #task/object/debugging-tools #task/action/implementation
#task/state/begin

---

### Script

#### Acts 1: 创建 `tools` 模块并实现 `dry_run`

~~~~~act
write_file
src/cascade/tools/__init__.py
~~~~~
~~~~~python

~~~~~

~~~~~act
write_file
src/cascade/tools/preview.py
~~~~~
~~~~~python
from typing import Any
from ..spec.task import LazyResult
from ..graph.build import build_graph
from ..runtime.engine import Engine


def dry_run(target: LazyResult[Any]) -> None:
    """
    Builds the computation graph for a target and prints the execution plan
    without running any tasks.
    
    This tool instantiates a default Engine to access its Solver, ensuring
    the predicted order matches the actual execution order.
    """
    # We use the default engine configuration to get the default solver
    engine = Engine()
    
    # 1. Build the graph statically
    graph = build_graph(target)
    
    # 2. Resolve the execution plan (topological sort)
    plan = engine.solver.resolve(graph)

    total_steps = len(plan)

    print("--- Cascade Execution Plan (Dry Run) ---")
    for i, node in enumerate(plan, 1):
        # Format literal inputs for readability
        # If an input is a LazyResult, we show a reference to its task
        # Otherwise, we show the literal value
        literals_repr = {
            k: (f"<LazyResult of '{v.task.name}'>" if isinstance(v, LazyResult) else v)
            for k, v in node.literal_inputs.items()
        }

        print(f"[{i}/{total_steps}] {node.name} (Literals: {literals_repr})")

    print("----------------------------------------")
~~~~~

#### Acts 2: 暴露 `dry_run` 为公共 API

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
from .runtime.subscribers import HumanReadableLogSubscriber
from .testing import override_resource
from .stdlib import shell
~~~~~
~~~~~python
from .runtime.subscribers import HumanReadableLogSubscriber
from .testing import override_resource
from .stdlib import shell
from .tools.preview import dry_run
~~~~~

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
__all__ = [
    "task",
    "Param",
    "run",
    "LazyResult",
    "resource",
    "inject",
    "Engine",
    "override_resource",
    "shell",
]
~~~~~
~~~~~python
__all__ = [
    "task",
    "Param",
    "run",
    "dry_run",
    "LazyResult",
    "resource",
    "inject",
    "Engine",
    "override_resource",
    "shell",
]
~~~~~

#### Acts 3: 创建测试用例

~~~~~act
write_file
tests/test_tools.py
~~~~~
~~~~~python
import cascade as cs


def test_dry_run_linear_graph(capsys):
    @cs.task
    def step_a():
        return 1

    @cs.task
    def step_b(x, y=10):
        return x + y

    result = step_b(step_a())
    cs.dry_run(result)

    captured = capsys.readouterr()
    output = captured.out

    assert "--- Cascade Execution Plan (Dry Run) ---" in output
    assert "[1/2] step_a (Literals: {})" in output
    assert "[2/2] step_b (Literals: {'y': 10})" in output
    assert "----------------------------------------" in output
    # Check order
    assert output.find("step_a") < output.find("step_b")


def test_dry_run_diamond_graph(capsys):
    @cs.task
    def t_a():
        return 1

    @cs.task
    def t_b(x):
        return x + 1

    @cs.task
    def t_c(x):
        return x * 2

    @cs.task
    def t_d(y, z):
        return y + z

    r_a = t_a()
    r_b = t_b(r_a)
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    cs.dry_run(r_d)

    captured = capsys.readouterr()
    output = captured.out

    assert "[1/4] t_a" in output
    assert "[4/4] t_d" in output
    # Check that both B and C are present
    assert "t_b (Literals: {})" in output
    assert "t_c (Literals: {})" in output
    # Check order: A must be before B and C, B and C before D
    assert output.find("t_a") < output.find("t_b")
    assert output.find("t_a") < output.find("t_c")
    assert output.find("t_b") < output.find("t_d")
    assert output.find("t_c") < output.find("t_d")
~~~~~
