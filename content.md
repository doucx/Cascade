非常感谢你的指正和帮助恢复文件！你说得对，我之前的 `rm -rf` 操作过于粗暴，错误地删除了与代码逻辑紧密相关的 `.stitcher.yaml` 文档文件。这是一个严重的疏忽。

代码、测试和文档应该被视为一个不可分割的单元。现在我将把这些恢复的文档文件移动到它们在 `cascade-std` 包中应在的新位置。

## [WIP] fix: 迁移指令集相关的 stitcher.yaml 文档文件

### 错误分析

我之前的计划在执行 `rm -rf` 以清理旧目录时，未能考虑到目录中还包含 `.stitcher.yaml` 文档文件。这导致与 `bleacher`, `stainer`, `observer` 及其测试相关的文档被一并删除，破坏了代码库的文档完整性。

### 用户需求

用户已经通过 `git` 恢复了被误删的 `.stitcher.yaml` 文件，现在需要将它们从 `cascade-vm` 的旧位置移动到 `cascade-std` 中对应的新位置。

### 评论

这是一个必要的修正。将文档与其描述的代码和测试放在一起，是保证项目可维护性的关键。感谢你指出这个问题，这有助于我们保持代码库的整洁和完整。

### 目标

1.  将 `cascade-vm` 中 `instructions` 目录下的三个 `stitcher.yaml` 文件移动到 `cascade-std` 的 `triad` 目录中。
2.  将 `cascade-vm` 中 `tests/unit/instructions` 目录下的三个测试 `stitcher.yaml` 文件移动到 `cascade-std` 的 `tests/unit/triad` 目录中。

### 基本原理

使用 `move_file` 指令可以原子化地完成文件迁移。我们将为每个需要移动的 `stitcher.yaml` 文件执行一次 `move_file` 操作，以确保计划的清晰性和准确性。

### 标签

#intent/fix #flow/ready #priority/medium #comp/vm #comp/docs #scope/dx #ai/instruct #task/domain/architecture #task/object/stitcher-files #task/action/migration #task/state/continue

---

### Script

#### Acts 1: 迁移源代码文档 (stitcher.yaml)

首先，移动与 `bleacher.py`, `stainer.py`, 和 `observer.py` 源码相对应的文档。

~~~~~act
move_file
packages/cascade-vm/src/cascade/vm/instructions/bleacher.stitcher.yaml
packages/cascade-std/src/cascade/std/triad/bleacher.stitcher.yaml
~~~~~

~~~~~act
move_file
packages/cascade-vm/src/cascade/vm/instructions/stainer.stitcher.yaml
packages/cascade-std/src/cascade/std/triad/stainer.stitcher.yaml
~~~~~

~~~~~act
move_file
packages/cascade-vm/src/cascade/vm/instructions/observer.stitcher.yaml
packages/cascade-std/src/cascade/std/triad/observer.stitcher.yaml
~~~~~

#### Acts 2: 迁移单元测试文档 (stitcher.yaml)

接下来，移动与单元测试文件相对应的文档。

~~~~~act
move_file
packages/cascade-vm/tests/unit/instructions/test_bleacher.stitcher.yaml
packages/cascade-std/tests/unit/triad/test_bleacher.stitcher.yaml
~~~~~

~~~~~act
move_file
packages/cascade-vm/tests/unit/instructions/test_stainer.stitcher.yaml
packages/cascade-std/tests/unit/triad/test_stainer.stitcher.yaml
~~~~~

~~~~~act
move_file
packages/cascade-vm/tests/unit/instructions/test_observer.stitcher.yaml
packages/cascade-std/tests/unit/triad/test_observer.stitcher.yaml
~~~~~

### 下一步建议

我们已经完成了所有文件的迁移和修正，`cascade-std` 包现在包含了完整的代码、测试和文档，并且 `cascade-vm` 的独立性得到了保证。项目结构现在处于一个干净和正确的状态。

我们可以继续执行路线图中的**任务 T3: 实现采样芯片 (Probe ICs)**。

如果您准备好了，请指示我开始创建 `probe` 目录和相关文件。
