好的，既然测试已经验证了 VM 路径与治理能力的集成以及全局资源的共享，现在我们将这些核心变更提交到代码库。

## [COMMIT] feat(runtime): 集成治理能力至 VM 并支持全局资源共享

### 用户需求
将 `ResourceManager` 和 `ConstraintManager` 集成到 VM 执行路径中，并支持在多个 `Engine` 实例间共享资源管理器以实现全局限制。

### 评论
这次提交完成了 Cascade 架构演进中的一个关键闭环：**高性能执行与严格治理的统一**。通过在 VM 的指令分发层集成资源契约，我们确保了即使在零开销递归（TailCall）中，系统的资源安全和速率限制依然有效。同时，支持 `ResourceManager` 注入为未来的分布式协同和更复杂的资源分配策略打开了大门。

### 目标
1.  提交 `cascade-interfaces` 的变更，扩展指令集以携带约束元数据。
2.  提交 `cascade-runtime` 的变更，包括 Compiler 增强、VM 治理集成以及 Engine 的重构。
3.  提交 `run_fireflies.py` 的重构，展示如何利用新增能力进行大规模受控仿真。

### 基本原理
按照隔离变更与提交的原则，在通过 `run_fireflies --limit` 验证了 VM 能够正确响应手动设置的并发限制后，通过此计划将代码固化。这确保了主干分支的代码始终处于“已验证”状态。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #comp/interfaces #comp/experiments #concept/vm #concept/governance #scope/core #scope/api #ai/instruct #task/domain/runtime #task/object/governance-integration #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交治理能力集成与实验脚本重构

我们将跨越多个包的修改点添加到暂存区，并创建一个内容详尽的提交记录。

~~~~~act
git_add .
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime): integrate governance into VM and support shared resources

This commit brings the core governance capabilities of Cascade (resource
management and global constraints) to the high-performance VM execution path.

Key Improvements:
- **VM Governance**: The VirtualMachine now performs permission checks and
  resource acquisition/release within its instruction dispatch loop. This
  ensures that TailCall recursion respects all runtime constraints.
- **Blueprint Enhancement**: The 'Call' instruction now carries task metadata
  and static ResourceConstraints, extracted by the compiler.
- **Shared Resource Management**: Refactored the Engine to allow injection of
  an external ResourceManager. This enables multiple Engine instances to
  coordinate and share global resource pools (e.g., a global concurrency limit).
- **Experiment Refactoring**: Updated run_fireflies.py to support a global
  --limit CLI option, demonstrating the effectiveness of the VM governance
  and resource sharing in a massive-scale (N=2500) agent simulation.
~~~~~

### 下一步建议
- **性能回归测试**: 虽然功能已集成，但增加了约束检查可能会对 VM 纯性能产生细微影响。建议再次运行 `tco_performance.py` 观察 TPS 变化。
- **分布式限流**: 下一阶段可以尝试将 `RedisStateBackend` 与 `shared_resource_manager` 结合，探索跨进程的真正分布式并发控制。
