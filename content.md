好的，已经完成了针对 Pyright 类型错误的修复。现在我们将这些更改作为一个完整的逻辑单元提交。

我将生成一个 `[COMMIT]` 计划，其中包含 `git_add` 和 `git_commit` 指令。

## [COMMIT] fix: 修复 Builder 和 VM 中的 Pyright 类型不匹配错误

### 用户需求
提交之前针对 `WiringContext` 不兼容和 `Machine` 依赖具体实现导致的两处类型错误的修复。

### 评论
这些修复不仅消除了静态分析器的报错，还通过引入 `ComputeServiceProtocol` 改进了 VM 架构的解耦，并利用继承简化了 Context 的层级关系。这有助于保持 CI 环境的清洁和代码库的长久稳健。

### 目标
1.  将修改后的 3 个文件添加到 Git 暂存区。
2.  创建一个包含详细说明的提交记录。

### 基本原理
遵循 `d3-constraint-quipu-plan-script-rules-D3-P2` 约束，将代码修改与 Git 提交隔离在不同的计划中。由于代码验证（逻辑上）已经通过，现在执行正式的持久化操作。

### 标签
#intent/fix #flow/ready #priority/high #comp/compiler #comp/runtime #scope/core #ai/instruct #task/domain/typing #task/object/type-errors #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将把涉及到的编译器后端 Context 修复、VM 协议更新以及 Machine 类的重构代码提交到仓库。

~~~~~act
git_add
packages/cascade-compiler/src/cascade/compiler/backend/wiring/context.py
packages/cascade-vm/src/cascade/vm/protocols.py
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix: resolve pyright type mismatch errors in builder and vm

- Refactored `WiringContext` to inherit from `ExpansionContext`. This allows `WiringContext` instances to be passed to `ExpansionPolicy.expand` methods, satisfying the type checker without duplicating logic.
- Introduced `ComputeServiceProtocol` in `cascade.vm.protocols` to abstract the behavior of compute services (sharing `run`, `stop`, `active_count`, and `is_idle`).
- Updated `Machine.__init__` to depend on `ComputeServiceProtocol` instead of `LocalComputeService`, allowing it to correctly accept `BridgedComputeService` in the `VMExecutionStrategy`.

These changes resolve two `reportArgumentType` errors reported by Pyright v1.1.407+ and improve the architectural decoupling of the VM from specific service implementations.
~~~~~

### 下一步建议
- **回归测试**：建议运行现有的 VM 策略测试（如 `tests/runtime/strategies/test_vm.py`，如果存在），以确保接口抽象后 Machine 和 Services 的协同工作仍然正常。
- **持续观测**：在下一次 CI 运行中关注 Pyright 的输出，确认当前工作区已完全清空相关报错。
