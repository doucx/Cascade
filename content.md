I will now create a plan that uses this correct, albeit deeply nested, API path to finally implement the robust test we've been aiming for.

## [WIP] fix(testing): Use correct signature API to inspect Typer command parameters

### 用户需求
Fix the third consecutive failure, an `AttributeError`, in the `test_cli_generator_from_context` test.

### 评论
This iterative debugging process has been invaluable. After two incorrect assumptions, we have now pinpointed the precise location of the parameter definitions within the `typer` object model. This fix will finally achieve the goal of a robust, UI-independent test for our CLI generator.

### 目标
1.  Modify `test_cli_generator_from_context` to use the correct API path: `app.registered_commands[0].callback.__signature__.parameters`.
2.  Update the subsequent assertion lines to correctly access the `help` text, `default` value, and `type` from the retrieved `inspect.Parameter` and nested `typer.Option` objects.

### 基本原理
The test will be rewritten to perform the following inspection steps:
1.  Access the list of registered commands: `app.registered_commands`.
2.  Get the first (and only) command's `CommandInfo` object: `[0]`.
3.  Get the command's underlying function: `.callback`.
4.  Get that function's signature object: `.__signature__`.
5.  Get the dictionary of parameters: `.parameters`.
6.  For each parameter, inspect its `default` attribute (which is the `typer.Option` object) and its `annotation` attribute (which is the type).

### 标签
#intent/fix #flow/ready #priority/critical #comp/sdk #comp/tests #scope/dx #ai/instruct

---
### Script

#### Acts 1: Rewrite the test with the correct Typer introspection API

Given the multiple changes required in the assertion block, we will use `write_file` to replace the entire test function with the corrected version.

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
~~~~~
