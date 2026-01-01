好的，遵照您的指示和项目路线图，我将为 `cascade-compiler` 和 `cascade-vm` 两个新包创建基础结构，并更新 Monorepo 的相关配置以集成它们。

这是一个奠基性的步骤，为后续实现“全对称计算物理场”的核心组件做好准备。

## [WIP] feat: 建立 cascade-compiler 和 cascade-vm 的包结构

### 用户需求

根据 Cascade 3.0 的重构路线图，需要创建 `cascade-compiler` 和 `cascade-vm` 两个新包的基础目录结构和 `pyproject.toml` 配置文件。同时，需要更新根目录的 `pyproject.toml` 以将这两个新包完全集成到 `uv`、`hatch` 和 `pyright` 的工作区中。

### 评论

这是实施 Cascade 3.0 路线图的关键第一步。通过预先建立清晰的包结构并配置好开发环境，我们可以确保后续的开发工作（如实现 Reactor 和 Expander）能够在一个类型安全、工具链完备的环境中顺利进行。这完全符合“焦土政策”后从零开始构建新晶体结构的精神。

### 目标

1.  为 `cascade-vm` 包创建完整的目录结构，包括 `src/cascade/vm`、命名空间 `__init__.py` 以及 `py.typed` 文件。
2.  为 `cascade-vm` 创建一个 `pyproject.toml`，声明其名称、依赖（`cascade-spec`, `cascade-common`）和构建配置。
3.  为 `cascade-compiler` 包创建与 `cascade-vm` 类似的完整目录结构。
4.  为 `cascade-compiler` 创建一个 `pyproject.toml`，声明其名称、依赖（`cascade-spec`, `cascade-common`, `cascade-graph`）和构建配置。
5.  更新根 `pyproject.toml`，将新包添加到项目依赖、`uv` 工作区、`hatch` 工作区、`dev` 依赖以及 `pyright` 的执行环境中。

### 基本原理

遵循 Monorepo 的最佳实践，任何新组件的引入都必须伴随着其在整个工作区配置中的“注册”。这确保了开发者体验（DX）的一致性，特别是 `pyright` 的类型检查和路径解析能力，从一开始就覆盖新代码。我们将基于现有包（如 `cascade-engine`）的模板来创建新包的配置，以保证规范统一。

### 标签

#intent/build #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/build #task/object/package-structure #task/action/setup #task/state/begin

---

### Script

#### Acts 1: 创建 `cascade-vm` 包的目录结构

首先，我们为物理引擎 `cascade-vm` 建立必要的目录和文件。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-vm/src/cascade/vm
touch packages/cascade-vm/src/cascade/vm/__init__.py
~~~~~

#### Acts 2: 为 `cascade-vm` 创建配置文件

接下来，我们创建 `cascade-vm` 的核心配置文件和命名空间声明。

~~~~~act
write_file
packages/cascade-vm/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-vm/src/cascade/py.typed
~~~~~
~~~~~
# Marker file for PEP 561
~~~~~

~~~~~act
write_file
packages/cascade-vm/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-vm"
version = "0.1.0"
description = "The physics engine for Cascade 3.0, implementing the token physics model."
requires-python = ">=3.8"
dependencies = [
  "cascade-spec",
  "cascade-common",
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-common = { workspace = true }
~~~~~

#### Acts 3: 创建 `cascade-compiler` 包的目录结构

现在，我们为编译器 `cascade-compiler` 建立目录结构。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-compiler/src/cascade/compiler
touch packages/cascade-compiler/src/cascade/compiler/__init__.py
~~~~~

#### Acts 4: 为 `cascade-compiler` 创建配置文件

为 `cascade-compiler` 创建配置文件，它将依赖 `cascade-graph` 来构建物理图。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-compiler/src/cascade/py.typed
~~~~~
~~~~~
# Marker file for PEP 561
~~~~~

~~~~~act
write_file
packages/cascade-compiler/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-compiler"
version = "0.1.0"
description = "The graph compiler for Cascade 3.0, expanding logic into physical topology."
requires-python = ">=3.8"
dependencies = [
  "cascade-spec",
  "cascade-common",
  "cascade-graph",
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-common = { workspace = true }
cascade-graph = { workspace = true }
~~~~~

#### Acts 5: 更新根 `pyproject.toml` 以集成新包

最后，我们将新包无缝集成到整个 Monorepo 的工作区和依赖项中。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
license = "Apache-2.0"
dependencies = [
    "cascade-spec",
    "cascade-engine",
    "cascade-sdk",
    "cascade-graph",
    "cascade-library",
]

[tool.uv.workspace]
~~~~~
~~~~~toml
license = "Apache-2.0"
dependencies = [
    "cascade-spec",
    "cascade-engine",
    "cascade-sdk",
    "cascade-graph",
    "cascade-library",
    "cascade-vm",
    "cascade-compiler",
]

[tool.uv.workspace]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
cascade-connector-local = { workspace = true }
cascade-common = { workspace = true }
cascade = { workspace = true }

[tool.hatch.workspaces]
packages = [
~~~~~
~~~~~toml
cascade-connector-local = { workspace = true }
cascade-common = { workspace = true }
cascade-vm = { workspace = true }
cascade-compiler = { workspace = true }
cascade = { workspace = true }

[tool.hatch.workspaces]
packages = [
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-engine",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
    "packages/cascade-graph",
    "packages/cascade-library",
    "packages/cascade-connector-local",
]

[tool.hatch.build.targets.wheel]
~~~~~
~~~~~toml
[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-engine",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
    "packages/cascade-graph",
    "packages/cascade-library",
    "packages/cascade-connector-local",
    "packages/cascade-vm",
    "packages/cascade-compiler",
]

[tool.hatch.build.targets.wheel]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
  "cascade-cli-observer",
  "cascade-connector-mqtt",
  "cascade-connector-local",
  # "cascade", # The python sdk
  "ruff",
]
~~~~~
~~~~~toml
  "cascade-cli-observer",
  "cascade-connector-mqtt",
  "cascade-connector-local",
  "cascade-vm",
  "cascade-compiler",
  # "cascade", # The python sdk
  "ruff",
]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
executionEnvironments = [
  { root = "packages", extraPaths = [ "packages/cascade-application/src", "packages/cascade-cli-controller/src", "packages/cascade-cli-observer/src", "packages/cascade-common/src", "packages/cascade-connector-local/src", "packages/cascade-connector-mqtt/src", "packages/cascade-engine/src", "packages/cascade-graph/src", "packages/cascade-library/src", "packages/cascade-provider-ipfs/src", "packages/cascade-sdk/src", "packages/cascade-spec/src" ] }
]
~~~~~
~~~~~toml
executionEnvironments = [
  { root = "packages", extraPaths = [ "packages/cascade-application/src", "packages/cascade-cli-controller/src", "packages/cascade-cli-observer/src", "packages/cascade-common/src", "packages/cascade-connector-local/src", "packages/cascade-connector-mqtt/src", "packages/cascade-engine/src", "packages/cascade-graph/src", "packages/cascade-library/src", "packages/cascade-provider-ipfs/src", "packages/cascade-sdk/src", "packages/cascade-spec/src", "packages/cascade-vm/src", "packages/cascade-compiler/src" ] }
]
~~~~~

### 下一步建议

我们已经成功地为 `cascade-vm` 和 `cascade-compiler` 两个新包奠定了基础。根据路线图，下一步是 **阶段 0：创世纪 (Genesis - Spec Definition)** 的核心任务。

我建议我们开始实施 **任务 0.1：定义令牌与物理节点**。这涉及到在 `cascade-spec` 包中创建 `physics.py` 文件，并实现 `Token`、`PhysicsDataNode` 和 `PhysicsFuncNode` 的 dataclass 定义。

如果您同意，我将为您生成相应的计划。
