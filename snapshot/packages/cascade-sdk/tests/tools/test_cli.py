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
    # The main command is the first registered one.
    params = {p.name: p for p in app.registered_commands[0].params}
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