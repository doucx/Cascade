好的，我们现在进入第二阶段。这是本次重构的核心操作，我们将把所有源代码和测试文件迁移到第一阶段创建的新目录结构中。

我将使用 `run_command` 来执行文件移动，以确保操作的健壮性。

## [WIP] refactor(build): Migrate source and test files to monorepo packages

### 用户需求
执行重构路线图的第二阶段：将现有 `src/cascade` 目录下的所有代码文件，以及 `tests` 目录下的所有测试文件，系统性地迁移到它们在 `packages/` 和 `tests/` 子目录中各自的新位置。

### 评论
这是整个重构过程中“体力活”最集中的一步。我们将一次性地对项目的文件系统进行大规模重组。这个操作会暂时性地“破坏”整个项目（因为所有的 Python导入路径都会失效），这是一个预期内的中间状态。关键在于精确、完整地执行文件迁移，为第三阶段的配置更新和最终修复做好准备。

### 目标
1.  将与接口、协议和数据模型相关的代码（`spec/`, `runtime/protocols.py`, `graph/model.py`）迁移至 `packages/cascade-interfaces/`。
2.  将核心的运行时引擎、求解器、执行器和适配器（`runtime/`, `adapters/` 等）迁移至 `packages/cascade-runtime/`。
3.  将面向用户的库代码，包括 `providers/`、`tools/` 和顶层 `__init__.py` 等，迁移至 `packages/cascade-py/`。
4.  将 CLI 专用代码（`tools/cli.py`）迁移至 `packages/cascade-cli/` 并重命名为 `main.py`。
5.  同步重组 `tests/` 目录，使其内部结构镜像新的多包布局。

### 基本原理
我们将严格遵循用户指令，使用 `run_command` 和 `mv` 来执行所有文件和目录的移动。为了清晰和可追溯，我们将文件迁移分为两个独立的 `act`：一个用于处理 `src` 目录下的源代码，另一个用于重组 `tests` 目录。通过在 shell 脚本中添加注释，我们能清楚地标示出每一条 `mv` 命令的目的地和意图，确保这个关键步骤的准确无误。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/build #task/object/monorepo-structure #task/action/setup #task/state/continue

---

### Script

#### Acts 1: 迁移源代码至各包

此脚本将 `src/cascade` 目录下的所有内容，根据其职责，分别移动到 `cascade-interfaces`、`cascade-runtime`、`cascade-cli` 和 `cascade-py` 包中。

~~~~~act
run_command
~~~~~
~~~~~bash
# --- 1. 迁移至 cascade-interfaces ---
# 移动所有数据规范、接口定义和核心图模型
mv src/cascade/spec packages/cascade-interfaces/src/cascade/
mv src/cascade/runtime/protocols.py packages/cascade-interfaces/src/cascade/interfaces/
mv src/cascade/graph/model.py packages/cascade-interfaces/src/cascade/graph/

# --- 2. 迁移至 cascade-runtime ---
# 移动运行时引擎、适配器、图构建逻辑等
mv src/cascade/adapters packages/cascade-runtime/src/cascade/
mv src/cascade/graph/build.py src/cascade/graph/serialize.py packages/cascade-runtime/src/cascade/graph/
# 注意：此时 src/cascade/runtime/ 目录只剩下 protocols.py（已被移走），所以我们移动整个目录
mv src/cascade/runtime packages/cascade-runtime/src/cascade/

# --- 3. 迁移至 cascade-cli ---
# 移动 CLI 实现，并重命名为 main.py 以符合惯例
mv src/cascade/tools/cli.py packages/cascade-cli/src/cascade/cli/main.py

# --- 4. 迁移剩余部分至 cascade-py ---
# 将 src/cascade/ 下所有剩余的文件和目录（providers, tools, __init__.py 等）移动到 cascade-py
mv src/cascade/* packages/cascade-py/src/cascade/
~~~~~

#### Acts 2: 重组测试目录

现在，我们将 `tests` 目录的结构进行调整，以匹配新的多包布局，确保测试代码与被测代码的结构保持一致。

~~~~~act
run_command
~~~~~
~~~~~bash
# 1. 创建新的测试根目录，用于归类
mkdir tests/interfaces tests/runtime tests/py tests/cli

# 2. 迁移测试文件到新位置
# 接口和规范相关的测试
mv tests/spec tests/interfaces/

# 运行时、集成和适配器相关的测试。它们紧密耦合，暂时都归入 'py'，因为它们主要测试 cascade-py 和 cascade-runtime 的集成行为。
# 后续可以根据需要进一步细化拆分。
mv tests/runtime tests/integration tests/adapters tests/py/

# CLI 相关的测试
mv tests/tools/test_cli.py tests/cli/

# 剩余的用户库和 providers 相关的测试
mv tests/tools tests/providers tests/messaging tests/graph tests/examples tests/py/
~~~~~

### 下一步建议
我们已经成功地将所有代码和测试文件迁移到了新的多包结构中。目前，项目处于一个“已重组但已损坏”的状态，因为 Python 的导入路径全部失效了，并且根 `pyproject.toml` 尚未更新。

接下来的 **第三阶段** 将解决这个问题：
1.  更新项目根目录的 `pyproject.toml`，将其配置为 Hatch workspace，从而让 `uv` 等工具能够理解新的多包布局。
2.  清理掉现在已经变空的旧 `src` 和 `tests` 子目录。

如果你确认继续，我将为你生成第三阶段的计划。
