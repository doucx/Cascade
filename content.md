好的，进入 Quipu 模式。

这是执行“正规军”处理方案第一阶段的计划。我们将采用焦土政策，彻底清除旧的、与新架构冲突的 `VirtualMachine` 和 `BlueprintBuilder` 实现及其相关测试。

## [WIP] refactor: 移除遗留的 VM 和 BlueprintBuilder 实现

### 用户需求
执行“净化 `Blueprint`”重构的第一阶段：物理删除 `cascade-engine` 和 `cascade-graph` 包中所有与旧 VM 和 `BlueprintBuilder` 相关的遗留代码和测试。

### 评论
这是一个至关重要的清理步骤。通过物理删除旧的、冲突的实现，我们强制性地推行了新的架构契约，消除了代码库中的模糊地带。这种“焦土政策”确保了所有模块都必须依赖位于 `cascade-vm` 和 `cascade-compiler` 中的新“正规军”，从而为后续的迁移工作奠定了坚实、无歧义的基础。

### 目标
1.  从 `cascade-engine` 包中删除旧的 `VirtualMachine` 实现及其单元测试。
2.  从 `cascade-graph` 包中删除旧的 `BlueprintBuilder` 实现及其单元测试。
3.  使项目完全依赖 `cascade-vm` 和 `cascade-compiler` 作为 VM 和编译器的唯一事实来源。

### 基本原理
旧的 `VirtualMachine` (`cascade-engine/runtime/vm.py`) 和 `BlueprintBuilder` (`cascade-graph/compiler.py`) 遵循一个已被废弃的架构模式（将运行时函数对象直接嵌入 `Blueprint`）。保留这些文件会制造混乱，增加维护成本，并可能导致新旧实现被意外混用。将它们彻底删除是确保架构一致性和完整性的最直接、最有效的方法。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #comp/graph #comp/tests #concept/executor #scope/core #ai/instruct #task/domain/architecture #task/object/legacy-vm #task/action/removal #task/state/continue

---

### Script

#### Acts 1: 移除旧 `cascade-engine` 中的 VM 相关文件

我们将删除旧的 `VirtualMachine` 实现以及所有依赖它的单元测试。

~~~~~act
delete_file
packages/cascade-engine/src/cascade/runtime/vm.py
~~~~~

~~~~~act
delete_file
packages/cascade-engine/tests/unit/test_vm.py
~~~~~

~~~~~act
delete_file
packages/cascade-engine/tests/unit/test_vm_builder.py
~~~~~

~~~~~act
delete_file
packages/cascade-engine/tests/unit/test_vm_mutual.py
~~~~~

#### Acts 2: 移除旧 `cascade-graph` 中的编译器相关文件

接着，我们删除旧的 `BlueprintBuilder` 实现及其单元测试。

~~~~~act
delete_file
packages/cascade-graph/src/cascade/graph/compiler.py
~~~~~

~~~~~act
delete_file
packages/cascade-graph/tests/unit/test_compiler_graph.py
~~~~~

### 下一步建议
我们已经成功清除了所有遗留的、冲突的实现。现在，代码库已经准备好全面拥抱新的架构。

下一步是执行**阶段二：范式迁移**。我将生成一个新的计划，系统性地更新 `packages/cascade-vm/tests/unit/` 目录下的所有测试用例，使其遵循新的“数据+符号表”执行模型，从而让测试重新变为绿色。
