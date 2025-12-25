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

    # 3. 生成 CLI
    app = cs.create_cli(target)

    # 4. 验证参数定义 (Robust method: Inspect the signature on the callback)
    # The dynamically generated signature is attached to the callback function
    # stored within the first registered CommandInfo object.
    assert len(app.registered_commands) == 1
    sig_params = app.registered_commands[0].callback.__signature__.parameters

    assert "name" in sig_params
    assert "count" in sig_params

    # The typer.Option object is the default value of the inspect.Parameter
    name_param = sig_params["name"]
    count_param = sig_params["count"]

    assert name_param.default.help == "User name"
    assert count_param.default.default == 1

    # The type is the annotation of the inspect.Parameter
    assert count_param.annotation is int

    # 5. 验证执行
    result = runner.invoke(app, ["--name", "World", "--count", "2"])
    assert result.exit_code == 0
    output = result.stdout + result.stderr
    assert "Hello World Hello World" in output