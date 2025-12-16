你发现了一个非常关键的问题。这是一个典型的**循环导入 (Circular Import)** 错误，你的分析完全正确。

我将生成一个计划来修复这个问题。


问题的根源在于以下导入链：

1.  测试启动时，`tests/tools/test_visualize.py` 导入 `cascade` (即 `src/cascade/__init__.py`)。
2.  `src/cascade/__init__.py` 为了暴露 `cs.cli`，执行 `from .tools.cli import cli`。
3.  Python 开始加载 `src/cascade/tools/cli.py`。
4.  在 `cli.py` 的顶层，它需要 `run` 函数，于是执行 `from .. import run as cascade_run`。
5.  这个导入试图从 `src/cascade/__init__.py` 中获取 `run`。
6.  **冲突点**：此时 `src/cascade/__init__.py` 还没有被完全加载（它正停在第 2 步等待 `cli.py` 加载完成），因此 `run` 这个名字在它的命名空间中还不存在，导致 `ImportError`。

这是一个经典的 A -> B -> A 循环。


解决这个问题的最直接、最符合 Python 惯例的方法是**延迟导入**或**本地导入**。我们只在实际需要 `run` 函数时（即在 `main` 函数被调用时）才导入它，而不是在模块的顶层。

## [WIP] fix: 解决 `tools.cli` 导致的循环导入问题

### 摘要头
**[WIP] fix: 解决 `tools.cli` 导致的循环导入问题**

### 用户需求
修复因 `src/cascade/tools/cli.py` 模块试图从部分初始化的 `src/cascade/__init__.py` 导入 `run` 函数而导致的 `ImportError`。

### 评论
这是一个在项目结构变得复杂时常见的架构问题。通过将导入语句从模块顶层移动到实际使用它的函数内部，我们可以打破导入时的依赖循环，确保所有模块都能被完全加载。这是解决此类问题的标准且健壮的方案。

### 目标
1.  修改 `src/cascade/tools/cli.py` 文件。
2.  移除顶层的 `from .. import run as cascade_run` 语句。
3.  将该导入语句移动到 `main` 函数的内部。

### 基本原理
当 `cli.py` 在模块顶层导入 `cascade.run` 时，它要求 `cascade` 包在 `cli.py` 之前被完全初始化，但 `cascade` 包的初始化又依赖于 `cli.py`，从而形成死锁。

将导入操作移入 `main` 函数，意味着导入只会在 CLI 被实际执行时发生。到那个时候，整个应用的模块加载阶段已经全部完成，`cascade` 包也已经被完全初始化，`cascade.run` 函数可以被安全地找到和导入。

### 标签
#intent/fix #flow/ready #priority/critical #comp/core #scope/core #ai/instruct #task/domain/architecture #task/object/circular-import #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 `cli.py` 中的循环导入

我们将通过一次 `patch` 操作，把顶层的导入语句移动到 `main` 函数内部。

~~~~~act
patch_file
src/cascade/tools/cli.py
~~~~~
~~~~~python
from ..spec.common import Param
from .. import run as cascade_run


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
        """The actual function that Typer will wrap."""
        # Filter out None values so they don't override defaults in cs.run
        run_params = {k: v for k, v in kwargs.items() if v is not None}
        cascade_run(target, params=run_params)
~~~~~
~~~~~python
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
        """The actual function that Typer will wrap."""
        from .. import run as cascade_run

        # Filter out None values so they don't override defaults in cs.run
        run_params = {k: v for k, v in kwargs.items() if v is not None}
        cascade_run(target, params=run_params)
~~~~~

### 下一步建议
执行此计划后，循环导入问题将被解决，测试应该能够正常收集和运行。

之后，我们可以放心地为 `cs.cli` 功能创建一个 `[COMMIT]` 计划。
