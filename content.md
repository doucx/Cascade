好的，我分析了新的错误。你的诊断是正确的，我们离成功很近了，但还有一个配置问题。

之前的修复是正确的，它解决了代码内部的 `import` 语句问题。然而，新的错误 `ModuleNotFoundError: No module named 'cascade.interfaces'` 指向了一个更深层次的、关于**包元数据（Packaging Metadata）**的问题。

## [WIP] fix(monorepo): 纠正根 pyproject.toml 的打包配置

### 错误分析
尽管我们已经将所有 Python 文件中的 `import` 语句修正为绝对路径，但 `pytest` 仍然无法找到 `cascade.interfaces` 模块。这表明问题出在**安装阶段**，而不是代码本身。

根本原因在于项目根目录的 `pyproject.toml` 文件中存在一个错误的配置节：
```toml
[tool.hatch.build.targets.wheel]
packages = ["packages/cascade-py/src/cascade"]
```
这个配置错误地告诉打包工具（如 `hatch` 和 `uv`），当构建或安装根项目 `cascade` 时，其源代码**只**来源于 `packages/cascade-py/src/cascade` 目录。因此，在可编辑（editable）安装模式下，Python 解释器只被告知去这个目录里寻找 `cascade` 模块。这直接导致了 `cascade-interfaces`、`cascade-runtime` 等其他包提供的命名空间（如 `cascade.interfaces`）完全不可见，从而引发 `ModuleNotFoundError`。

对于一个工作区（workspace）的根配置文件来说，它本身不应该定义一个具体的、可构建的包，而应作为一个**虚拟清单（virtual manifest）**，其作用是聚合工作区内的其他包。

### 用户需求
彻底解决 `ModuleNotFoundError`，使得 `pytest` 能够成功加载并运行所有测试。

### 评论
这是一个微妙但关键的打包配置错误。修复它将使项目的多包架构与现代 Python 打包工具（如 `uv` 和 `hatch`）的工作方式完全对齐，确保可编辑安装能够正确地将所有子包的源目录暴露给 Python 解释器，从而形成一个统一的 `cascade` 命名空间。

### 目标
1.  修改项目根目录的 `pyproject.toml` 文件。
2.  移除其中错误的 `[tool.hatch.build.targets.wheel]` 配置节。
3.  保留并依赖 `[tool.uv.workspace]` 和根项目的 `[project.dependencies]` 来正确地聚合和安装所有子包。

### 基本原理
通过移除根 `pyproject.toml` 中不正确的 `[tool.hatch.build.targets.wheel]` 部分，我们消除了关于 `cascade` 包来源的错误元数据。这将允许 `uv pip install -e .` 正确地识别这是一个工作区，并根据 `[project.dependencies]` 和 `[tool.uv.sources]` 的配置，为**每一个**子包（`cascade-interfaces`, `cascade-runtime`, `cascade-py`, `cascade-cli`）创建正确的路径链接。这样，Python 解释器在 `import cascade.interfaces` 时，就能成功地在 `packages/cascade-interfaces/src` 目录中找到它。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #scope/dx #ai/instruct #task/domain/build #task/object/packaging-metadata #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修正根 `pyproject.toml`

我们将移除错误的 `[tool.hatch.build.targets.wheel]` 配置节，让根项目作为一个纯粹的工作区聚合器。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
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
~~~~~
~~~~~toml
[tool.hatch.workspaces]
packages = [
    "packages/cascade-interfaces",
    "packages/cascade-runtime",
    "packages/cascade-py",
    "packages/cascade-cli",
]

[tool.pytest.ini_options]
addopts = "-ra"
~~~~~

### 下一步建议
这个修改是解决问题的关键。请再次运行安装和测试命令。这一次，`uv` 应该能够正确地为所有子包设置可编辑模式的路径，从而解决 `ModuleNotFoundError`。

1.  **重新安装**:
    ```bash
    uv pip install -e ".[dev]"
    ```
2.  **运行测试**:
    ```bash
    pytest
    ```
