好的，我们正式启动 Cascade 阶段三的开发工作。第一步是实现 `cs.dry_run`，这是一个对开发者体验至关重要的轻量级调试工具。

我将生成一个计划来实现这个功能。

## [WIP] feat(tools): Implement cs.dry_run for execution plan preview

### 用户需求
根据《Cascade 阶段三执行计划》，需要实现一个新的顶层函数 `cs.dry_run(target: LazyResult)`。该函数应构建计算图，解析执行计划，并将其以人类可读的格式打印到标准输出，而不实际执行任何任务。

### 评论
这是一个关键的开发者体验 (DX) 功能。它为用户提供了一种零成本、无副作用的方式来验证和理解他们构建的工作流的结构和执行顺序，是调试复杂依赖关系的必备工具。

### 目标
1.  创建一个新的模块 `src/cascade/tools/preview.py` 并实现 `dry_run` 函数。
2.  在 `src/cascade/__init__.py` 中导出 `dry_run` 函数，使其成为公共 API 的一部分。
3.  创建一个新的测试文件 `tests/test_tools.py` 并为 `dry_run` 添加单元测试，覆盖线性和菱形依赖图。

### 基本原理
为了确保一致性并避免代码重复，`dry_run` 的实现将复用现有的 `Engine` 和其内部的 `Solver` 来生成执行计划。输出将进行格式化，以清晰地展示执行顺序、任务名称和静态的字面量输入，为用户提供最大的调试价值。新的 `tools` 包将用于存放此类面向开发者的辅助工具，保持核心 `runtime`, `spec`, `graph` 模块的纯净。

### 标签
#intent/build #flow/ready #priority/high
#comp/cli #scope/dx
#ai/instruct
#task/domain/core #task/object/debugging-tools #task/action/implementation
#task/state/begin

---

### Script

#### Acts 1: 创建 `tools` 模块并实现 `dry_run`

我们首先创建 `tools` 模块和 `preview.py` 文件，其中包含 `dry_run` 函数的完整实现。

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
from ..spec.task import LazyResult
from ..graph.build import build_graph
from ..runtime.engine import Engine


def dry_run(target: LazyResult) -> None:
    """
    Builds the computation graph for a target and prints the execution plan
    without running any tasks.
    """
    engine = Engine()
    graph = build_graph(target)
    plan = engine.solver.resolve(graph)

    total_steps = len(plan)

    print("--- Cascade Execution Plan (Dry Run) ---")
    for i, node in enumerate(plan, 1):
        # Format literal inputs for readability
        literals_repr = {
            k: (f"<LazyResult of '{v.task.name}'>" if isinstance(v, LazyResult) else v)
            for k, v in node.literal_inputs.items()
        }

        print(f"[{i}/{total_steps}] {node.name} (Literals: {literals_repr})")

    print("----------------------------------------")
~~~~~

#### Acts 2: 暴露 `dry_run` 为公共 API

现在，我们将 `dry_run` 函数导入到顶层 `__init__.py` 文件中，并将其添加到 `__all__` 列表中。

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

最后，我们创建 `tests/test_tools.py` 文件，并添加测试用例来验证 `dry_run` 的输出是否正确。

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
    # Check order
    assert output.find("t_a") < output.find("t_b")
    assert output.find("t_a") < output.find("t_c")
    assert output.find("t_b") < output.find("t_d")
    assert output.find("t_c") < output.find("t_d")
~~~~~

### 下一步建议
实施完成后，我们将运行测试套件以验证新功能。通过后，我将生成 `[COMMIT]` 计划来正式提交 `dry_run` 工具。之后，我们将继续阶段三的下一个任务：**实现 `cs.File`**。
