好的，测试通过意味着我们的物理执行逻辑和观测机制都是稳健的，只是测试代码在断言逻辑上之前存在偏差。现在我们将这些改进作为一个完整的逻辑单元提交。

## [COMMIT] test(compiler): fix event filtering and concurrency analysis in resource test

### 用户需求
修正资源竞争集成测试中的事件收集和断言逻辑，使其兼容基于哈希的任务 ID，并能正确分析任务并发度。

### 评论
这个修复确保了测试套件的可靠性。通过区分“等待结束条件”和“数据分析需求”，我们解决了由于 IR 生成器升级导致的测试脆弱性问题。目前测试已能稳定地验证在资源受限的情况下，系统既没有死锁，也严格遵守了容量限制。

### 目标
1. 将 `packages/cascade-compiler/tests/integration/test_resource_contention.py` 的改动提交到 Git。
2. 确保提交信息详细描述了对 `collection_predicate` 的修正及其背后的原因。

### 基本原理
根据 [COMMIT] 标志规范，该计划仅包含 Git 操作。我们已经验证代码在当前环境中运行正确。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/tests #concept/observability #scope/core #ai/instruct #task/domain/testing #task/object/integration-test #task/action/fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交测试修复

我们将修改后的测试文件添加到暂存区并执行提交。

~~~~~act
git_add
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
test(compiler): fix event filtering and concurrency analysis in resource test

Fixed a regression in 'test_resource_scarcity_topology_and_execution' caused by the move to hash-based task IDs and overly aggressive event filtering.

Changes:
- Removed the broken dependency on 'node_' ID prefix in the collection predicate, as IRGenerator now produces content-based hashes.
- Fixed the event collection logic to preserve both 'start' and 'end' events. Previously, it only collected 'end' events to satisfy the completion condition, which broke the subsequent concurrency analysis that relies on 'start' timestamps.
- The predicate now correctly uses 'end' events as the flow control signal while maintaining a complete history for data assertions.

Verified that the test now reliably asserts that max concurrency stays within environment limits (e.g., 3 GPUs for 20 tasks).
~~~~~

### 下一步建议
- **性能监控**: 既然集成测试已经稳定，我们可以考虑为 `EventDrivenRunner` 增加一个统计输出，记录 Reactor 执行的总 `step` 数与有效任务数之比，以此作为衡量调度效率的指标。
- **调度优化**: 日志中显示的“请求风暴”表明 `discrete_allocator` 在高竞争下的重试机制过于频繁，可以作为下一个性能优化周期的重点。
