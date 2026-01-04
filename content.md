好的，执行方案二。

这是一个经典的架构重构，通过提取关注点（代码反射和哈希）到一个独立的、轻量的包中，我们可以极大地改善系统的模块化程度和可维护性。

我将生成一个计划，分步执行以下操作：
1.  **创建 `packages/cascade-reflection`**：搭建新包的骨架，包括 `pyproject.toml` 和目录结构。
2.  **迁移核心逻辑**：将 `ReflectionAnalyzer` 和 `HashingService` 的实现从 `cascade-graph` 移动到新包中。
3.  **更新依赖**：修改根 `pyproject.toml` 以及 `cascade-graph` 和 `cascade-compiler` 的 `pyproject.toml`，以正确声明新的依赖关系。
4.  **重构代码**：更新 `cascade-graph` 和 `cascade-compiler` 中所有相关的 `import` 语句，使其指向新的 `cascade.reflection` 包。
5.  **清理冗余**：删除旧位置的重复代码文件。

这将彻底解决 DRY 违规问题，并为未来的静态分析工具奠定坚实的基础。

## [WIP] refactor: 创建 cascade-reflection 包以集中化代码分析

### 用户需求
解决 `analyze` 和 `_compute_structure_hash` 函数在 `cascade-compiler` 和 `cascade-graph` 包中的重复实现问题。通过创建一个新的、专门的 `cascade-reflection` 包来统一这些功能，并重构现有代码以使用这个新包。

### 评论
这是一个优秀的架构决策。将代码反射、静态分析和哈希指纹生成这些底层、纯粹的功能提取到一个独立的包中，可以：
1.  **实现关注点分离**：让 `cascade-graph` 专注于图的拓扑结构，`cascade-compiler` 专注于将逻辑图转换为物理图，而 `cascade-reflection` 则专注于理解 Python 代码本身。
2.  **打破不必要的依赖**：其他需要代码分析能力的工具（如未来的 CLI `inspect` 命令）将可以只依赖这个轻量的 `cascade-reflection` 包，而无需引入整个图构建或编译引擎。
3.  **建立单一事实来源**：为全系统的哈希和指纹计算提供一个权威的、统一的实现，确保一致性。

### 目标
1.  创建一个名为 `cascade-reflection` 的新 Python 包。
2.  将 `ReflectionAnalyzer` 和 `HashingService` 的实现统一并迁移到 `cascade-reflection` 中。
3.  重构 `cascade-graph` 和 `cascade-compiler` 包，使其依赖并使用新的 `cascade-reflection` 包。
4.  彻底消除代码库中的重复实现，解决 DRY 违规问题。

### 基本原理
我们将遵循标准的 Python 包创建和依赖管理流程。首先，我们会像创建其他 `cascade-*` 包一样，创建 `cascade-reflection` 的目录结构和 `pyproject.toml` 文件。该包将只依赖 `cascade-spec`，因为它需要 `TaskDef` 等 IR 模型。

然后，我们将 `cascade-graph` 中的 `analysis` 和 `hashing` 逻辑作为“事实来源”，移动到新包中，并相应地调整其内部导入。

最后，修改 `cascade-graph` 和 `cascade-compiler` 的 `pyproject.toml` 文件以添加对 `cascade-reflection` 的依赖，并使用 `patch_file` 命令修正所有旧的 `import` 语句，完成整个重构过程。

### 标签
#intent/refine #flow/ready #priority/high
#comp/graph #comp/compiler #scope/dx
#ai/brainstorm
#task/domain/architecture #task/object/code-reflection #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 脚手架：创建 `cascade-reflection` 包

首先，我们创建新包的目录结构和配置文件。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-reflection/src/cascade/reflection
touch packages/cascade-reflection/src/cascade/__init__.py
touch packages/cascade-reflection/src/cascade/reflection/__init__.py
touch packages/cascade-reflection/src/cascade/py.typed
~~~~~

~~~~~act
write_file
packages/cascade-reflection/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-reflection"
version = "0.1.0"
description = "Core reflection, static analysis, and hashing utilities for the Cascade ecosystem."
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

#### Acts 2: 迁移：将核心逻辑移动到新包

我们将 `cascade-graph` 中现有的实现作为“源”，移动到 `cascade-reflection`。

~~~~~act
move_file
packages/cascade-graph/src/cascade/graph/analysis/protocols.py
packages/cascade-reflection/src/cascade/reflection/protocols.py
~~~~~

~~~~~act
move_file
packages/cascade-graph/src/cascade/graph/analysis/reflection.py
packages/cascade-reflection/src/cascade/reflection/analyzer.py
~~~~~

~~~~~act
move_file
packages/cascade-graph/src/cascade/graph/hashing.py
packages/cascade-reflection/src/cascade/reflection/hashing.py
~~~~~

#### Acts 3: 初始化：配置新包的 `__init__.py` 并修复内部导入

现在，我们导出新包的公共 API，并修正刚才移动的文件中的相对导入。

~~~~~act
write_file
packages/cascade-reflection/src/cascade/reflection/__init__.py
~~~~~
~~~~~python
from .protocols import TaskAnalyzer
from .analyzer import ReflectionAnalyzer
from .hashing import HashingService, BlueprintHasher

__all__ = ["TaskAnalyzer", "ReflectionAnalyzer", "HashingService", "BlueprintHasher"]
~~~~~

~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/analyzer.py
~~~~~
~~~~~python.old
from cascade.graph.analysis.protocols import TaskAnalyzer
~~~~~
~~~~~python.new
from .protocols import TaskAnalyzer
~~~~~

#### Acts 4: 配置：更新 Monorepo 配置文件

将新包添加到工作区和开发依赖中。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.workspace]
members = ["packages/*"]
~~~~~
~~~~~toml.new
[tool.uv.workspace]
members = [
    "packages/*",
]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
~~~~~
~~~~~toml.new
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
cascade-reflection = { workspace = true }
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
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
    "packages/cascade-std",
    "packages/cascade-vm-rs",
]
~~~~~
~~~~~toml.new
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
    "packages/cascade-std",
    "packages/cascade-vm-rs",
    "packages/cascade-reflection",
]
~~~~~

#### Acts 5: 重构 `cascade-graph`

更新 `cascade-graph` 的依赖和代码，使其使用 `cascade-reflection`。

~~~~~act
patch_file
packages/cascade-graph/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
  "cascade-spec",
  "cascade-common"
]
~~~~~
~~~~~toml.new
dependencies = [
  "cascade-spec",
  "cascade-common",
  "cascade-reflection",
]
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
from .registry import NodeRegistry
from .hashing import HashingService
from .analysis.reflection import ReflectionAnalyzer
~~~~~
~~~~~python.new
from .registry import NodeRegistry
from cascade.reflection import HashingService, ReflectionAnalyzer
~~~~~

#### Acts 6: 重构 `cascade-compiler`

同样更新 `cascade-compiler` 的依赖和代码。

~~~~~act
patch_file
packages/cascade-compiler/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
  "cascade-spec",
  "cascade-common",
  "cascade-graph",
]
~~~~~
~~~~~toml.new
dependencies = [
  "cascade-spec",
  "cascade-common",
  "cascade-graph",
  "cascade-reflection",
]
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
from cascade.spec.ir.models import GraphIR, NodeIR
from cascade.compiler.utils.reflection import ReflectionAnalyzer
from cascade.compiler.utils.hashing import HashingService
~~~~~
~~~~~python.new
from cascade.spec.ir.models import GraphIR, NodeIR
from cascade.reflection import ReflectionAnalyzer, HashingService
~~~~~

#### Acts 7: 清理：删除旧的重复文件和目录

最后，删除所有冗余的代码。

~~~~~act
run_command
~~~~~
~~~~~
rm -rf packages/cascade-graph/src/cascade/graph/analysis
rm -rf packages/cascade-compiler/src/cascade/compiler/utils/reflection.py
rm -rf packages/cascade-compiler/src/cascade/compiler/utils/hashing.py
~~~~~

### 下一步建议
我们已经完成了核心的重构工作。下一步至关重要：
1.  **运行测试**：执行完整的测试套件 (`pytest`)，以确保我们的重构没有破坏任何现有功能。
2.  **创建提交**：如果所有测试都通过，我将为你生成一个 `[COMMIT]` 计划，将这些架构改进固化到版本历史中。
