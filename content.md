好的，我们开始执行重构路线图的第一阶段：为新的 `cascade-execution-graph` 包搭建脚手架。

这将建立新包的物理结构，并将其集成到我们的 Monorepo 工作区中，为第二阶段的代码迁移做好准备。

## [WIP] chore: Scaffold cascade-execution-graph package

### 用户需求

执行“Runtime 解耦与执行器分离”路线图的第一阶段（Phase 1），为新的 `cascade-execution-graph` 包创建完整的脚手架，并更新 Monorepo 的工作区配置以包含这个新包。

### 评论

这是解耦 `cascade-runtime` 核心逻辑的关键第一步。通过预先建立一个结构完整、配置正确的包，我们为后续的代码迁移提供了一个清晰的目标，确保了整个重构过程的平稳进行。将新包立即集成到工作区中，也能保证开发环境（如类型检查器和依赖管理器）的一致性。

### 目标

1.  创建 `packages/cascade-execution-graph` 的目录结构。
2.  为其创建一个 `pyproject.toml` 文件，定义其元数据、构建配置和依赖项（包括 `python-constraint`）。
3.  建立正确的 `pkgutil` 风格的命名空间包。
4.  添加 `py.typed` 文件以确保 PEP 561 合规性。
5.  更新根 `pyproject.toml`，将新包添加到 `hatch` 和 `uv` 的工作区配置中。

### 基本原理

我们严格遵循“重构路线图”中定义的“脚手架搭建”阶段。首先创建物理结构和配置文件，可以使后续的代码迁移任务（Phase 2）简化为纯粹的文件移动和导入路径更新，从而降低了重构的复杂性。这种分步方法确保了每一步都是一个原子化的、可验证的操作。

### 标签

#intent/tooling #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/runtime #task/object/decoupling #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建包的目录结构

首先，我们为 `cascade-execution-graph` 包创建所有必需的目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-execution-graph/src/cascade/execution/graph
~~~~~

#### Acts 2: 创建 `pyproject.toml`

接下来，创建新包的 `pyproject.toml` 文件，定义其项目元数据、构建系统、依赖项和工作区引用。

~~~~~act
write_file
packages/cascade-execution-graph/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-execution-graph"
version = "0.1.0"
description = "The legacy graph-based execution strategy for Cascade, separated from the core runtime."
requires-python = ">=3.8"
dependencies = [
  "cascade-spec",
  "cascade-common",
  "cascade-runtime",
  "cascade-compiler",
  "python-constraint"
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-common = { workspace = true }
cascade-runtime = { workspace = true }
cascade-compiler = { workspace = true }
~~~~~

#### Acts 3: 建立命名空间包

创建 `__init__.py` 文件，使用 `pkgutil` 模式将 `cascade.execution.graph` 建立为一个显式的命名空间包，以确保与 Monorepo 中的其他包兼容。

~~~~~act
write_file
packages/cascade-execution-graph/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Shim to expose the SDK API if available in the environment
try:
    from cascade.sdk import *  # noqa: F403
    from cascade.sdk import __all__, __getattr__  # noqa: F401
except ImportError:
    pass
~~~~~

~~~~~act
write_file
packages/cascade-execution-graph/src/cascade/execution/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-execution-graph/src/cascade/execution/graph/__init__.py
~~~~~
~~~~~python
# This file can be empty, its presence defines the module.
~~~~~

#### Acts 4: 添加 PEP 561 类型支持文件

创建一个空的 `py.typed` 文件，向类型检查器声明此包提供类型提示。

~~~~~act
write_file
packages/cascade-execution-graph/src/cascade/py.typed
~~~~~
~~~~~
~~~~~

#### Acts 5: 更新根 `pyproject.toml` 以集成新包

最后，我们将新包添加到根 `pyproject.toml` 的工作区配置中，以便 `uv` 和 `hatch` 能够识别它。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-runtime = { workspace = true }
cascade-sdk = { workspace = true }
cascade-reflection = { workspace = true }
cascade-library = { workspace = true }
cascade-application = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
cascade-common = { workspace = true }
cascade-test-utils = { workspace = true }
cascade-vm = { workspace = true }
cascade-compiler = { workspace = true }
cascade-std = { workspace = true }
cascade = { workspace = true }
cascade-vm-rs = { workspace = true }

[tool.hatch.workspaces]
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-runtime = { workspace = true }
cascade-sdk = { workspace = true }
cascade-reflection = { workspace = true }
cascade-library = { workspace = true }
cascade-application = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
cascade-common = { workspace = true }
cascade-test-utils = { workspace = true }
cascade-vm = { workspace = true }
cascade-compiler = { workspace = true }
cascade-execution-graph = { workspace = true }
cascade-std = { workspace = true }
cascade = { workspace = true }
cascade-vm-rs = { workspace = true }

[tool.hatch.workspaces]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
    "packages/cascade-compiler",
    "packages/cascade-std",
    "packages/cascade-vm-rs",
    "packages/cascade-reflection",
    "packages/cascade-test-utils",
]

[tool.hatch.build.targets.wheel]
~~~~~
~~~~~toml
    "packages/cascade-compiler",
    "packages/cascade-std",
    "packages/cascade-vm-rs",
    "packages/cascade-reflection",
    "packages/cascade-test-utils",
    "packages/cascade-execution-graph",
]

[tool.hatch.build.targets.wheel]
~~~~~

### 下一步建议

我们已经成功完成了 Phase 1。

下一步是 **Phase 2: 代码大迁徙 (The Great Migration)**。我们将把 `cascade-runtime` 中与遗留图执行器相关的代码（模型、逻辑、求解器和策略）物理移动到新建的 `cascade-execution-graph` 包中，并同步更新它们的导入路径。

如果你准备好了，我将开始生成执行代码迁移的计划。
