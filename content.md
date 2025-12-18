简要回答：
构建失败是因为在 `project.dependencies` 中使用了相对路径 (`@ file:../...`)，这在构建 Wheel 时会导致路径解析错误。正确的 Monorepo 实践是：在 `dependencies` 中仅声明包名，通过 `uv` 的 Workspace 机制来解析本地路径。

## [WIP] fix(build): 移除硬编码文件路径依赖并配置 UV Workspace

### 错误分析
错误 `relative path without a working directory: ../cascade-py` 表明构建后端无法将相对路径依赖写入 Wheel 的元数据。
此外，根目录 `pyproject.toml` 中使用了非标准的 `${PROJECT_ROOT}` 变量，这也会导致解析失败。

### 用户需求
修复构建依赖关系，使得 `uv pip install -e ".[dev]"` 能够成功执行。

### 目标
1.  将所有子包 (`cascade-cli`, `cascade-py`, `cascade-runtime`) 的依赖声明回退为纯包名（移除 `@ file:...`）。
2.  将根目录 `pyproject.toml` 的依赖声明回退为纯包名。
3.  在根目录 `pyproject.toml` 中配置 `[tool.uv.workspace]`，启用自动本地包发现。

### 基本原理
通过将依赖声明与依赖源分离（Dependency Declaration vs Resolution），我们遵循了 Python 打包的最佳实践。`project.dependencies` 只描述“需要什么”，而 `tool.uv.workspace` 告诉工具“去哪里找”。这既解决了构建错误，也保持了包未来发布到 PyPI 的可能性。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #concept/config #scope/dx #ai/instruct #task/domain/devops #task/object/monorepo-config #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 `cascade-cli` 依赖
移除 `file:` 引用。

~~~~~act
patch_file
packages/cascade-cli/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
  "cascade-py @ file:../cascade-py",
  "typer"
]
~~~~~
~~~~~toml
dependencies = [
  "cascade-py",
  "typer"
]
~~~~~

#### Acts 2: 修复 `cascade-py` 依赖
移除 `file:` 引用。

~~~~~act
patch_file
packages/cascade-py/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
  "cascade-interfaces @ file:../cascade-interfaces",
  "cascade-runtime @ file:../cascade-runtime"
]
~~~~~
~~~~~toml
dependencies = [
  "cascade-interfaces",
  "cascade-runtime"
]
~~~~~

#### Acts 3: 修复 `cascade-runtime` 依赖
移除 `file:` 引用。

~~~~~act
patch_file
packages/cascade-runtime/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
  "cascade-interfaces @ file:../cascade-interfaces"
]
~~~~~
~~~~~toml
dependencies = [
  "cascade-interfaces"
]
~~~~~

#### Acts 4: 修复根目录 `pyproject.toml` 并启用 Workspace
移除 `file:` 引用及错误的 `${PROJECT_ROOT}` 变量，添加 `[tool.uv.workspace]` 配置。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
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
~~~~~
~~~~~toml
# 关键修复 2: 添加对工作区内所有包的显式依赖
dependencies = [
    "cascade-interfaces",
    "cascade-runtime",
    "cascade-py",
    "cascade-cli",
]

[tool.uv.workspace]
members = ["packages/*"]

[tool.hatch.workspaces]
packages = [
    "packages/cascade-interfaces",
    "packages/cascade-runtime",
    "packages/cascade-py",
    "packages/cascade-cli",
]
~~~~~

### 下一步建议
再次运行 `uv pip install -e ".[dev]"`。这次 `uv` 应该能通过 Workspace 机制自动解析所有本地包，而不会触发 Hatchling 的路径构建错误。
