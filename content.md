好的，既然测试已经通过，我们将把这些优化和基础设施的改进作为一个完整的逻辑单元提交。

## [COMMIT] refactor(observatory): 迁移 Kuramoto Agent 至 VM TailCall 并优化基础设施

### 用户需求
提交已验证的 Kuramoto Agent 迁移代码，包括启用 VM 模式、重构网络层目录结构以及新增的调试工具。

### 评论
这次提交标志着 Cascade 实验基础设施的一个里程碑。我们不仅通过 `TailCall` 实现了 Agent 的性能飞跃，还清理了代码结构并建立了基准测试体系。这为后续更大规模（N=10k+）的复杂仿真奠定了物理和性能基础。

### 目标
执行 Git 提交，持久化性能优化成果。

### 基本原理
按照「脚本与 Git 操作互斥」原则，在代码修改验证通过后，通过独立的 `[COMMIT]` 计划完成代码入库，确保提交历史的整洁。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/benchmarks #scope/perf #ai/instruct #task/domain/vm #task/object/kuramoto-agent #task/action/migration #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将所有涉及的文件添加到暂存区，并执行一次详细的提交。

~~~~~act
git_add
observatory/agents/kuramoto.py
observatory/experiments/run_fireflies.py
observatory/networking/direct_channel.py
observatory/scripts/debug_headless_throughput.py
observatory/scripts/debug_renderer_throughput.py
observatory/scripts/profile_entry.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(observatory): migrate Kuramoto agent to VM TailCall and optimize infra

Migrated the Kuramoto firefly agent to the high-performance VM path using the
TailCall primitive. This refactoring eliminates the graph building and solving
overhead per simulation tick, enabling massive agent counts with minimal CPU latency.

Key changes:
- Refactored kuramoto.py: Removed nested task definitions in favor of imperative
  async logic returning TailCall objects.
- Updated run_fireflies.py: Enabled use_vm=True for agent execution.
- Restructured networking: Moved DirectChannel to a stable location at
  observatory/networking/ to improve module organization.
- Added Benchmarking Suite: Introduced specialized scripts for measuring headless
  throughput, renderer performance, and detailed profiling (cProfile).
~~~~~

### 下一步建议
- **性能基准记录**: 建议使用 `observatory/scripts/profile_entry.py` 运行一次详细的性能画像分析，记录下当前的 CPU 分布情况作为“黄金基准”。
- **VM 能力增强**: 考虑下一步在 VM 的 `_dispatch` 循环中集成 `ConstraintManager` 的检查逻辑，使 `TailCall` 递归中的每一跳都能享受到 Cascade 的并发治理能力。
