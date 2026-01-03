分析正确。连续两次超时，即使在负载降低后，也强烈表明问题不是性能瓶颈（活锁），而是**死锁**。系统根本没有在取得进展。

你提出的观测需求是解决这个问题的关键。我们当前的测试断言就像只盯着工厂的“成品出口”，而完全忽略了内部所有“传送带”和“机床”的运转情况。当成品不再出来时，我们不知道是哪个环节卡住了。

为了诊断问题，我们必须连接一根“观测总线”，监听**物理场中每一个节点**的生命周期事件，而不仅仅是我们定义的逻辑任务。这将为我们提供一份详细的“物理模拟日志”，揭示死锁的确切位置。

`EventDrivenRunner` 和 `standard_observer` 已经具备了这个能力，我们只需要修改测试用例，让它捕获并打印所有事件。

## [WIP] debug(test): 为资源竞争测试增加全物理场事件观测

### 错误分析
`test_resource_scarcity_topology_and_execution` 持续超时，表明存在死锁。根本原因未知，因为测试的观测范围被限定在逻辑任务上 (`startswith("node_")`)，导致所有关键的资源管理节点（Allocator, Reclaimer, Requestor 等）的活动对我们来说都是一个黑箱。我们无法判断是资源没有被正确释放，还是 Ledger 令牌在某个循环中被卡住。

### 用户需求
为失败的测试添加一根“观测线”，捕获并打印出物理场中**所有**节点的 `start` 和 `end` 事件，以便诊断死锁的根源。

### 评论
这是将 Cascade 的“全息可观测性”理念用于自身调试的绝佳实践。通过移除事件过滤器并增加日志记录，我们将把 `EventDrivenRunner` 从一个简单的“测试器”升级为一个强大的“物理场分析仪”。日志输出将清晰地展示出哪个节点被频繁调用（可能的活锁），或者哪个节点在等待一个永远不会到来的输入（死锁）。

### 目标
-   修改 `test_resource_scarcity_topology_and_execution` 测试用例。
-   移除 `collection_predicate` 中的 `id` 过滤器，使其捕获所有节点的生命周期事件。
-   在谓词函数中加入 `print` 语句，实时打印捕获到的事件，生成一份详细的执行日志。

### 基本原理
**诊断优于猜测**：在复杂的并发系统中，盲目地修改代码来“修复”一个未知的死锁是低效且危险的。正确的做法是首先提升系统的可观测性，让问题自我暴露。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #concept/observability #scope/test #task/domain/testing #task/object/debugging #task/action/instrument #task/state/continue

---

### Script

#### Acts 1: 为资源竞争测试安装“观测总线”

我们将修改 `test_resource_scarcity_topology_and_execution`，移除事件过滤器并添加日志记录。这将把失败的测试用例变成一个强大的诊断工具。

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
    try:
        # Collect all 'start' and 'end' events
        events: List[ObservedEvent] = []
        
        # We wait until we have 2 * TASK_COUNT events (start + end for each)
        # We need a robust condition.
        def collection_predicate(e: ObservedEvent):
            if e.event_type in ("start", "end") and e.trace_data.get("id", "").startswith("node_"):
                events.append(e)
            # Stop when we have all completion events
            completed = sum(1 for x in events if x.event_type == "end")
            return completed == TASK_COUNT

        # Timeout needs to be generous.
        # With request recirculation, the reactor steps many times per useful work.
        await runner.wait_for_event(collection_predicate, timeout=10.0)
~~~~~
~~~~~python.new
    try:
        # Collect all 'start' and 'end' events
        events: List[ObservedEvent] = []
        
        print("\n--- Physical Field Event Log ---")
        
        # We wait until we have 2 * TASK_COUNT logical task completions.
        # But we log EVERY physical event to diagnose the deadlock.
        def collection_predicate(e: ObservedEvent):
            # Log ALL physical events for debugging
            node_id = e.trace_data.get("id", "unknown")
            print(f"[{e.event_type.upper():<5}] {node_id}")

            # Only count logical task events for completion condition
            if e.trace_data.get("id", "").startswith("node_"):
                events.append(e)
                
            completed = sum(1 for x in events if x.event_type == "end")
            return completed == TASK_COUNT

        # Timeout needs to be generous.
        # With request recirculation, the reactor steps many times per useful work.
        await runner.wait_for_event(collection_predicate, timeout=10.0)
~~~~~

### 下一步建议
现在，请重新运行测试。我们**期望测试仍然会因超时而失败**，但这没关系。

关键是，这次失败会附带一份详细的**物理场事件日志**。请将完整的失败输出（包括 `--- Physical Field Event Log ---` 部分）提供给我。

通过分析这份日志，我们可以精确地看到：
-   `Allocator` 和 `Reclaimer` 是否在交替执行？
-   `Ledger` 令牌是否在它们之间正常流动？
-   `RelBuffer` 是否接收到了来自 `Stainer` 的释放信号？

这份日志将是解开死锁之谜的“罗塞塔石碑”。
