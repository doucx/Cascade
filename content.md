好的，我们来完成文档的最后一部分：**参考 (Reference)**。

我将为你生成 `cs.cli` 工具的文档。这篇参考文档将是技术性的、以示例为导向的，旨在精确地告诉开发者如何使用这个强大的工具。

## [WIP] docs: 填充 `cs.cli` 工具参考文档

### 用户需求
为 `cs.cli` 工具创建一篇详细的参考文档，解释其功能、用法和工作原理，并将其填充到 `docs/reference/cli-tools.md` 文件中。

### 评论
`cs.cli` 是 `Cascade` 开发者体验 (DX) 的一个亮点功能，它将声明式工作流的强大能力暴露给了命令行。一篇好的参考文档需要清晰地展示如何将 `cs.Param` 对象映射到命令行选项，并提供一个完整的、可运行的示例。

### 目标
1.  撰写 `cs.cli` 的功能说明和使用示例。
2.  将内容写入 `docs/reference/cli-tools.md` 文件。

### 基本原理
参考文档应该精确且实用。我将遵循以下结构：
1.  **功能概述**：清晰地列出 `cs.cli` 的核心能力。
2.  **使用方法**：提供一个完整的、从定义工作流到在终端中运行的端到端示例。
3.  **工作原理**：简要说明其背后的机制（图检查与动态生成），以满足好奇用户的求知欲，并增强他们对 `Cascade` 设计的理解。

### 标签
#intent/document #flow/ready #priority/medium #comp/docs #scope/dx #ai/delegate #task/domain/docs #task/object/content-population #task/action/write #task/state/continue

---

### Script

#### Acts 1: 撰写并填充 `cs.cli` 工具参考文档

我们将把精心撰写的参考内容写入 `cli-tools.md` 文件中。

~~~~~act
write_file
docs/reference/cli-tools.md
~~~~~
~~~~~markdown
# 参考：CLI 工具 (`cs.cli`)

`Cascade` 提供了一个强大的实用工具 `cs.cli`，它可以**自动**从你的工作流定义中生成一个功能完备的命令行接口 (Command-Line Interface, CLI)。

这意味着你无需编写任何 `argparse` 或 `typer` 的模板代码，就能将你的 `Cascade` 脚本变成一个专业的、自文档化的命令行工具。

## 核心功能

*   **自动参数发现**: `cs.cli` 会检查你的工作流依赖图，并自动为你定义的每一个 `cs.Param` 对象创建一个对应的命令行选项（例如，`--name`）。
*   **智能帮助信息**: 自动将 `cs.Param` 的 `description` 字段内容用作该选项的 `--help` 帮助文本。
*   **类型与默认值**: 自动处理 `cs.Param` 中定义的类型（如 `int`, `bool`）和 `default` 值。
*   **零配置**: 你唯一需要做的，就是将你工作流最终的 `LazyResult` 传入 `cs.cli()` 函数。

## 使用方法

让我们通过一个例子来看看它是如何工作的。

### 步骤 1: 定义带参数的工作流

创建一个名为 `greeter.py` 的文件。在这个文件中，我们定义一个工作流，它依赖于两个参数：`name` 和 `count`。

```python
# greeter.py
import cascade as cs

# 1. 定义将在 CLI 中暴露的参数
name_param = cs.Param("name", description="要问候的人的姓名。")
count_param = cs.Param("count", default=1, type=int, description="问候的次数。")

# 2. 定义执行核心逻辑的任务
@cs.task
def generate_greeting(name: str, count: int) -> str:
    """生成重复的问候语。"""
    return "\n".join([f"Hello, {name}!" for _ in range(count)])

@cs.task
def print_to_console(greeting: str):
    """一个简单的任务，只是为了将结果打印出来。"""
    print(greeting)

# 3. 将所有部分连接起来，形成最终的工作流目标
workflow = print_to_console(
    generate_greeting(name=name_param, count=count_param)
)

# 4. 使用 cs.cli 生成并运行应用
if __name__ == "__main__":
    app = cs.cli(workflow)
    app()
```

### 步骤 2: 在终端中使用

现在，你的 `greeter.py` 脚本已经是一个功能齐全的 CLI 工具了。

#### 查看帮助信息

你可以运行 `--help` 来查看自动生成的帮助文档。

```console
$ python greeter.py --help

  Usage: greeter.py [OPTIONS]

  Runs the Cascade workflow.

  Options:
    --name TEXT    要问候的人的姓名。  [required]
    --count INTEGER  问候的次数。  [default: 1]
    --help           Show this message and exit.
```
注意 `description` 是如何完美地变成了帮助文本的。

#### 运行工作流

现在，通过命令行传递参数来运行你的工作流。

```console
$ python greeter.py --name Cascade --count 2
Hello, Cascade!
Hello, Cascade!
```

如果你不提供可选参数，它会自动使用默认值。

```console
$ python greeter.py --name World
Hello, World!
```

## 工作原理

`cs.cli` 的“魔法”遵循 `Cascade` 的核心哲学：

1.  当你调用 `cs.cli(workflow)` 时，它并不会立即执行。
2.  它接收你的最终 `LazyResult`，并在内部调用 `build_graph()` 来构建完整的依赖图。
3.  它遍历图中的所有节点，并找出所有 `node_type` 为 `"param"` 的节点。
4.  对于每一个 `Param` 节点，它读取其元数据（`name`, `default`, `type`, `description`）。
5.  借助 Python 的 `inspect` 模块和 `typer` 库，它**动态地**创建一个新的 Python 函数，该函数的签名与所有 `Param` 选项完全匹配。
6.  最后，它将这个动态生成的函数注册为一个 `typer` 命令，并返回 `typer` 应用。

这正是 `Cascade` 将声明式定义转化为实际可用工具的强大能力的体现。
~~~~~

### 下一步建议
我们已经完成了所有计划中的文档填充工作！`tutorial`, `how-to-guides`, `concepts`, 和 `reference` 的主要页面现在都有了内容。

最后一步是 **`API 参考`**。`docs/reference/api.md` 文件已经准备好接收 `mkdocstrings` 的自动生成内容。

现在，我建议执行一次**完整性提交流程**，将本次所有关于文档的工作（添加依赖、创建文件结构、填充内容）作为一个完整的、有意义的功能提交到版本控制中。这标志着“文档系统建立”这个宏观任务的圆满完成。

如果你同意，我将为你生成一个 `[COMMIT]` 计划。
