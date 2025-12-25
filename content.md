好的，我们现在开始执行 ADR-013 路线图的第一阶段。

这是一个纯粹的奠基性工作，我们将创建 `cascade-application` 包，定义 `CascadeApp` 的初始接口，并将其正确地集成到项目的 Monorepo 构建系统中，确保命名空间和类型提示的正确性。

## [WIP] feat(arch): 实现 Application 层重构的第一阶段

### 用户需求
执行 ADR-013 路线图的第一阶段：创建 `cascade-application` 包，定义 `CascadeApp` 接口，并更新根 `pyproject.toml` 以集成新包。

### 评论
这是 Application 层重构的第一个具体步骤。正确设置包结构、命名空间和构建配置是保证 Monorepo 健康和提供良好开发者体验（DX）的关键。此阶段完成后，我们将拥有一个清晰的目标模块来承接后续阶段的逻辑迁移。

### 目标
1.  创建 `packages/cascade-application` 的目录结构。
2.  定义一个空的 `CascadeApp` 类接口，作为后续实现的契约。
3.  创建符合 PEP 561 和显式命名空间规范的 `__init__.py` 和 `py.typed` 文件。
4.  为新包创建 `pyproject.toml` 文件。
5.  修改根 `pyproject.toml`，将新包加入工作区。

### 基本原理
通过 `run_command` 创建目录和空文件可以快速完成结构搭建。使用 `write_file` 写入新文件的完整内容，可以确保原子性和准确性。对于根 `pyproject.toml` 的修改，使用 `patch_file` 可以在不重写整个文件的情况下精确地添加所需条目，降低了操作风险。

### 标签
#intent/build #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/architecture #task/object/application-layer #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建包目录结构和基础文件

首先，我们创建 `cascade-application` 包所需的完整目录结构和空的 Python 模块文件。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-application/src/cascade/app
touch packages/cascade-application/src/cascade/__init__.py
touch packages/cascade-application/src/cascade/app/__init__.py
touch packages/cascade-application/src/cascade/py.typed
touch packages/cascade-application/pyproject.toml
~~~~~

#### Acts 2: 填充新包的配置文件和接口

现在，我们为新创建的文件写入内容，包括命名空间声明、`CascadeApp` 的初始接口定义以及新包的 `pyproject.toml`。

~~~~~act
write_file
packages/cascade-application/src/cascade/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-engine) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python
from typing import Any, Dict, List, Tuple, Union

# Use a string forward reference to avoid circular dependency at this stage
if "LazyResult" not in globals():
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from cascade.spec.lazy_types import LazyResult


class CascadeApp:
    """
    The central manager for a workflow's lifecycle, encapsulating all
    infrastructure, configuration, and top-level operations.
    """

    def __init__(self, target: Union["LazyResult", List[Any], Tuple[Any, ...]]):
        """
        Initializes the application context for a given workflow target.

        This constructor is responsible for:
        - Setting up the internal Engine, MessageBus, and other infrastructure.
        - Applying pre-processing to the target, such as auto-gathering lists.
        """
        pass

    def run(self, params: Dict[str, Any] = None) -> Any:
        """Executes the workflow and returns the final result."""
        pass

    def visualize(self) -> str:
        """Generates and returns a Graphviz DOT string of the workflow."""
        pass

    def dry_run(self) -> None:
        """Builds and prints the execution plan without running any tasks."""
        pass
~~~~~

~~~~~act
write_file
packages/cascade-application/src/cascade/py.typed
~~~~~
~~~~~
# This file is intentionally empty.
# It signals to type checkers that this package supports type hints (PEP 561).
~~~~~

~~~~~act
write_file
packages/cascade-application/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-application"
version = "0.1.0"
description = "The application layer for Cascade, providing a unified API entrypoint."
requires-python = ">=3.8"
dependencies = [
  "cascade-spec",
  "cascade-engine",
  "cascade-graph",
  "cascade-sdk"
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-graph = { workspace = true }
cascade-sdk = { workspace = true }
~~~~~

#### Acts 3: 将新包集成到 Monorepo 工作区

最后，我们修改根目录的 `pyproject.toml`，将 `cascade-application` 正式注册为工作区的一个成员，并使其在开发环境中可用。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-sdk = { workspace = true }
cascade-graph = { workspace = true }
cascade-library = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
~~~~~
~~~~~toml
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
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
  # Local workspace packages needed for testing
  "cascade-provider-ipfs",
  "cascade-cli-controller",
  "cascade-cli-observer",
  "cascade-connector-mqtt",
  "cascade-connector-local",
]
~~~~~
~~~~~toml
  # Local workspace packages needed for testing
  "cascade-application",
  "cascade-provider-ipfs",
  "cascade-cli-controller",
  "cascade-cli-observer",
  "cascade-connector-mqtt",
  "cascade-connector-local",
]
~~~~~

### 下一步建议
我们已经成功完成了路线图的第一阶段。`cascade-application` 包的骨架已经搭建完毕并集成到了项目中。

接下来的**第二阶段**将是核心逻辑的迁移：我们会将 `cs.run()` 函数中关于 `Engine` 实例化、消息总线配置和渲染器注入的逻辑，逐步迁移到 `CascadeApp` 类的 `__init__` 方法和 `run` 方法中。如果你同意，我将为你生成执行此阶段的计划。
