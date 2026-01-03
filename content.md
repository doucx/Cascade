简要回答：
分析日志发现，所有 20 个任务实际上都已经执行并完成了（日志中有 20 个 `[OBS-END]`），但测试却超时了。这是因为测试断言的谓词错误地过滤了事件：它期待任务 ID 以 `node_` 开头，但 `IRGenerator` 生成的是基于内容的哈希 ID（如 `5449...`）。

## [WIP] fix(test): 修正资源竞争测试中的事件过滤器断言

### 错误分析

**现象**: 测试 `test_resource_scarcity_topology_and_execution` 超时失败。
**证据**:
1.  控制台日志显示了大量的 `[OBS-END]` 事件，去重后数量为 20 个，与 `TASK_COUNT` 一致。这意味着物理层的执行是完全正确的，没有死锁。
2.  日志中的 ID 是哈希值（例如 `5449cba8...`）。
3.  测试代码中的断言谓词：
    ```python
    if e.trace_data.get("id", "").startswith("node_"):
        events.append(e)
    ```
    这个过滤器直接丢弃了所有哈希格式 ID 的事件，导致 `completed` 计数器永远为 0，最终触发超时。

**根本原因**: 测试编写者假设逻辑节点的 ID 是 `node_0`, `node_1` 等可读格式，但当前的 `IRGenerator` 为了保证确定性，使用的是基于内容的哈希 ID。

### 用户需求
修复集成测试 `test_resource_contention.py`，使其能够正确识别并统计使用哈希 ID 的任务完成事件。

### 评论
这是一个典型的测试代码与实现细节（ID 生成策略）脱节的案例。虽然日志中确实存在由于分配器自旋导致的“请求风暴”现象（大量的 `[MAN-START] Allocator`），但这属于性能/效率问题（Livelock风险），并非本次测试失败的直接原因（Timeout）。当务之急是修正断言逻辑，让测试变绿。

### 目标
修改 `packages/cascade-compiler/tests/integration/test_resource_contention.py` 中的 `collection_predicate` 函数，移除对 `node_` 前缀的错误依赖。

### 基本原理
由于该测试拓扑中仅包含我们需要关注的 `resource_heavy_task`，我们可以安全地假设收到的所有 `end` 类型事件都代表一个任务的完成。因此，放宽过滤条件是安全且正确的。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/observability #scope/core #ai/instruct #task/domain/testing #task/object/integration-test #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修正断言谓词

我们将修改 `collection_predicate`，移除 `startswith("node_")` 的检查，改为统计所有的 `end` 事件。

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
            # Only count logical task events for completion condition
            if e.trace_data.get("id", "").startswith("node_"):
                events.append(e)
                
            completed = sum(1 for x in events if x.event_type == "end")
            return completed == TASK_COUNT
~~~~~
~~~~~python.new
            # Only count logical task events for completion condition
            # IRGenerator produces hash-based IDs, so we count all 'end' events
            # assuming only our tasks are generating them in this topology.
            if e.event_type == "end":
                events.append(e)

            return len(events) == TASK_COUNT
~~~~~

### 下一步建议

测试修复后，建议运行该测试以确认通过。

此外，日志中确实暴露了 Allocator 在资源不足时频繁自旋（Request Storm）的问题。虽然这未导致死锁，但浪费了 CPU 资源。在后续的性能优化阶段（Phase 2），我们应该考虑引入一种机制（如 Allocator 在拒绝请求后让出控制权，或使用 Backoff 策略），来减轻这种活锁现象。
