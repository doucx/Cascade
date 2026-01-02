好的，我们开始执行 Act 0.5.1 的第一部分：初始化 `cascade-std` 包。

我将创建一个计划，该计划会建立 `cascade-std` 的目录结构，配置其 `pyproject.toml` 以声明对 `cascade-spec` 的依赖，并建立符合我们 Monorepo 规范的 `pkgutil` 命名空间。

## [WIP] feat: 初始化 cascade-std 包结构

### 用户需求

根据 `Act 0.5` 路线图，执行任务 T1：项目初始化。这包括创建 `cascade-std` 包，配置其依赖，并设置命名空间。

### 评论

这是建立 Cascade “标准物理库”的第一步，也是至关重要的一步。一个干净、合规的包结构是后续功能迁移和开发的基础，能确保我们的 Monorepo 工具链和类型检查器正确识别新包，从而提供良好的开发者体验。

### 目标

1.  创建 `packages/cascade-std` 的完整目录结构。
2.  为 `cascade-std` 创建一个 `pyproject.toml` 文件，声明其元数据和对 `cascade-spec` 的依赖。
3.  创建符合 PEP 561 规范的 `py.typed` 文件和符合 `pkgutil` 规范的命名空间 `__init__.py` 文件。
4.  将新包注册到根 `pyproject.toml` 的 workspace 中，使其成为 Monorepo 的一部分。

### 基本原理

我们将使用一系列原子化的文件系统操作来完成初始化：
1.  `run_command` 与 `mkdir -p` 结合可以一次性、幂等地创建所有必需的目录。
2.  `write_file` 用于创建新文件，包括 `pyproject.toml` 和 `__init__.py`。新包的 `pyproject.toml` 会被配置为 workspace 成员，并使用 `uv.sources` 链接到本地的 `cascade-spec`。
3.  `patch_file` 用于向根 `pyproject.toml` 中添加新成员，这比重写整个文件更安全、更精确。

### 标签

#intent/build #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/architecture #task/object/cascade-std #task/action/initialization #task/state/begin

---

### Script

#### Acts 1: 创建 `cascade-std` 目录结构

首先，我们创建新包所需的所有目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-std/src/cascade/std
~~~~~

#### Acts 2: 创建 `cascade-std` 的包配置文件

接下来，创建 `pyproject.toml` 文件，定义包的元数据和依赖项。

~~~~~act
write_file
packages/cascade-std/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-std"
version = "0.1.0"
description = "Standard library of physical primitives (ICs) for the Cascade VM."
requires-python = ">=3.8"
dependencies = [
  "cascade-spec",
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-spec = { workspace = true }
~~~~~

#### Acts 3: 建立命名空间和类型支持

现在，我们创建 `__init__.py` 文件以建立 `pkgutil` 命名空间，并添加 `py.typed` 文件以确保类型提示被正确识别。

~~~~~act
write_file
packages/cascade-std/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-std/src/cascade/std/__init__.py
~~~~~
~~~~~python
# Standard library of physical primitives (ICs) for the Cascade VM.
~~~~~

~~~~~act
write_file
packages/cascade-std/src/cascade/py.typed
~~~~~
~~~~~
~~~~~

#### Acts 4: 将新包注册到 Monorepo workspace

最后，我们将 `cascade-std` 添加到根 `pyproject.toml` 的 `uv.sources` 和 `hatch.workspaces` 中，以便 Monorepo 工具可以识别它。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
cascade-compiler = { workspace = true }
cascade = { workspace = true }
~~~~~
~~~~~toml.new
cascade-compiler = { workspace = true }
cascade-std = { workspace = true }
cascade = { workspace = true }
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
    "packages/cascade-vm",
    "packages/cascade-compiler",
]
~~~~~
~~~~~toml.new
    "packages/cascade-vm",
    "packages/cascade-compiler",
    "packages/cascade-std",
]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
executionEnvironments = [
  { root = "packages", extraPaths = [ "packages/cascade-application/src", "packages/cascade-cli-controller/src", "packages/cascade-cli-observer/src", "packages/cascade-common/src", "packages/cascade-connector-local/src", "packages/cascade-connector-mqtt/src", "packages/cascade-engine/src", "packages/cascade-graph/src", "packages/cascade-library/src", "packages/cascade-provider-ipfs/src", "packages/cascade-sdk/src", "packages/cascade-spec/src", "packages/cascade-vm/src", "packages/cascade-compiler/src" ] }
]
~~~~~
~~~~~toml.new
executionEnvironments = [
  { root = "packages", extraPaths = [ "packages/cascade-application/src", "packages/cascade-cli-controller/src", "packages/cascade-cli-observer/src", "packages/cascade-common/src", "packages/cascade-connector-local/src", "packages/cascade-connector-mqtt/src", "packages/cascade-engine/src", "packages/cascade-graph/src", "packages/cascade-library/src", "packages/cascade-provider-ipfs/src", "packages/cascade-sdk/src", "packages/cascade-spec/src", "packages/cascade-vm/src", "packages/cascade-compiler/src", "packages/cascade-std/src" ] }
]
~~~~~

### 下一步建议

我们已经成功地创建了 `cascade-std` 包的骨架。

根据路线图，下一步是**任务 T2: 指令集迁出 (The Great Migration)**。这涉及到将 `cascade-vm` 中的 `bleacher.py`, `stainer.py` 和 `observer.py` 移动到新的 `cascade-std` 包中，并清理 `cascade-vm`。

如果你准备好了，请指示我开始 `cascade-vm` 的文件迁移工作。
