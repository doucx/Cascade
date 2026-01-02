你说得完全正确。这是一个非常敏锐的架构观察，也是我之前计划中的一个疏忽。

感谢你指出的错误。测试失败是因为我只迁移了源代码，却忘记了与之对应的单元测试。更重要的是，你提出的**“不希望 vm 依赖 std”**是一个关键的架构原则。VM 应该是一个纯粹的、通用的执行引擎，它不应该知道任何“标准库”的具体实现。标准库是使用 VM 规范的“应用”，而不是 VM 的“依赖”。

我之前的计划错误地引入了这个不必要的依赖。我们现在就来纠正这个错误。

我将生成一个新的计划，该计划不仅会修复测试失败的问题，还会通过将相关单元测试一并迁移到 `cascade-std` 来彻底移除 `cascade-vm` 对 `cascade-std` 的依赖，从而实现更清晰的架构分离。

## [WIP] fix: 迁移指令集单元测试并移除 vm 对 std 的依赖

### 错误分析

我之前的计划 (`[WIP] feat: 迁移标准指令集到 cascade-std`) 存在两个核心问题：
1.  **遗漏了单元测试**：计划只移动了 `bleacher.py`, `stainer.py`, `observer.py` 的源代码，但将它们的单元测试 (`tests/unit/instructions/*`) 遗留在了 `cascade-vm` 包中。这直接导致了 `pytest` 在收集测试时因找不到模块而报错。
2.  **引入了错误的依赖关系**：为了让 `cascade-vm` 中的集成测试能找到迁移后的代码，我为其添加了对 `cascade-std` 的依赖。正如你所指出的，这是一个架构错误，它破坏了 VM 作为通用引擎的纯粹性。

正确的做法是，与代码一同迁移其单元测试，并解除这个不当的依赖关系。集成测试 (`test_resource_backpressure.py`) 依然需要从 `cascade.std` 导入，但它本身位于 `cascade-vm` 的 `tests` 目录下，这在测试环境中是允许的，并且不会影响 `cascade-vm` 包本身的运行时依赖。

### 用户需求

修复因指令集迁移导致的测试失败，并将相关的单元测试文件移动到 `cascade-std` 包，同时解除 `cascade-vm` 对 `cascade-std` 的显式依赖。

### 评论

这是一个非常重要的修正，它不仅仅是修复一个 Bug，更是对系统架构的一次净化。将代码和其单元测试视为一个不可分割的整体进行迁移，是维护代码库健康的基本原则。解除 `vm` -> `std` 的依赖，则捍卫了我们核心组件的纯粹性和通用性。

### 目标

1.  从 `cascade-vm` 的 `pyproject.toml` 中移除对 `cascade-std` 的依赖。
2.  将 `tests/unit/instructions` 目录及其内容从 `cascade-vm` 移动到 `cascade-std`。
3.  更新被移动的测试文件中的导入路径，使其指向新的 `cascade.std.triad` 命名空间。
4.  清理 `cascade-vm` 中残留的空目录。

### 基本原理

我们将通过一系列精确的 `patch_file` 和 `move_file` 操作来完成这次修正。
1.  首先，逆向操作，从 `cascade-vm/pyproject.toml` 中删除之前添加的依赖项，恢复其独立性。
2.  然后，创建新的测试目录结构 `packages/cascade-std/tests/unit/triad`。
3.  使用 `move_file` 将 `test_*.py` 文件迁移到新位置。
4.  对每一个被移动的测试文件使用 `patch_file`，将其中的导入语句从 `cascade.vm.instructions` 更新为 `cascade.std.triad`。
5.  最后，使用 `rm -rf` 清理 `cascade-vm` 中遗留的空测试目录。

### 标签

#intent/fix #flow/ready #priority/critical #comp/vm #comp/build #scope/core #ai/brainstorm #task/domain/architecture #task/object/cascade-std #task/action/migration #task/state/continue

---

### Script

#### Acts 1: 从 `cascade-vm` 移除对 `cascade-std` 的依赖

这是最关键的一步，我们首先修正架构上的错误。

~~~~~act
patch_file
packages/cascade-vm/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
  "cascade-spec",
  "cascade-common",
  "cascade-std",
]
~~~~~
~~~~~toml.new
dependencies = [
  "cascade-spec",
  "cascade-common",
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
cascade-std = { workspace = true }
~~~~~
~~~~~toml.new
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-common = { workspace = true }
~~~~~

#### Acts 2: 迁移单元测试文件

现在，我们将单元测试移动到它们所属的代码包 `cascade-std` 中。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-std/tests/unit/triad
~~~~~

~~~~~act
move_file
packages/cascade-vm/tests/unit/instructions/test_bleacher.py
packages/cascade-std/tests/unit/triad/test_bleacher.py
~~~~~

~~~~~act
move_file
packages/cascade-vm/tests/unit/instructions/test_stainer.py
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~

~~~~~act
move_file
packages/cascade-vm/tests/unit/instructions/test_observer.py
packages/cascade-std/tests/unit/triad/test_observer.py
~~~~~

#### Acts 3: 修复已迁移测试的导入路径

更新这些测试文件，让它们从正确的位置导入模块。

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_bleacher.py
~~~~~
~~~~~python.old
from cascade.vm.instructions.bleacher import standard_bleacher
~~~~~
~~~~~python.new
from cascade.std.triad.bleacher import standard_bleacher
~~~~~

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~
~~~~~python.old
from cascade.vm.instructions.stainer import standard_stainer
~~~~~
~~~~~python.new
from cascade.std.triad.stainer import standard_stainer
~~~~~

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_observer.py
~~~~~
~~~~~python.old
from cascade.vm.instructions.observer import standard_observer, ObservedEvent
~~~~~
~~~~~python.new
from cascade.std.triad.observer import standard_observer, ObservedEvent
~~~~~

#### Acts 4: 清理 `cascade-vm` 中的旧测试目录

最后，删除 `cascade-vm` 中残留的空目录。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf packages/cascade-vm/tests/unit/instructions
~~~~~

### 下一步建议

我们已经完成了这次重要的修正，现在 `cascade-vm` 重新变得独立，而 `cascade-std` 则包含了它自己的代码和测试，架构更加清晰和健壮。

现在我们已经回到了正轨。下一步依然是**任务 T3: 实现采样芯片 (Probe ICs)**。

如果您准备好了，我将开始为 `ParamProbe`, `EnvProbe`, 和 `Pulse` 创建文件和基本实现。
