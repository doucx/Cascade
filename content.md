好的，我们来执行任务 T2：指令集大迁徙。

这个计划的核心是将 VM 的核心逻辑（`bleacher`, `stainer`, `observer`）从 `cascade-vm` 包中剥离出来，迁移到我们新创建的 `cascade-std` 包中。这标志着 VM 向一个纯粹的、无业务逻辑的物理反应堆演进的关键一步。

## [WIP] feat: 迁移标准指令集到 cascade-std

### 用户需求

根据 `Act 0.5` 路线图，执行任务 T2：将 `cascade-vm` 中的 `instructions` 目录内容迁移到 `cascade-std`，并更新相关依赖和导入。

### 评论

这是一个关键的架构重构。它强制性地将“物理定律的执行机制”（VM）与“具体的物理定律本身”（标准指令集）分离开来。这不仅净化了 VM 的职责，也为未来扩展更多标准库（`std`）函数奠定了基础。此举会引入一个新的依赖关系 (`cascade-vm` -> `cascade-std`)，我们需要在 `pyproject.toml` 中明确声明它。

### 目标

1.  在 `cascade-std` 中创建 `triad` 子目录。
2.  将 `bleacher.py`, `stainer.py`, 和 `observer.py` 从 `cascade-vm` 移动到 `cascade-std/triad`。
3.  更新 `cascade-vm` 的 `pyproject.toml`，添加对 `cascade-std` 的依赖。
4.  修正 `cascade-vm` 测试文件中对这些指令的导入路径。
5.  删除 `cascade-vm` 中遗留的、现已为空的 `instructions` 目录。

### 基本原理

我们将分步执行此次重构：
1.  首先使用 `mkdir` 和 `write_file` 准备好目标目录结构。
2.  然后使用 `move_file` 原子化地迁移文件，确保文件历史的完整性。
3.  接着，通过 `patch_file` 修改 `cascade-vm` 的构建配置和源代码，使其适应新的文件位置。这是确保系统在迁移后仍能正确构建和测试的关键。
4.  最后，使用 `run_command` 和 `rm -rf` 清理源目录，完成迁移。

### 标签

#intent/refine #flow/ready #priority/high #comp/vm #comp/build #scope/core #ai/instruct #task/domain/architecture #task/object/cascade-std #task/action/migration #task/state/continue

---

### Script

#### Acts 1: 在 `cascade-std` 中创建目标目录

我们首先在 `cascade-std` 包中创建用于存放三连体（Triad）逻辑的 `triad` 目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-std/src/cascade/std/triad
~~~~~

~~~~~act
write_file
packages/cascade-std/src/cascade/std/triad/__init__.py
~~~~~
~~~~~python
# Standard Triad logic (Execution Units) for the Cascade VM.
~~~~~

#### Acts 2: 迁移指令集文件

现在，我们将三个核心指令文件从 `cascade-vm` 移动到 `cascade-std`。

~~~~~act
move_file
packages/cascade-vm/src/cascade/vm/instructions/bleacher.py
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~

~~~~~act
move_file
packages/cascade-vm/src/cascade/vm/instructions/stainer.py
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~

~~~~~act
move_file
packages/cascade-vm/src/cascade/vm/instructions/observer.py
packages/cascade-std/src/cascade/std/triad/observer.py
~~~~~

#### Acts 3: 更新 `cascade-vm` 的依赖

由于 `cascade-vm` 的测试代码需要用到这些已移走的指令，我们必须为其添加对 `cascade-std` 的依赖。

~~~~~act
patch_file
packages/cascade-vm/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
  "cascade-spec",
  "cascade-common",
]
~~~~~
~~~~~toml.new
dependencies = [
  "cascade-spec",
  "cascade-common",
  "cascade-std",
]
~~~~~

~~~~~act
patch_file
packages/cascade-vm/pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-common = { workspace = true }
~~~~~
~~~~~toml.new
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-common = { workspace = true }
cascade-std = { workspace = true }
~~~~~

#### Acts 4: 更新 `cascade-vm` 测试中的导入路径

迁移完成后，我们需要修复 `cascade-vm` 测试代码中的导入路径，使其指向 `cascade.std`。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
from cascade.vm.instructions.bleacher import standard_bleacher
from cascade.vm.instructions.stainer import standard_stainer
~~~~~
~~~~~python.new
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
~~~~~

#### Acts 5: 清理 `cascade-vm` 中的旧目录

最后，我们删除 `cascade-vm` 中现在已经为空的 `instructions` 目录。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf packages/cascade-vm/src/cascade/vm/instructions
~~~~~

### 下一步建议

我们已经成功地将核心指令集迁移到了 `cascade-std`，并修复了 `cascade-vm` 的依赖和测试。`cascade-vm` 现在是一个更纯粹的执行引擎了。

根据路线图，下一步是**任务 T3: 实现采样芯片 (Probe ICs)**。这包括实现 `ParamProbe`, `EnvProbe`, 和 `Pulse` 等用于从环境中获取输入的标准库函数。

如果你同意，我将开始为这些新的“采样芯片”创建文件和基本框架。
