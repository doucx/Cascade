你的分析完全正确。

我之前的计划在创建一个名为 `cascade` 的新包时，与根目录中同样名为 `cascade` 的项目发生了冲突。`uv` 在扫描工作区时发现了两个都想成为 `cascade` 的成员，因此报错。这是我的失误。

解决方案是明确责任：
1.  **根 `pyproject.toml`** 应作为 `cascade` 这个最终用户包的**唯一、权威的定义文件**。
2.  **`packages/cascade-python`** 目录应只作为该包的**源代码位置**，而不应拥有自己的 `pyproject.toml`，从而不被视为一个独立的 workspace member。

我将生成一个计划来纠正这个结构问题。

## [WIP] fix: 解决 uv 工作区中 `cascade` 包的命名冲突

### 摘要
本计划修正了因 `cascade-python` 包与根项目同名而导致的 `uv` 构建失败问题。通过移除 `cascade-python` 的 `pyproject.toml` 并将根项目配置为从该目录构建，我们确保了 `cascade` 包在工作区中只有一个权威定义。

### 错误分析
`uv` 报错 `Two workspace members are both named cascade`，因为根 `pyproject.toml` 和 `packages/cascade-python/pyproject.toml` 都定义了一个名为 `cascade` 的项目。这在工作区配置中是明确的冲突。

### 用户需求
修复构建错误，使 `uv pip install -e .[dev]` 能够成功执行。

### 评论
这是一个典型的 Monorepo 配置陷阱。将包的定义（`pyproject.toml`）与其源代码的物理位置分离是解决此类问题的关键。此修复将使我们的项目结构更加健壮和清晰。

### 目标
1.  将 `packages/cascade-python` 降级为纯源代码目录。
2.  更新根 `pyproject.toml`，使其成为 `cascade` 包的唯一声明，并从 `packages/cascade-python` 构建。
3.  整合 `cascade` 包的核心依赖项到根 `pyproject.toml` 中。

### 基本原理
通过移除冲突的 `pyproject.toml`，`uv` 的工作区扫描器将不再视 `packages/cascade-python` 为一个独立的成员。同时，通过修改根 `pyproject.toml` 的 `tool.hatch.build.targets.wheel.packages` 指令，我们告诉构建系统在哪里找到 `cascade` 包的源代码，从而将定义和实现解耦。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #scope/core #task/domain/core #task/object/cascade-python #task/action/restructure #task/state/continue

---

### Script

#### Acts 1: 移除冲突的包定义
删除 `cascade-python` 的 `pyproject.toml`，使其不再被 `uv` 视为一个独立的 workspace member。

~~~~~act
delete_file
packages/cascade-python/pyproject.toml
~~~~~

#### Acts 2: 修正根 `pyproject.toml`
更新根 `pyproject.toml`，使其成为 `cascade` 包的唯一权威定义，并指向正确的源代码位置和依赖。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[project]
name = "cascade"
version = "0.1.0"
description = "A modern, declarative automation library for Python."
readme = "README.md"
requires-python = ">=3.8"
license = "Apache-2.0"
dependencies = [
    "cascade-spec",
    "cascade-engine",
    "cascade-sdk",
    "cascade-graph",
    "cascade-library",
]

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
cascade-graph = { workspace = true }
cascade-library = { workspace = true }
cascade-application = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
cascade-compiler = { workspace = true }
cascade-vm = { workspace = true }
cascade = { path = "packages/cascade-python", editable = true }

[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-engine",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
    "packages/cascade-graph",
    "packages/cascade-library",
    "packages/cascade-connector-local",
    "packages/cascade-compiler",
    "packages/cascade-vm",
    "packages/cascade-python",
]

[tool.hatch.build.targets.wheel]
packages = ["packages/cascade-python/src/cascade"]
~~~~~
~~~~~toml.new
[project]
name = "cascade"
version = "0.1.0"
description = "The official Python SDK for Cascade."
readme = "README.md"
requires-python = ">=3.8"
license = "Apache-2.0"
dependencies = [
    "cascade-spec",
    "cascade-common",
    "cascade-graph",
    "cascade-engine",
    "cascade-application",
    "cascade-library",
    "cascade-cli-controller",
    "cascade-cli-observer",
]

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
cascade-graph = { workspace = true }
cascade-library = { workspace = true }
cascade-application = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
cascade-compiler = { workspace = true }
cascade-vm = { workspace = true }
cascade-python = { path = "packages/cascade-python", editable = true }

[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-engine",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
    "packages/cascade-graph",
    "packages/cascade-library",
    "packages/cascade-connector-local",
    "packages/cascade-compiler",
    "packages/cascade-vm",
    "packages/cascade-python",
]

[tool.hatch.build.targets.wheel]
packages = ["packages/cascade-python/src/cascade"]
~~~~~

#### Acts 3: 修正 `cascade-sdk` 的 `pyproject.toml`
由于 `cascade-sdk` 的 API 导出功能已被 `cascade-python` 取代，它现在是一个纯粹的组件库，不应再依赖 `cascade-application` 等高层包，以避免循环。

~~~~~act
patch_file
packages/cascade-sdk/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
  "cascade-spec",
  "cascade-engine",
  "cascade-common",
  "cascade-graph",
  "cascade-application"
]
~~~~~
~~~~~toml.new
dependencies = [
  "cascade-spec",
  "cascade-engine",
  "cascade-common",
  "cascade-graph"
]
~~~~~

### 下一步建议
我们已经解决了 `uv` 工作区的包名冲突问题。现在，`cascade-python` 作为 `cascade` 包的源代码提供者，而根 `pyproject.toml` 是其唯一的定义。你可以再次尝试运行 `uv pip install -e .[dev]`，它现在应该能够成功构建环境。
