好的，我们将更新 `cs.cli` 的生成逻辑，使其自动包含 `--log-level` 选项，并确保该值被正确传递给 `cascade.run`。

## [WIP] feat(cli): Add --log-level option to generated CLI

### 用户需求
需要通过 `cs.cli` 生成的命令行应用程序（Typer App）能够接收 `--log-level` 选项，并将其值透明地传递给底层的 `cascade.run` 函数。

### 评论
这个修复是完成日志等级功能链条的关键一步。它将确保用户无论是通过 Python 脚本还是 CLI 运行工作流，都能保持一致的日志控制体验。由于 `log_level` 是 `cs.run` 的固定参数，它需要被硬编码到 CLI 签名中。

### 目标
1.  在 `src/cascade/tools/cli.py` 中，修改 `main` 函数，使其能够提取 `log_level` 并将其传递给 `cascade_run`。
2.  修改元编程逻辑，在生成的 CLI 签名中显式添加 `--log-level` 选项定义，包括帮助文本和默认值。
3.  更新现有测试，确认 `--log-level` 选项出现在帮助信息中。

### 基本原理
`cs.cli` 依赖 Python 的 `inspect` 模块动态构建 Typer 函数签名。我们将手动创建一个 `log_level` 的 `inspect.Parameter` 对象，将其插入到动态签名中。在 `main` 函数的实现中，我们通过 `kwargs.pop()` 提取 `log_level`，然后将其作为关键字参数传递给 `cascade_run`。

### 标签
#intent/build #flow/ready #priority/medium
#comp/cli #comp/runtime #concept/ui #scope/dx
#ai/instruct
#task/domain/cli #task/object/cli-options #task/action/implementation
#task/state/begin

---

### Script

#### Acts 1: 修改 CLI 生成逻辑，添加 `log_level` 选项

修改 `src/cascade/tools/cli.py` 文件中的 `main` 函数和签名生成逻辑，以包含新的 `log_level` 选项。

~~~~~act
patch_file
src/cascade/tools/cli.py
~~~~~
~~~~~python
    def main(**kwargs):
        """The actual function that Typer will wrap."""
        from .. import run as cascade_run

        # Filter out None values so they don't override defaults in cs.run
        run_params = {k: v for k, v in kwargs.items() if v is not None}
        cascade_run(target, params=run_params)

    # --- Metaprogramming to create the dynamic signature ---
    sig_params = []
    for p in params.values():
        # Determine the default value for Typer
~~~~~
~~~~~python
    def main(**kwargs):
        """The actual function that Typer will wrap."""
        from .. import run as cascade_run

        # Extract log_level explicitly since it's injected by Typer via the dynamic signature
        log_level = kwargs.pop("log_level", "INFO")

        # Filter out None values so they don't override defaults in cs.run
        run_params = {k: v for k, v in kwargs.items() if v is not None}
        cascade_run(target, params=run_params, log_level=log_level)

    # --- Metaprogramming to create the dynamic signature ---
    sig_params = []

    # 1. Add log_level as a standard CLI option
    log_level_param = inspect.Parameter(
        name="log_level",
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=typer.Option(
            "INFO",
            "--log-level",
            help="Minimum level for console logging (DEBUG, INFO, WARNING, ERROR).",
        ),
        annotation=str,
    )
    sig_params.append(log_level_param)

    # 2. Add user-defined parameters
    for p in params.values():
        # Determine the default value for Typer
~~~~~

#### Acts 2: 更新 CLI 测试用例

更新 `tests/tools/test_cli.py` 中的帮助信息测试，以确保新的 `--log-level` 选项被正确显示。

~~~~~act
patch_file
tests/tools/test_cli.py
~~~~~
~~~~~python
def test_cli_generator_help_message():
    """Tests that the --help message is generated correctly from Param descriptions."""

    name_param = cs.Param("name", description="The name to greet.")
    count_param = cs.Param(
        "count", default=1, type=int, description="Number of times to greet."
    )

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
~~~~~
~~~~~python
def test_cli_generator_help_message():
    """Tests that the --help message is generated correctly from Param descriptions, including log_level."""

    name_param = cs.Param("name", description="The name to greet.")
    count_param = cs.Param(
        "count", default=1, type=int, description="Number of times to greet."
    )

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
    assert "--log-level" in result.stdout
    assert "Minimum level for console logging" in result.stdout
~~~~~

### 下一步建议
我们已经完成了 `cs.cli` 的更新。现在需要执行测试，如果测试通过，就可以提交本次修改。
