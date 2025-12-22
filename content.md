好的，我们立即开始第二阶段的架构重构。

此计划将遵循您的指示，将所有与“图”相关的逻辑（构建、编译、哈希、序列化）从 `cascade-engine` 中剥离出来，并封装到一个全新的、职责单一的 `cascade-graph` 包中。

## [WIP] refactor(arch): Isolate graph logic into a dedicated cascade-graph package

### 用户需求
根据架构建议书，将图的编译、构建、哈希和序列化逻辑从 `cascade-engine` 包中移出，创建一个新的 `cascade-graph` 包。

### 评论
这是语义化重构的下一步，也是非常关键的一步。将“逻辑表示”（Graph）与“物理执行”（Engine）分离，是实现高度模块化系统设计的核心原则。此举将使 `cascade-engine` 的职责更加纯粹，只关注于“如何运行指令”，而将“如何生成指令”的逻辑委托给 `cascade-graph`。

### 目标
1.  创建 `packages/cascade-graph` 的目录结构及其 `pyproject.toml` 文件。
2.  将 `packages/cascade-engine/src/cascade/graph/` 目录整体移动到 `packages/cascade-graph/src/cascade/` 中。
3.  更新根目录的 `pyproject.toml`，将 `cascade-graph` 添加为新的工作区成员。
4.  更新 `cascade-engine` 和 `cascade-sdk` 的 `pyproject.toml`，添加对新 `cascade-graph` 包的依赖。
5.  重新安装工作区依赖并运行测试，以验证重构的正确性。

### 基本原理
通过创建 `cascade-graph` 包，我们为系统的“编译器”和“静态分析器”提供了一个明确的归属。`cascade-engine` 将从一个既是编译器又是执行器的“混合体”，演变为一个更纯粹的“运行时”。这种清晰的职责划分，极大地提高了代码的可维护性和可理解性。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #scope/core #ai/instruct #task/domain/architecture #task/object/package-structure #task/action/refactor #task/state/continue #task/status/active

---

### Script

#### Acts 1: 创建 `cascade-graph` 包结构和配置文件
我们首先创建新包的目录和基础 `pyproject.toml`。它将依赖于 `cascade-spec`，因为图模型定义在 `spec` 包中。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-graph/src/cascade
~~~~~

~~~~~act
write_file
packages/cascade-graph/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-graph"
version = "0.1.0"
description = "Graph building, compilation, and serialization logic for the Cascade ecosystem."
requires-python = ">=3.8"
dependencies = [
  "cascade-spec"
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-spec = { workspace = true }
~~~~~

#### Acts 2: 移动图逻辑模块
现在，我们将整个 `graph` 目录从 `engine` 移动到新创建的 `graph` 包中。

~~~~~act
move_file
packages/cascade-engine/src/cascade/graph
packages/cascade-graph/src/cascade/graph
~~~~~

#### Acts 3: 更新工作区配置
我们需要让 monorepo 工具（uv, hatch）知道这个新包的存在。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~
[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
~~~~~
~~~~~
[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
cascade-graph = { workspace = true }
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~
[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-engine",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
]
~~~~~
~~~~~
[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-engine",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
    "packages/cascade-graph",
]
~~~~~

#### Acts 4: 更新依赖 `cascade-graph` 的包
`cascade-engine` 和 `cascade-sdk` 现在需要显式地依赖于 `cascade-graph`。

~~~~~act
patch_file
packages/cascade-engine/pyproject.toml
~~~~~
~~~~~
dependencies = [
  "cascade-spec",
  "cascade-common"
]
~~~~~
~~~~~
dependencies = [
  "cascade-spec",
  "cascade-common",
  "cascade-graph"
]
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/pyproject.toml
~~~~~
~~~~~
dependencies = [
  "cascade-spec",
  "cascade-engine",
  "cascade-common"
]
~~~~~
~~~~~
dependencies = [
  "cascade-spec",
  "cascade-engine",
  "cascade-common",
  "cascade-graph"
]
~~~~~

### 下一步建议
如果本次重构成功，我们将只剩下最后一个核心架构调整：
**创建 `cascade-library` 包，并将所有内置的 provider（如 `http`, `sql`, `io` 等）从 `cascade-sdk` 中迁移过去。**
这将使 `cascade-sdk` 成为一个纯粹的、轻量级的用户入口，而将具体的“功能实现”放入标准库中。
