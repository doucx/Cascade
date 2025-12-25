Excellent analysis. The CI failure, contrasted with local success, is a classic sign of an environment-dependent test. Your diagnosis is spot-on: the test is too brittle.

I will now generate a plan to fix this by adopting a more robust testing strategy.

错误分析

The test `test_cli_generator_from_context` is failing in the CI environment because it asserts against the raw string output of `typer`'s `--help` command. This output is highly dependent on the environment:

1.  **TTY vs. Non-TTY**: CI runners are non-TTY environments. `typer` (and its dependency `rich`) detects this and disables ANSI color codes (`\x1b[...]`). This alone can change the output string.
2.  **Terminal Width**: The formatting and line wrapping of the help text can change based on the perceived terminal width, which often differs between a local machine and a CI runner.

Asserting against the exact visual representation of a CLI's help screen is an anti-pattern. It makes the test fragile and prone to breaking with minor dependency updates or environment changes. The core principle of "Verifying Intent, Not Presentation" (`d3-principle-python-testing-mock-intent`) applies here perfectly.

解决方案

The correct approach is to test the *configuration* of the `typer` application, not its rendered output. We need to verify that our `cs.create_cli` function correctly processed the `ParamSpec` from the context and used them to build the `Typer` object with the correct parameter definitions (name, type, default, help text).

I will rewrite the test to programmatically inspect the generated `Typer` app object's internal parameter list. This directly tests the logic of `create_cli` and is completely decoupled from the UI/rendering layer, making it robust and reliable.

## [WIP] fix(testing): Make CLI generator test robust by inspecting data, not UI

### 用户需求
Fix the failing `test_cli_generator_from_context` test in `packages/cascade-sdk/tests/tools/test_cli.py`.

### 评论
This is a critical improvement. By moving from a brittle, presentation-layer assertion to a robust, data-layer one, we not only fix the immediate CI failure but also significantly improve the quality and long-term stability of the test itself.

### 目标
1.  Modify the `test_cli_generator_from_context` test case.
2.  Instead of invoking `--help` and checking the output string, the test will directly inspect the `app` object returned by `cs.create_cli`.
3.  It will assert that the `Typer` app has been configured with parameters named "name" and "count" and that their attributes (like `help` text and `default` value) are correct.

### 基本原理
The `typer.Typer` object stores its registered parameters internally in a list of `click.Parameter` objects, accessible via `app.registered_cli.params`. We can iterate through this list to find the parameters we expect and assert their properties. This approach validates that our `create_cli` function correctly translates `ParamSpec` objects into `typer`'s internal data structures, which is the "intent" we want to verify. The test will remain valid regardless of how `typer` chooses to format its help text in the future.

### 标签
#intent/fix #flow/ready #priority/high #comp/sdk #comp/tests #concept/ui #scope/dx #ai/instruct

---
### Script

#### Acts 1: Refactor the CLI test for robustness

We will rewrite the test to inspect the application's internal state instead of its rendered output.

~~~~~act
write_file
packages/cascade-sdk/tests/tools/test_cli.py
~~~~~
~~~~~python
import pytest
from typer.testing import CliRunner
import cascade as cs
from cascade.context import get_current_context

# Skip if typer is not installed
pytest.importorskip("typer")

runner = CliRunner()


def test_cli_generator_from_context():
    """
    [V1.3 更新] 验证 CLI 生成器是从全局上下文读取 ParamSpec，
    而不是解析图结构。
    """

    # 1. 定义工作流构建函数
    # 这是一个新模式：为了让 CLI 扫描到参数，我们需要执行定义逻辑
    def workflow_def():
        # 清理上下文以确保测试隔离
        if hasattr(get_current_context(), "input_specs"):
            get_current_context().input_specs.clear()

        name = cs.Param("name", description="User name")
        count = cs.Param("count", default=1, type=int)

        @cs.task
        def greet(n, c):
            return f"Hello {n} " * c

        return greet(name, count)

    # 2. 模拟“导入时执行”：先运行一次定义，填充上下文
    target = workflow_def()

    # Debug: Verify context is populated
    specs = get_current_context().get_all_specs()
    assert len(specs) == 2, f"Context should have 2 specs, got {len(specs)}"

    # 3. 生成 CLI
    app = cs.create_cli(target)

    # 4. 验证参数定义 (Robust method: Inspect data, not UI)
    # Instead of checking the --help string, we inspect the Typer app's
    # internal configuration. This is resilient to formatting changes.
    params = {p.name: p for p in app.registered_cli.params}
    assert "name" in params
    assert "count" in params
    assert params["name"].help == "User name"
    assert params["count"].default == 1
    assert params["count"].type.name == "int"

    # 5. 验证执行
    result = runner.invoke(app, ["--name", "World", "--count", "2"])
    assert result.exit_code == 0
    # Engine logs 默认可能在 stderr
    output = result.stdout + result.stderr
    assert "Hello World Hello World" in output
~~~~~
