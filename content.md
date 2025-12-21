Got it. I have analyzed the existing documentation. It's clear that the `getting-started.md` tutorial, while functional, doesn't showcase the latest, more intuitive APIs, and the project lacks a centralized guide for contributors.

I will now generate a plan to rectify this, establishing a clear development contract and modernizing the user's first experience.

## [WIP] docs: Create contribution guide and update getting-started tutorial

### 用户需求
1.  **环境规范化**: 记录并推广 `uv pip install -e .[dev]` 作为唯一的开发环境入口。
2.  **教程现代化**: 更新入门教程，展示阶段二引入的“直觉化”特性（如列表依赖、`cs.format`）。
3.  **建立贡献指南**: 创建 `CONTRIBUTING.md` 以固化开发流程。

### 评论
这是提升项目健康度和开发者体验（DX）的关键一步。一个清晰的贡献指南和现代化的入门教程是项目从“能用”到“好用”的标志，能有效降低新贡献者的入门门槛，并确保开发环境的一致性。

### 目标
1.  创建一个新的 `CONTRIBUTING.md` 文件，详细说明开发环境的设置、测试的运行方式和代码风格约定。
2.  重写 `docs/tutorial/getting-started.md`，用一个更简单、更直接的示例来代替当前的 `load_yaml`/`lookup` 流程，并使用新的 `cs.format` provider。
3.  在根 `README.md` 文件中添加一个“For Developers”部分，链接到新的贡献指南。

### 基本原理
我们将使用 `write_file` 创建全新的 `CONTRIBUTING.md` 和 `getting-started.md` 文件，因为内容的改动幅度较大，重写比修补更清晰。对于 `README.md`，我们只需添加一小段内容，因此 `patch_file` 是最合适的工具。

### 标签
#intent/document #flow/ready #priority/medium 
#comp/docs #scope/dx #ai/instruct
#task/domain/docs #task/object/onboarding-docs #task/action/creation
#task/state/begin

---

### Script

#### Acts 1: 创建贡献指南 `CONTRIBUTING.md`

我们将创建一个标准的贡献指南，核心是明确“一键式”的开发环境设置。

~~~~~act
write_file
CONTRIBUTING.md
~~~~~
~~~~~markdown
# Contributing to Cascade

First off, thank you for considering contributing to Cascade! It's people like you that make Cascade such a great tool.

Following these guidelines helps to communicate that you respect the time of the developers managing and developing this open source project. In return, they should reciprocate that respect in addressing your issue or assessing patches and features.

## Getting Started

### Setting Up the Development Environment

The Cascade repository is a monorepo managed with `uv`. We have consolidated all development and testing dependencies into a single `[dev]` extra in the root `pyproject.toml`.

To set up your environment for development, please follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/doucx/Cascade.git
    cd Cascade
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install in editable mode with all dev dependencies:**
    This is the single most important step. This command installs all sub-packages in editable mode and pulls in all dependencies required for testing and documentation.

    ```bash
    uv pip install -e .[dev]
    ```

That's it! Your environment is now ready for development.

### Running Tests

To run the entire test suite, simply execute `pytest` from the root of the repository:

```bash
pytest
```

### Code Style

We will be using `ruff` for linting and formatting. Before submitting a pull request, please run:

```bash
# (Coming soon)
# ruff check .
# ruff format .
```

### Commit Messages

We follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification. This helps us automate changelog generation and makes the project history more readable. Please format your commit messages accordingly.
~~~~~

#### Acts 2: 现代化快速上手教程

我们将重写 `getting-started.md`，使用一个更直观的例子，结合 `cs.shell` 和新的 `cs.format` provider。

~~~~~act
write_file
docs/tutorial/getting-started.md
~~~~~
~~~~~markdown
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
~~~~~

#### Acts 3: 在 README 中添加开发者入口

最后，我们在 `README.md` 中添加一个指向新贡献指南的链接。

~~~~~act
patch_file
README.md
~~~~~
~~~~~markdown
# 安装所有可选依赖 (推荐用于完整体验)
pip install cascade-py[all]
```
~~~~~
~~~~~markdown
# 安装所有可选依赖 (推荐用于完整体验)
pip install cascade-py[all]
```

## 🧑‍💻 For Developers

如果你希望为 Cascade 贡献代码，请查阅我们的贡献指南来设置你的开发环境。

[**👉 查看贡献指南 (CONTRIBUTING.md)**](CONTRIBUTING.md)
~~~~~
