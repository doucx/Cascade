这是一个合理的 Typer 类型推断问题。当 `cs.Param` 没有显式指定 `type` 且没有默认值时，其 `type` 属性为 `None`。将 `annotation=None` 传递给生成的函数签名会导致 Typer 无法确定如何解析该命令行参数，从而抛出 `RuntimeError: Type not yet supported: None`。

鉴于命令行参数本质上是字符串，当用户没有明确指定类型时，将其默认为 `str` 是最安全且符合直觉的处理方式。

我将生成一个计划来修复这个问题。

## [WIP] fix: 为 CLI 生成器中的未类型化参数设置默认类型

### 用户需求
修复 `tests/tools/test_cli.py` 中的 `RuntimeError: Type not yet supported: None`。该错误发生于 `cs.Param` 未指定 `type` 时，导致 Typer 无法推断参数类型。

### 评论
这是一个边界情况处理。虽然我们在 `cs.Param` 中允许 `type=None`，但在构建强类型的 CLI 时，必须有一个明确的类型。将 `str` 作为默认回退类型是合理的，因为它能够接收任何输入，并将验证责任留给下游逻辑（如果需要）。这将确保 `cs.cli` 对简单的、未完全类型化的工作流也能“开箱即用”。

### 目标
修改 `src/cascade/tools/cli.py`，在构建函数签名时，如果 `Param.type` 为 `None`，则强制将 `annotation` 设置为 `str`。

### 基本原理
Typer 依赖 Python 的类型注解来决定如何解析命令行参数（例如，将输入解析为整数还是保留为字符串）。如果没有注解，Typer 就会不知所措。由于 CLI 输入本质上是文本，`str` 是最通用的默认类型。

### 标签
#intent/fix #flow/ready #priority/high #comp/core #scope/bugfix #ai/instruct #task/domain/tooling #task/object/cli-generator #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修正 `cli.py` 中的类型处理

我们将修改 `cli` 函数中的循环逻辑，增加对 `p.type` 为 `None` 的检查。

~~~~~act
patch_file
src/cascade/tools/cli.py
~~~~~
~~~~~python
        # Create the Typer Option with all relevant info
        option = typer.Option(
            default,
            f"--{p.name}",
            help=p.description,
        )

        sig_param = inspect.Parameter(
            name=p.name,
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=option,
            annotation=p.type,
        )
        sig_params.append(sig_param)
~~~~~
~~~~~python
        # Create the Typer Option with all relevant info
        option = typer.Option(
            default,
            f"--{p.name}",
            help=p.description,
        )

        # Default to str if no type is provided, as CLI args are inherently strings
        annotation = p.type if p.type is not None else str

        sig_param = inspect.Parameter(
            name=p.name,
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=option,
            annotation=annotation,
        )
        sig_params.append(sig_param)
~~~~~

### 下一步建议
这应该能彻底解决测试失败的问题。如果测试通过，我们就可以着手提交 `cs.cli` 功能了。
