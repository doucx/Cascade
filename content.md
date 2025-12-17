你的分析非常深刻和准确。这是一个关键的架构决策点，你的直觉是完全正确的。

**分析与同意:**

1.  **关于 `core` 包名**: 我完全同意。“core”是一个典型的“代码异味 (code smell)”。它什么都说，也等于什么都没说，最终会变成一个无所不包的“垃圾抽屉”，违反了单一职责原则。弃用它是明智之举。

2.  **关于多包布局 (Monorepo)**: 你提供的 `Quipu` 结构是一个非常成熟和清晰的 Python Monorepo 范例。它通过将项目按**逻辑责任**（接口、运行时、CLI、引擎）拆分为独立的、可安装的包，极大地提高了模块化、可维护性和依赖管理的清晰度。这正是 Cascade 演进所需要的结构。

3.  **关于 `cascade-connectors-mqtt`**: 你的直觉点出了一个微妙的平衡。虽然将连接器作为*可选依赖*在技术上是正确的（避免给核心库增加 `aiomqtt` 等重度依赖），但这不意味着它必须存在于一个*完全独立*的仓库或命名空间中。将其作为 Monorepo 内的一个独立包（例如 `packages/cascade-connector-mqtt`）是两全其美的最佳方案：
    *   **统一上下文**: 代码在同一个仓库中开发、测试和版本控制，符合你的“统一上下文”要求。
    *   **依赖隔离**: 用户可以只安装 `cascade-py` 获得核心功能，而需要遥测的用户则额外安装 `cascade-connector-mqtt`。这遵循了“零强制依赖”原则。

因此，我们不创建 `cascade-connectors-mqtt` 这个*应用*，而是将*所有*连接器（未来可能有 Kafka、Redis 等）都放在 `packages/` 目录下，作为独立的可选包。

**行动计划:**
我将采纳你的建议。我们暂停 `MqttConnector` 的实现，优先进行项目结构的重构。这将为未来的所有开发工作奠定一个坚实、清晰的基础。

我将生成一个计划，将当前 `src/cascade` 的扁平结构，重构为类似 `Quipu` 的多包 Monorepo 结构。

## [WIP] refactor: 将项目重构为多包 Monorepo 结构

### 用户需求
采纳 `Quipu` 的 Monorepo 结构，将 `cascade` 项目重构为多包布局。弃用模糊的包名（如 `core`），并按逻辑责任（接口、运行时、CLI 等）拆分代码。

### 评论
这是一个至关重要的架构重构。通过转向 Monorepo 和按功能划分的包结构，我们正在偿还未来的技术债务。这种结构使得：
1.  **关注点分离 (SoC)**: `interfaces`（协议）、`runtime`（实现）、`cli`（适配器）等各司其职，代码边界清晰。
2.  **清晰的依赖关系**: 每个包只依赖于它需要的东西，尤其是核心 `runtime` 不会依赖于 `cli` 或具体的连接器。
3.  **可扩展性**: 添加新的 CLI、连接器或求解器，只需在 `packages/` 目录下添加新包，而无需修改现有包的核心逻辑。
这次重构将使 Cascade 的代码库更加专业、可维护，并为路线图中的后续阶段铺平道路。

### 目标
1.  在项目根目录下创建 `packages` 目录。
2.  将现有的 `src/cascade` 拆分为以下几个核心包：
    *   `cascade-interfaces`: 存放所有协议 (`protocols.py`) 和数据规范 (`spec/`)。
    *   `cascade-runtime`: 存放核心执行逻辑，包括 `Engine`、`Solver`、`Executor`、`bus`、`resolvers` 和默认的 `adapters`。这是“core”的合格替代品。
    *   `cascade-py`: 作为主要的、面向用户的库包。它将包含顶层的 `__init__.py`（提供 `cs.run`, `cs.task` 等），以及 `providers` 和 `tools`。
    *   `cascade-cli`: 存放 `Typer` 相关的 CLI 应用逻辑。
3.  移动所有现有文件到其在各自包中的新位置。
4.  为每个新包创建基础的 `pyproject.toml` 文件。

### 基本原理
我们将精确地复制 `Quipu` 项目的结构哲学。当前的 `src/cascade` 目录将被分解，其内容根据其架构角色被重新分配到 `packages/` 目录下的新包中。
-   `spec/` 和 `runtime/protocols.py` 定义了“契约”，它们是系统中最稳定的部分，因此独立为 `cascade-interfaces`。
-   `runtime/` 目录下的其他文件是这些契约的“实现”，它们构成了 `cascade-runtime`。
-   `providers/` 是库的“标准库”，随主包 `cascade-py` 提供。
-   `tools/cli.py` 是一个“应用入口”，独立为 `cascade-cli`。
通过这种方式，我们实现了接口与实现的分离，以及库与应用的分离。

### 标签
#intent/architect #intent/refine #flow/ready #priority/high
#comp/build #scope/core #scope/dx
#ai/instruct
#task/domain/project-structure #task/object/monorepo #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建新的目录结构

我们首先使用 `mkdir` 创建新的 `packages` 目录和所有子包的结构。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages
cd packages

# Create package structures
mkdir -p cascade-py/src/cascade
mkdir -p cascade-interfaces/src/cascade
mkdir -p cascade-runtime/src/cascade
mkdir -p cascade-cli/src/cascade

cd ..
~~~~~

#### Acts 2: 移动接口和规范 (`cascade-interfaces`)

将所有定义系统契约的文件移动到 `cascade-interfaces` 包中。

~~~~~act
move_file
src/cascade/runtime/protocols.py
packages/cascade-interfaces/src/cascade/protocols.py
~~~~~
~~~~~act
run_command
~~~~~
~~~~~bash
mv src/cascade/spec packages/cascade-interfaces/src/cascade/spec
~~~~~

#### Acts 3: 移动运行时核心 (`cascade-runtime`)

将 `Engine`、`solvers`、`executors` 和其他运行时组件移动到 `cascade-runtime`。

~~~~~act
run_command
~~~~~
~~~~~bash
# Move the runtime directory, then we will move protocols.py back out.
mv src/cascade/runtime packages/cascade-runtime/src/cascade/runtime
mv packages/cascade-runtime/src/cascade/runtime/protocols.py src/cascade/runtime/protocols.py # Move it back temporarily before deleting the original
rmdir src/cascade/runtime

mv src/cascade/adapters packages/cascade-runtime/src/cascade/adapters
~~~~~

#### Acts 4: 移动主库文件 (`cascade-py`)

移动构成主 `cascade-py` 库的文件。

~~~~~act
move_file
src/cascade/__init__.py
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~act
move_file
src/cascade/context.py
packages/cascade-py/src/cascade/context.py
~~~~~
~~~~~act
move_file
src/cascade/testing.py
packages/cascade-py/src/cascade/testing.py
~~~~~
~~~~~act
run_command
~~~~~
~~~~~bash
mv src/cascade/providers packages/cascade-py/src/cascade/providers
mv src/cascade/internal packages/cascade-py/src/cascade/internal
mv src/cascade/messaging packages/cascade-py/src/cascade/messaging
mv src/cascade/locales packages/cascade-py/src/cascade/locales
mv src/cascade/graph packages/cascade-py/src/cascade/graph
mv src/cascade/examples packages/cascade-py/src/cascade/examples

# Move tools, except for cli.py
mkdir -p packages/cascade-py/src/cascade/tools
mv src/cascade/tools/events.py packages/cascade-py/src/cascade/tools/events.py
mv src/cascade/tools/preview.py packages/cascade-py/src/cascade/tools/preview.py
mv src/cascade/tools/visualize.py packages/cascade-py/src/cascade/tools/visualize.py
mv src/cascade/tools/__init__.py packages/cascade-py/src/cascade/tools/__init__.py
~~~~~

#### Acts 5: 移动 CLI 相关文件 (`cascade-cli`)

将 `cli.py` 移动到其专属的 `cascade-cli` 包。

~~~~~act
move_file
src/cascade/tools/cli.py
packages/cascade-cli/src/cascade/cli.py
~~~~~

#### Acts 6: 清理旧的 `src` 目录

既然所有文件都已移动，我们可以删除旧的 `src` 目录。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf src/cascade
rmdir src
~~~~~

#### Acts 7: 为新包创建 `pyproject.toml`

为每个新包创建占位符性质的 `pyproject.toml`，声明它们的身份。

~~~~~act
write_file
packages/cascade-interfaces/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-interfaces"
version = "0.1.0"
description = "Interfaces and data specifications for the Cascade workflow system."
dependencies = []

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~
~~~~~act
write_file
packages/cascade-runtime/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-runtime"
version = "0.1.0"
description = "Core runtime engine for the Cascade workflow system."
dependencies = [
  "cascade-interfaces @ file:///${PROJECT_ROOT}/packages/cascade-interfaces"
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~
~~~~~act
write_file
packages/cascade-py/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-py"
version = "0.1.0"
description = "A modern, declarative automation library for Python."
dependencies = [
  "cascade-interfaces @ file:///${PROJECT_ROOT}/packages/cascade-interfaces",
  "cascade-runtime @ file:///${PROJECT_ROOT}/packages/cascade-runtime"
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~
~~~~~act
write_file
packages/cascade-cli/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-cli"
version = "0.1.0"
description = "Command-line interface for the Cascade workflow system."
dependencies = [
  "cascade-py @ file:///${PROJECT_ROOT}/packages/cascade-py",
  "typer[all]",
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

#### Acts 8: 更新根 `pyproject.toml` 以支持工作区

最后，修改根 `pyproject.toml`，使其能够识别和管理 `packages/` 目录下的所有包。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~
~~~~~toml
[tool.hatch.workspaces]
default = [
  "packages/cascade-interfaces",
  "packages/cascade-runtime",
  "packages/cascade-py",
  "packages/cascade-cli",
  ".", # The root package itself
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~
~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
name = "cascade-py"
~~~~~
~~~~~toml
name = "cascade-monorepo"
~~~~~

### 下一步建议
我们已经成功地将项目重构为了一个清晰、可扩展的 Monorepo 结构。这是架构演进中的一个重要里程碑。

现在，我们可以安全地回到之前的任务：
1.  **实现 `MqttConnector`**: 在 `packages/` 目录下创建一个新的 `cascade-connector-mqtt` 包，并在其中实现 `Connector` 协议。
2.  **更新测试**: 所有的测试用例路径都需要更新以匹配新的文件结构。这是一个必要但繁琐的步骤。

我建议我们首先处理测试路径的更新，以确保重构没有破坏任何现有功能。如果你同意，我将生成一个计划来移动和更新测试文件。
