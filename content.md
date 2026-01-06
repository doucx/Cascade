太棒了！8.7 Mops/s 的性能数据证明了我们转向“绝对同步内核”战略的正确性。0.11 μs 的延迟意味着我们现在拥有一种接近物理极限的超低延迟调度能力。同时，`Machine` 集成测试的通过标志着我们已经成功打通了物理层与计算层之间的司法管辖边界。

我将生成一个 `[COMMIT]` 计划，将这些验证成果和关键修复正式提交到代码库。

## [COMMIT] feat(vm): 完成阶段 3 验证并修复计算服务竞态条件

### 用户需求

根据“奇点内核重构”项目计划，在完成阶段 3 的验证和修复后，创建一个完整的 Git 提交。

### 评论

这是一个重大的里程碑。我们不仅在理论上构想了一个高性能架构，而且通过基准测试和端到端集成测试在物理上实现了它。修复 `LocalComputeService` 中的竞态条件是确保系统在生产环境下确定性运行的关键。现在的基准性能（~8.7 Mops/s）为 Cascade 未来处理大规模、高并发工作流提供了坚实的基础。

### 目标

1.  将阶段 3 涉及的所有修改添加到 Git 暂存区。
2.  创建一个详尽的 Git 提交，记录性能数据和核心修复逻辑。

### 基本原理

阶段 3 的任务旨在验证重构后的系统是否达到了设计的性能指标和正确性标准。通过集成测试发现并修复的竞态条件属于架构的核心健壮性改进。将这些更改作为一个逻辑单元提交，有助于保持项目历史的清晰，并为后续的架构固化提供基准。

### 标签

#intent/build #flow/ready #priority/high #comp/vm #comp/tests #concept/executor #scope/core #ai/instruct #task/domain/vm #task/object/sync-kernel-validation #task/action/completion #task/state/end

---

### Script

#### Acts 1: 提交验证成果与核心修复

我们将基准测试脚本、`Machine` 协调逻辑、`ComputeService` 的竞态修复以及新的集成测试一并提交。

~~~~~act
git_add
scripts/benchmark_vm_tco.py
packages/cascade-vm/src/cascade/vm/compute/service.py
packages/cascade-vm/src/cascade/vm/machine.py
tests/vm/integration/test_machine_integration.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(vm): Validate Sync Kernel performance and fix compute race condition

This commit completes Phase 3 of the Singularity Project, establishing the
performance and correctness baselines for the new synchronous reactor.

Key changes:
1.  **Benchmarking**: Refactored 'benchmark_vm_tco.py' for the sync kernel,
    demonstrating performance of ~8.7 Mops/s with 0.11us step latency.
2.  **Compute Service Fix**: Resolved a critical race condition in
    'LocalComputeService' where the machine could enter an idle state during
    the gap between a request being dequeued and its processing task starting.
    Implemented a "pre-increment" strategy for '_active_count'.
3.  **Machine Observability**: Added structured debug logging to the
    'Machine.run()' loop to track reactor firing, ingress status, and
    asynchronous plane load.
4.  **Integration Testing**: Added 'test_machine_integration.py' as the new
    "gold standard" for end-to-end physical-to-async coordination, verifying
    successful task completion and Machine auto-quiescence.
~~~~~

### 下一步建议

阶段 3 已正式结束，Cascade 的“心脏”——物理内核现在既快又稳。

根据项目计划，下一步是 **阶段 4：文档与知识固化**。我建议我们首先执行 **任务 4.1：重写白皮书核心章节**，将“绝对同步内核”和“二分图物理场”这些新概念正式写入架构规范，彻底消除旧架构的影子。如果你准备好了，我们可以开始重写白皮书。
