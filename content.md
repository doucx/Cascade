好的，这是一个绝佳的选择。`cs.cli` 是一个能够极大提升 Cascade 易用性和分发能力的功能。将一个复杂的工作流封装成一个独立的、带有自动生成的帮助文档的命令行工具，是开发者体验 (DX) 的一次巨大飞跃。

我们将使用 `Typer` 库来实现这个功能，因为它基于 Python 的类型提示，与 Cascade 的现代 API 风格完美契合。

我将生成实现此功能的完整计划。

## [WIP] feat(tools): 实现 `cs.cli` 以从工作流参数自动生成 CLI

### 用户需求
实现一个新的顶层函数 `cs.cli(target: LazyResult)`，该函数能够：
1.  自动扫描目标工作流 (`target`) 的依赖图，找出所有 `cs.Param` 依赖。
2.  基于这些 `Param` 的定义（名称、默认值、类型、描述），动态地创建一个功能完备的命令行接口。
3.  该 CLI 能够接收用户输入的参数，并用它们来执行 `cs.run(target, params=...)`。

### 评论
这是 Cascade 从一个“库”向一个“自动化平台”演进的关键一步。`cs.cli` 将彻底改变 Cascade 脚本的分发和使用方式。开发者不再需要手动编写 `argparse` 或 `click` 代码，只需在工作流的末尾添加一行 `cs.cli(target)()`，就能立即获得一个专业的 CLI 工具，自带参数解析、类型验证和详细的 `--help` 文档。这极大地降低了将自动化逻辑分享给他人的门槛。

我们选择 `Typer` 作为底层实现，因为它能让我们以编程方式、优雅地构建 CLI，并与 `cs.Param` 的设计理念（特别是类型和帮助文本）无缝对接。

### 目标
1.  为 `cascade-py` 添加一个新的可选依赖 `typer`。
2.  创建一个新模块 `src/cascade/tools/cli.py` 来封装 CLI 生成逻辑。
3.  实现核心的 `cli(target)` 工厂函数。该函数不直接运行，而是返回一个可调用的对象，该对象在被调用时才启动 CLI。
4.  `cli` 函数内部必须：
    a.  调用 `build_graph` 来发现所有 `Param` 节点。
    b.  为每个 `Param` 动态创建一个 `typer.Option`。
    c.  将 `Param` 的 `name`、`default`、`type` 和 `description` 属性精确地映射到 `typer.Option` 的对应参数上。
    d.  动态构建一个 `main` 函数，其签名包含所有生成的 `typer.Option`。
    e.  该 `main` 函数的主体将调用 `cs.run`，并传入从命令行解析到的参数。
5.  创建一个新的测试文件 `tests/tools/test_cli.py`，使用 `typer.testing.CliRunner` 来验证生成的 CLI 是否能正确接收参数、显示帮助并触发工作流。
6.  在 `src/cascade/__init__.py` 中暴露 `cs.cli` 函数。

### 基本原理
我们将采用元编程（metaprogramming）技术来动态构建 CLI。`cli(target)` 函数会首先遍历计算图，收集所有 `cs.Param` 定义。然后，它会利用 Python 的 `inspect` 模块，为将要执行的 `main` 函数动态地创建一个函数签名 (`__signature__`)。签名中的每个参数都将是一个 `typer.Option`，其配置完全由对应的 `cs.Param` 决定。最后，这个动态生成的函数会被注册为一个 `Typer` 命令。当用户运行脚本时，Typer 会接管并处理所有命令行交互，然后调用我们的 `main` 函数，最终触发 `cs.run`。

### 标签
#intent/build #flow/ready #priority/high #comp/core #scope/dx #ai/instruct #task/domain/tooling #task/object/cli-generator #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 添加 `typer` 作为可选依赖

为了保持核心库的轻量级，我们将 `typer` 添加到一个新的可选依赖组 `[cli]` 中。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "mypy",
  "pytest-aiohttp",
]
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]
~~~~~
~~~~~toml
[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "mypy",
  "pytest-aiohttp",
  "typer[all]",
]
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]
cli = ["typer[all]"]
~~~~~

#### Acts 2: 实现 `cli.py` 模块

这是功能的核心。我们将创建 `cli` 工厂函数，它负责所有的图分析和 CLI 动态构建工作。

~~~~~act
write_file
src/cascade/tools/cli.py
~~~~~
~~~~~python
import inspect
from typing import Any, Callable

try:
    import typer
except ImportError:
    typer = None

from ..spec.task import LazyResult
from ..graph.build import build_graph
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

    # --- Metaprogramming to create the dynamic signature ---
    sig_params = []
    for p in params.values():
        # Determine the default value for Typer
        # If no default, it's a required CLI argument (or option if -- is used)
        default = p.default if p.default is not None else ...

        # Create the Typer Option with all relevant info
        option = typer.Option(
            default,
            f"--{p.name}",
            help=p.description,
            # Typer can infer type from default, but explicit is better
            type=p.type,
        )

        sig_param = inspect.Parameter(
            name=p.name,
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=option,
            annotation=p.type,
        )
        sig_params.append(sig_param)

    # Set the dynamic signature on the main function
    main.__signature__ = inspect.Signature(parameters=sig_params)
    # Give it a docstring for better --help
    main.__doc__ = "Runs the Cascade workflow."

    # Register the dynamically created function with Typer
    app.command()(main)

    return app
~~~~~

#### Acts 3: 创建 `test_cli.py`

我们需要一个测试来验证生成的 CLI 是否按预期工作，包括参数传递和帮助文本的生成。

~~~~~act
write_file
tests/tools/test_cli.py
~~~~~
~~~~~python
import pytest
from typer.testing import CliRunner
import cascade as cs

# Skip if typer is not installed
pytest.importorskip("typer")

runner = CliRunner()


def test_cli_generator_success():
    """Tests that the generated CLI runs the workflow correctly."""

    # 1. Define a workflow with Params
    name_param = cs.Param("name", description="The name to greet.")
    count_param = cs.Param("count", default=1, type=int, description="Number of times to greet.")

    @cs.task
    def greet(name: str, count: int) -> str:
        return "\n".join([f"Hello, {name}!" for _ in range(count)])

    @cs.task
    def print_greeting(greeting: str):
        # We print to stdout, which the runner can capture
        print(greeting)

    workflow = print_greeting(greet(name=name_param, count=count_param))

    # 2. Generate the CLI application
    app = cs.cli(workflow)

    # 3. Invoke the CLI with arguments
    result = runner.invoke(app, ["--name", "Cascade", "--count", "2"])

    assert result.exit_code == 0
    assert "Hello, Cascade!\nHello, Cascade!" in result.stdout


def test_cli_generator_help_message():
    """Tests that the --help message is generated correctly from Param descriptions."""

    name_param = cs.Param("name", description="The name to greet.")
    count_param = cs.Param("count", default=1, type=int, description="Number of times to greet.")

    @cs.task
    def dummy(name: str, count: int):
        pass

    workflow = dummy(name=name_param, count=count_param)
    app = cs.cli(workflow)

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "The name to greet." in result.stdout
    assert "Number of times to greet." in result.stdout
    assert "--name" in result.stdout
    assert "--count" in result.stdout


def test_cli_missing_required_param():
    """Tests that the CLI correctly identifies and fails for missing required params."""
    required_param = cs.Param("required")  # No default value

    @cs.task
    def dummy_task(required: str):
        pass

    workflow = dummy_task(required=required_param)
    app = cs.cli(workflow)

    result = runner.invoke(app, [])

    assert result.exit_code != 0
    assert "Missing option '--required'" in result.stderr
~~~~~

#### Acts 4: 暴露 `cs.cli` 到公共 API

最后，我们将新函数添加到 `__init__.py` 中。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize

# Note: 'shell' is removed from static imports to support dynamic provider loading
__all__ = [
    "task",
    "Param",
    "run",
    "dry_run",
    "visualize",
    "LazyResult",
    "Router",
    "File",
    "resource",
    "inject",
    "Engine",
    "override_resource",
]
~~~~~
~~~~~python
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import cli

# Note: 'shell' is removed from static imports to support dynamic provider loading
__all__ = [
    "task",
    "Param",
    "run",
    "dry_run",
    "visualize",
    "cli",
    "LazyResult",
    "Router",
    "File",
    "resource",
    "inject",
    "Engine",
    "override_resource",
]
~~~~~

### 下一步建议
一旦此计划执行完毕，`cs.cli` 功能将完全可用。我们可以运行新的测试套件以确保一切正常。

之后，下一步自然是创建一个 `[COMMIT]` 计划，将这个极具价值的新工具合并到我们的代码库中。
