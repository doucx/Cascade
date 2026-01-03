简要回答
测试失败是因为上一步的修复过度过滤了事件，导致只收集了 `end` 事件而丢失了 `start` 事件，使得后续的并发度计算逻辑（依赖 start 时间戳）失效，计算结果为 0，从而触发 `assert 0 > 1`。

## [WIP] fix(test): 修复资源竞争测试中事件收集过激导致并发计算失败的问题

### 错误分析

**现象**: 测试 `test_resource_scarcity_topology_and_execution` 失败，报错 `AssertionError: Tasks ran purely sequentially, which is suspicious. assert 0 > 1`。
**证据**:
1.  错误信息 `assert 0 > 1` 表明 `max_concurrency` 被计算为 0。
2.  并发计算逻辑依赖于 `intervals` 字典中的 `start` 时间戳。
3.  上一轮的修复代码中：
    ```python
    if e.event_type == "end":
        events.append(e)
    ```
    这导致 `events` 列表**仅包含** `end` 事件，完全丢弃了 `start` 事件。因此 `intervals` 字典中没有 `start` 数据，导致并发计算逻辑无法执行，结果默认为 0。

**根本原因**: 修复逻辑为了通过“完成条件检查”，错误地将“事件收集逻辑”也限制在了仅 `end` 事件，破坏了后续断言所需的数据完整性。

### 用户需求
修复测试逻辑，使其既能正确判断测试完成（基于 `end` 事件计数），又能完整收集所有事件（包括 `start`）用于后续的并发度分析。

### 评论
这是一个典型的“修复引入回归”的例子。在处理事件流测试时，必须区分“控制流谓词（何时停止等待）”和“数据流收集（收集什么数据）”这两个关注点。

### 目标
修改 `collection_predicate`，使其无条件收集所有事件，但仅依据 `end` 事件的数量来决定是否结束等待。

### 基本原理
在这个测试拓扑中，只有任务的三连体连接到了观测总线，因此所有收到的 `ObservedEvent` 都是相关的。我们可以安全地收集所有事件。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/integration-test #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修正事件收集逻辑

修改 `collection_predicate`，无条件追加事件到 `events` 列表，但仅通过统计其中的 `end` 事件来返回 `True`。

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
            # Only count logical task events for completion condition
            # IRGenerator produces hash-based IDs, so we count all 'end' events
            # assuming only our tasks are generating them in this topology.
            if e.event_type == "end":
                events.append(e)

            return len(events) == TASK_COUNT
~~~~~
~~~~~python.new
            # Log ALL physical events for debugging
            # node_id = e.trace_data.get("id", "unknown")
            # print(f"[OBS-START] {node_id}" if e.event_type == "start" else f"[OBS-END  ] {node_id}")

            # Collect ALL events so we can analyze start/end intervals later
            events.append(e)

            # Check completion condition based on END events only
            completed = sum(1 for x in events if x.event_type == "end")
            return completed == TASK_COUNT
~~~~~

### 下一步建议

该修复应该能让测试通过。通过后，建议运行全套测试以确保系统稳定性。
然后，鉴于日志中暴露的 Request Storm 问题，建议在后续优化阶段考虑优化 Allocator 的重试机制。
