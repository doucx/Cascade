# 快速上手

本教程将引导你完成第一个 `Cascade` 应用的创建。只需一分钟，你就能体验到声明式工作流的简洁与强大。

## 1. 安装

`Cascade` 支持 Python 3.8+。我们将安装核心库以及运行 `shell` 命令所需的功能。

```bash
pip install "cascade-py"
```

> 注意：根据你的 shell 配置，你可能需要使用 `pip3`。

## 2. 您的第一个 Cascade 应用

我们的目标是：运行一个 shell 命令来统计当前目录下的文件数量，然后将结果格式化成一句问候语。

### 步骤 1：创建 Python 脚本

在你的项目目录下，创建一个名为 `app.py` 的文件：

```python
# app.py
import cascade as cs

# 1. 定义一个参数，用于在运行时接收用户名。
user_name = cs.Param("name", default="Guest")

# 2. 声明一个执行 shell 命令的任务。
#    这将创建一个 LazyResult，它代表了未来 shell 命令的输出结果。
#    注意我们如何像乐高积木一样将多个命令通过管道连接起来。
file_count = cs.shell("ls -1 | wc -l")

# 3. 使用新的 cs.format 来组合最终的输出字符串。
#    它清晰地声明了 greeting 依赖于 user_name 和 file_count 的结果。
greeting = cs.format(
    "Hello, {name}! There are {count} files in this directory.",
    name=user_name,
    count=file_count
)

# 4. 运行工作流并请求最终结果。
if __name__ == "__main__":
    print("开始运行 Cascade 工作流...")
    # 调用 run() 时，Cascade 会自动构建依赖图并按正确顺序执行所有任务。
    final_message = cs.run(greeting, params={"name": "Developer"})
    
    print("\n工作流完成！")
    print(final_message)
```

### 步骤 2：运行它！

打开你的终端，运行脚本。`Cascade` 会自动将 `params` 字典中的 `name` 注入到工作流中。

```bash
$ python app.py
```

你应该会看到类似如下的输出：

```
开始运行 Cascade 工作流...
▶️  Running workflow for target: format
   - with params: {'name': 'Developer'}
   - Task '_get_param_value' started.
   - ✅ Task '_get_param_value' succeeded in 0.00s.
   - Task 'shell' started.
   - ✅ Task 'shell' succeeded in 0.01s.
   - Task 'format' started.
   - ✅ Task 'format' succeeded in 0.00s.
✅ Run finished successfully in 0.01s.

工作流完成！
Hello, Developer! There are 5 files in this directory.
```

恭喜！你刚刚构建了一个简洁、可读且完全类型安全的 `Cascade` 工作流。你已经掌握了声明任务、定义参数和组合结果的核心概念。

在接下来的指南中，我们将深入探索 `Cascade` 的更多强大功能。