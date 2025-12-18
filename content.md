你的分析非常敏锐，观察到了两个关键问题。

1.  `warning: The package typer==0.20.0 does not have an extra named all`
2.  "安装的包比预想的少" (Fewer packages were installed than expected)

这两个问题指向了我们根 `pyproject.toml` 中的两个不同但相关的配置缺陷。我将为你生成一个计划来一次性修复它们。

***

你的分析完全正确，安装结果确实不符合预期。这暴露出我们根 `pyproject.toml` 文件的一个核心配置问题。

## [COMMIT] fix(build): Add explicit workspace dependencies to root pyproject

### 错误分析

你遇到的安装问题由两个独立的配置错误导致：

**问题一：依赖项声明错误**
`uv` 的警告 `warning: The package typer==0.20.0 does not have an extra named all` 非常精确。较新版本的 `typer` 已经将所有依赖项内置，不再需要（也不支持）`[all]` 这个 "extra"。这是一个直接的语法错误，需要修正。

**问题二：Monorepo 依赖关系不完整（核心问题）**
你观察到“安装的包比预想的少”是问题的关键所在。当你运行 `uv pip install -e .` 时，`uv` 只安装了根项目 `cascade`，而完全忽略了 `packages/` 目录下的其他包。

原因在于：
*   `[tool.hatch.workspaces]` 配置节是给 `hatch` **工具链** 使用的，它告诉 `hatch` 在运行 `hatch run test` 等命令时需要管理哪些子项目。
*   然而，对于 `pip` 或 `uv` 这样的 **安装器** 来说，这个配置节是不可见的。安装器只关心 `[project]` 表中定义的依赖关系。
*   我们当前的根 `pyproject.toml` 文件定义了一个名为 `cascade` 的项目，但**没有在其 `[project.dependencies]` 中声明它依赖于 `cascade-interfaces`、`cascade-runtime` 等本地包**。

因此，`uv` 忠实地执行了指令：只安装了 `cascade` 这一个包，而没有理由去安装工作区中的其他成员。

### 用户需求
修正项目根 `pyproject.toml` 的配置，确保当用户执行 `uv pip install -e '.[dev]'` 时，能够：
1.  正确无误地解析所有可选依赖（修复 `typer` 的问题）。
2.  将工作区中的所有本地包（`cascade-interfaces`, `cascade-runtime`, `cascade-py`, `cascade-cli`）作为根项目的依赖一并安装。

### 评论
这是一个至关重要的修复，它使我们的 Monorepo 从一个“名义上的集合”转变为一个“真正可安装的整体”。通过让根项目显式依赖于所有子包，我们为开发者提供了一个“一键安装”的入口点，极大地改善了开发环境的设置体验（DX），并确保了整个生态系统的一致性。

### 目标
1.  修改 `pyproject.toml` 中 `[project.optional-dependencies.dev]` 的内容，将 `typer[all]` 修正为 `typer`。
2.  在 `pyproject.toml` 中添加 `[project.dependencies]` 表。
3.  在该表中，使用 PEP 508 路径依赖语法，明确声明根项目 `cascade` 依赖于所有 `packages/*` 子包。

### 基本原理
我们将通过一次 `write_file` 操作，完整替换根 `pyproject.toml` 的内容。
-   **修复 `typer`**: 直接修改字符串，消除警告。
-   **添加依赖**: 增加一个新的 `[project.dependencies]` 节。在该节中，我们使用 `package-name @ file:///${PROJECT_ROOT}/path/to/package` 的形式。这是一种现代、明确且健壮的方式，用于声明对本地文件系统上其他包的依赖，`uv` 和 `pip` 都能很好地理解这种语法。这使得我们的根项目 `cascade` 变成了一个“元包”，其唯一的职责就是将整个项目生态聚合在一起。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #scope/dx #ai/instruct #task/domain/build #task/object/monorepo-structure #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正并完善根 `pyproject.toml`

此操作将使用一个完整的、修正后的版本覆盖根 `pyproject.toml` 文件，以解决依赖声明错误和工作区依赖关系不完整的问题。

~~~~~act
write_file
pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade"
version = "0.1.0"
description = "A modern, declarative automation library for Python."
readme = "README.md"
requires-python = ">=3.8"
license = "MIT"
# 关键修复 2: 添加对工作区内所有包的显式依赖
dependencies = [
    "cascade-interfaces @ file:///${PROJECT_ROOT}/packages/cascade-interfaces",
    "cascade-runtime @ file:///${PROJECT_ROOT}/packages/cascade-runtime",
    "cascade-py @ file:///${PROJECT_ROOT}/packages/cascade-py",
    "cascade-cli @ file:///${PROJECT_ROOT}/packages/cascade-cli",
]

[tool.hatch.workspaces]
packages = [
    "packages/cascade-interfaces",
    "packages/cascade-runtime",
    "packages/cascade-py",
    "packages/cascade-cli",
]

[tool.hatch.build.targets.wheel]
packages = ["packages/cascade-py/src/cascade"]

[tool.pytest.ini_options]
addopts = "-ra"

[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "mypy",
  "pytest-aiohttp",
  "moto[s3]",
  # 关键修复 1: 移除 "[all]"
  "typer",
  "mkdocs",
  "mkdocs-material",
  "mkdocstrings[python]",
]
~~~~~

### 下一步建议
我们已经修复了构建和安装的所有已知问题。现在，整个项目的结构和元数据都已准备就绪。

1.  **再次运行安装**:
    ```bash
    uv pip install -e ".[dev]"
    ```
    这一次，你应该会看到 `uv` 成功解析并安装了 `cascade` 以及所有 `cascade-*` 子包。

2.  **准备修复代码**:
    安装成功后，我们终于可以回到最初的目标：修复因文件移动而损坏的所有 Python `import` 语句。这是让项目重新变得可运行的最后一步。

我已准备好为你生成一个全面修复 `import` 路径的计划。请确认是否继续。
