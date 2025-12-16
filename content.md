非常抱歉，这是一个 API 使用错误。在 `Typer` 中，参数的类型是通过 Python 的**类型注解 (Type Hints)** 传递给函数的，而不是作为参数传递给 `typer.Option()` 构造函数。

`typer.Option()` 负责定义 CLI 行为（如默认值、帮助文本、标志名称），而参数的解析和验证逻辑是由 Typer 检查函数签名中的 `annotation` 来自动处理的。我们在 `inspect.Parameter` 中已经正确设置了 `annotation`，因此 `typer.Option` 中的 `type` 参数不仅是多余的，而且是错误的。

我将生成一个计划来移除这个错误的参数。

## [WIP] fix: 移除 `typer.Option` 中错误的 `type` 参数

### 用户需求
修复 `src/cascade/tools/cli.py` 中的 `TypeError`，该错误是由于向 `typer.Option` 传递了不支持的 `type` 参数引起的。

### 评论
这是一个对 Typer 库 API 的误解。Typer 及其底层 Click 库的设计哲学是利用 Python 原生的类型注解系统。在我们的动态 CLI 生成逻辑中，类型信息已经通过 `inspect.Parameter(..., annotation=p.type)` 正确传递给了生成的函数签名。因此，只需从 `Option` 调用中移除该参数即可解决问题，且不会丢失类型验证功能。

### 目标
修改 `src/cascade/tools/cli.py`，在创建 `typer.Option` 实例时，移除 `type=p.type` 这一行。

### 基本原理
`typer.Option` 的构造函数签名不包含 `type`。类型推断完全依赖于函数参数的注解。

### 标签
#intent/fix #flow/ready #priority/high #comp/core #scope/bugfix #ai/instruct #task/domain/tooling #task/object/cli-generator #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修正 `cli.py`

移除 `typer.Option` 调用中错误的 `type` 参数。

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
            # Typer can infer type from default, but explicit is better
            type=p.type,
        )
~~~~~
~~~~~python
        # Create the Typer Option with all relevant info
        option = typer.Option(
            default,
            f"--{p.name}",
            help=p.description,
        )
~~~~~

### 下一步建议
修复此错误后，`tests/tools/test_cli.py` 应该能够通过。

如果测试通过，我们就完成了 `cs.cli` 的所有实现工作，可以准备创建 `[COMMIT]` 计划了。
