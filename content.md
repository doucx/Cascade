测试已全部通过，系统现在处于稳定且确定的状态。

我将生成一个 `[COMMIT]` 计划，将这些关键的并发修复和测试套件优化集成到代码库中。

## [COMMIT] fix: 修复 VM 调度活锁、内核恐慌及测试延时冲突

### 错误分析

在引入新的 `VMExecutionStrategy` 后，发现了三个导致集成测试超时的不同维度的问题：

1.  **调度活锁 (Livelock)**: `Machine` 主循环在使用 `asyncio.sleep(0)` 忙等待时过于激进，在某些负载下会导致事件循环饥饿，使得后台计算任务的结果无法及时返回，进而导致死锁。
2.  **内核恐慌 (Kernel Panic)**: 测试工具 `EventDrivenRunner` 未能与生产环境同步，缺少 `system.egress_queue` 资源的注册。这导致 `standard_egress` 节点在触发时因找不到依赖而崩溃。
3.  **测试逻辑冲突**: `test_is_idle_state_changes` 中包含一个硬编码的 1 秒 `sleep`，这与测试框架的全局超时限制重合，导致在环境略有波动时必然失败。

### 用户需求

巩固并提交已验证的修复方案，确保 VM 执行策略在并发场景下的稳健性，并保证集成测试套件的长期稳定性。

### 评论

这是一次非常深入的调试过程。通过解决这三个问题，我们不仅让测试通过了，更重要的是，我们完善了 `Machine` 的公平调度机制，并确保了测试基础设施（Harness）与生产环境（Harness）在架构上的本体对齐。

### 目标

1.  将经过验证的调度修复、测试工具完善和测试用例优化提交到 Git。
2.  确保宏观任务“修复并发测试”圆满结束。

### 基本原理

通过 `git_add` 和 `git_commit` 指令，我们将之前的零散修复（`machine.py` 的微延迟、`harness.py` 的资源注册、`test_compute_adapters.py` 的耗时优化）作为一个完整的逻辑单元持久化。

### 标签

#intent/fix #flow/ready #priority/high #comp/runtime #comp/tests #concept/state #task/domain/testing #task/object/concurrency-bugs #task/action/bug-fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 添加更改到暂存区

我们将所有涉及修复的文件添加到 Git 暂存区。

~~~~~act
git_add
packages/cascade-vm/src/cascade/vm/machine.py
packages/cascade-vm/src/cascade/vm/harness.py
packages/cascade-vm/tests/integration/test_compute_adapters.py
~~~~~

#### Acts 2: 提交变更

我们将创建一个详尽的提交记录，说明修复的三个核心问题。

~~~~~act
git_commit
~~~~~
~~~~~text
fix(vm): resolve concurrency livelocks and kernel panics in VM execution

This commit aggregates three critical fixes discovered during VM integration testing:

1. Scheduler Fairness: Replaced 'asyncio.sleep(0)' with 'asyncio.sleep(0.001)' in the Machine loop. This prevents a livelock situation where a tight polling loop starves the event loop, ensuring background compute tasks can report results back to the reactor.

2. Test Harness Alignment: Updated 'EventDrivenRunner' to initialize and register the 'system.egress_queue' resource. This resolves a kernel panic in integration tests where 'standard_egress' nodes failed due to missing dependencies.

3. Test Robustness: Optimized 'test_is_idle_state_changes' by reducing hardcoded delays that conflicted with the global 1s test timeout, ensuring deterministic passes across different execution environments.
~~~~~

### 下一步建议

- **持续监控**: 随着更多复杂工作流的引入，应继续监控 `Machine` 的调度开销。
- **扩展 Harness**: 考虑将 `EventDrivenRunner` 中通用的资源初始化逻辑提取为辅助函数，以便未来扩展更多的系统资源。
- **性能回归测试**: 建立一个基准测试，监控引入 `0.001` 延迟后对极轻量级工作流吞吐量的影响。
