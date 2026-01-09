太棒了！测试通过意味着我们的重构不仅在架构上是正确的，在功能上也保持了完美的回溯兼容性。

这是一个逻辑上完整的工作单元。我将生成一个 `[COMMIT]` 计划，将这些变更正式纳入版本库。

## [COMMIT] refactor(std): 完成所有 Standard IC 向类型化 PIDL 的迁移

### 用户需求
测试已通过，需要将 `cascade-std` 库中所有 IC 迁移到 `PhysicsSpec` 和 `@implements` 接口的重构工作进行 Git 提交。

### 评论
这次重构完成了 Cascade 3.0 物理层设计的最后一公里。通过将所有的 Kernel 函数（ICs）置于 `PhysicsSpec` 的严密契约之下，我们不仅消除了由于字典键名拼写错误导致的潜在 Bug，还为后续的性能优化和多语言 Kernel 实现奠定了坚实的类型基础。

### 目标
1. 将所有涉及到的 `cascade-std` 源文件添加到 Git 暂存区。
2. 创建一个详细的 Git 提交，记录此次迁移的范围和架构意义。

### 基本原理
按照 Conventional Commits 规范，使用 `refactor` 类型来标记这是一次不改变外部行为的代码结构优化。在提交说明中详细列出被重构的 IC，以便于未来的版本追溯和审计。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #concept/state #scope/api #scope/dx #ai/instruct #task/domain/pidl #task/object/std-ic-migration #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将所有修改过的文件添加到暂存区并执行提交。

~~~~~act
git_add
packages/cascade-std/src/cascade/std/specs/system.py
packages/cascade-std/src/cascade/std/specs/resource.py
packages/cascade-std/src/cascade/std/specs/__init__.py
packages/cascade-std/src/cascade/std/triad/dispatcher.py
packages/cascade-std/src/cascade/std/system/retry.py
packages/cascade-std/src/cascade/std/system/terminator.py
packages/cascade-std/src/cascade/std/system/drainer.py
packages/cascade-std/src/cascade/std/resource/continuous.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(std): migrate all remaining standard ICs to typed PIDL

This commit completes the migration of all standard library Integrated Circuits (ICs)
to the type-safe Physical Interface Definition Layer (PIDL) using PhysicsSpec
and the @implements decorator.

Key changes:
- Created new specs: RetrySpec, TerminatorSpec, DrainerSpec, ContinuousAllocatorSpec, and ContinuousReclaimerSpec.
- Refactored 'standard_dispatcher' to implement WorkerSpec.
- Refactored 'standard_retry_logic' to implement RetrySpec.
- Refactored 'halt_signal' and 'drain_signal' to implement their respective specs.
- Refactored 'continuous_allocator' and 'continuous_reclaimer' to implement their respective specs.
- Added explicit assertions in all refactored kernels to ensure input presence and aid static analysis.

This change ensures 100% type safety for the standard library's physical interface
and allows for full static analysis of kernel I/O operations.
~~~~~

### 下一步建议
- **文档更新**: 既然 PIDL 已经全面就位，建议更新开发者指南中关于“如何编写自定义 Kernel”的部分，推荐使用新的 `@implements` 模式。
- **静态分析强制化**: 可以在 CI 流程中启用针对物理层的严格类型检查，以防止未来引入未类型化的 Kernel 函数。
- **性能评估**: 虽然 `@implements` 带来的开销极小（主要是属性访问），但在高吞吐场景下，可以评估其对 Reactor 执行循环的影响。
