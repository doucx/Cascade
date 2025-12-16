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