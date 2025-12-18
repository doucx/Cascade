好的，我明白了。这个新的错误非常具有指导性。

我的上一个计划在逻辑上是正确的——修复导入路径——但它引入了一个新的、与构建系统（`hatchling`）相关的问题。我移除了 `[tool.hatch.build.targets.wheel]`，是想让根项目成为一个纯粹的“虚拟”工作区，但 `hatchling` 在被要求构建一个可编辑的包（`uv pip install -e .` 的操作）时，仍然需要明确的指令来知道哪些文件构成了这个名为 `cascade` 的根包。

错误信息 `ValueError: Unable to determine which files to ship inside the wheel` 明确地告诉我们，`hatchling` 找不到一个名为 `cascade` 的目录来打包，因此构建失败。

解决方案是将根 `pyproject.toml` 调整为一个正确的**聚合器包（Aggregator Package）**。它本身是一个有效的、可安装的包，其主要职责是：
1.  将 `packages/cascade-py/src/cascade` 作为 `cascade` 包的源代码。
2.  在其 `dependencies` 中明确声明它依赖于工作区中的所有其他包（`cascade-interfaces`, `cascade-runtime` 等）。

我将生成一个计划来纠正这个配置。

## [WIP] fix(monorepo): 修复根 pyproject.toml 的构建和依赖配置

### 错误分析
安装命令 `uv pip install -e ".[dev]"` 失败，并显示 `hatchling` 构建错误。根本原因在于，在我上一次的修改中，我从根 `pyproject.toml` 文件中移除了 `[tool.hatch.build.targets.wheel]` 配置节。

这一移除导致 `hatchling` 在尝试构建名为 `cascade` 的根包时，无法找到任何源文件。`hatchling` 的默认行为是寻找一个与项目同名的目录（即 `cascade/`），但该目录在项目根目录下并不存在。

此外，根 `pyproject.toml` 的 `[project]` 部分也缺少一个关键的 `dependencies` 列表。作为一个聚合器包，它必须明确声明它依赖于工作区中的所有其他子包。没有这个声明，即使安装成功，包之间的依赖关系也是不完整的。

### 用户需求
修复 `pyproject.toml` 的配置，使 `uv pip install -e ".[dev]"` 能够成功执行，并正确安装所有工作区内的包及其依赖项。

### 评论
这是一个典型的 monorepo 配置问题。通过将根项目配置为一个有效的“聚合器”包，我们为 `hatchling` 和 `uv` 提供了清晰的指令，既解决了构建问题，也正确地建立了包之间的依赖关系。这个修复是使多包架构正常工作的最后一步。

### 目标
1.  恢复根 `pyproject.toml` 中的 `[tool.hatch.build.targets.wheel]` 配置，并将其指向正确的源目录 (`packages/cascade-py/src/cascade`)。
2.  在根 `pyproject.toml` 的 `[project]` 表中添加一个 `dependencies` 列表，明确声明对所有 `cascade-*` 子包的依赖。
3.  （可选但推荐）简化 `[project.optional-dependencies.dev]` 中的 `typer[all]` 为 `typer`，以提高兼容性。

### 基本原理
通过恢复 `[tool.hatch.build.targets.wheel]`，我们告诉 `hatchling`：“当你构建 `cascade` 这个包时，它的源代码在 `packages/cascade-py/src/cascade`。” 这解决了构建错误。

通过添加 `dependencies`，我们告诉 `pip`/`uv`：“当你安装 `cascade` 这个包时，请同时确保 `cascade-interfaces`, `cascade-runtime` 等包也被安装。” `uv` 的工作区解析器会智能地从本地路径 (`packages/*`) 安装这些依赖，而不是去 PyPI 查找。这两个修改共同确保了整个 monorepo 能够被正确地构建和安装为一个连贯的整体。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #scope/dx #ai/instruct #task/domain/build #task/object/packaging-metadata #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复根 `pyproject.toml` 的构建和依赖配置

我们将一次性修复 `pyproject.toml`，恢复构建目标，添加核心依赖，并清理开发依赖。

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
dependencies = [
    "cascade-interfaces",
    "cascade-runtime",
    "cascade-py",
    "cascade-cli",
]

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
cascade-interfaces = { workspace = true }
cascade-runtime = { workspace = true }
cascade-py = { workspace = true }
cascade-cli = { workspace = true }

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
  "typer",
  "mkdocs",
  "mkdocs-material",
  "mkdocstrings[python]",
]

[tool.hatch.metadata]
allow-direct-references = true
~~~~~

### 下一步建议
这次的 `pyproject.toml` 文件是完整且正确的，它定义了一个有效的聚合器包。现在请再次运行安装和测试命令，问题应该已得到彻底解决。

1.  **重新安装**:
    ```bash
    uv pip install -e ".[dev]"
    ```
2.  **运行测试**:
    ```bash
    pytest
    ```
