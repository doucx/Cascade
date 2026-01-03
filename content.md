**诊断完成。**

感谢你提供日志。这份日志虽然充满了无法直接阅读的哈希值，但它本身就暴露了致命的问题所在：**我们的观测存在巨大的盲点**。

1.  **日志揭示的问题**：日志中只包含了逻辑任务（`resource_heavy_task`）的 `START` 和 `END` 事件。我们完全看不到任何与资源管理相关的物理节点的活动，例如 `allocator`, `reclaimer`, `requestor`。系统在这些关键组件上是“瞎”的。

2.  **代码层面的原因**：回顾 `Builder` 的代码，我们只为通过 `Expander` 创建的“三连体”子图（即用户定义的逻辑任务）连接了观测线：
    ```python
    # in builder.py
    # 3.3 Wire task observability TO the sidecar bus
    wire.connect(subgraph.bleacher.id, "obs_output", d_life_id, "in")
    wire.connect(subgraph.stainer.id, "obs_output", d_life_id, "in")
    ```
    所有全局的、手写的物理节点（`Allocator`, `Reclaimer` 等）都没有被连接到 `global.observability.bus`。因此，`standard_observer` 永远不会收到它们的生命周期事件，我们的日志自然就是一片空白。

3.  **推断出的死锁**：
    - 日志显示前三批任务（共 3 * 3 = 9 个）成功启动并完成。这意味着 `Allocator` 至少成功分配了 3 次，并且 `Reclaimer` 也成功回收了资源，使得后续批次得以运行。
    - 在第 9 个任务结束后，日志停止了。这表明第 3 批任务完成了，它们的 `Stainer` 向 `RelBuffer` 发送了释放信号。
    - 此时，`Reclaimer` 应该被激活以回收资源，但它没有。同时，等待队列中的 `Allocator` 也没有被激活来分配新的资源。
    - **结论**：系统进入了死锁。最可能的情况是 `Reclaimer` 和 `Allocator` 都在等待同一个永远不会到来的 `Ledger` 令牌。某个组件（很可能是 `Reclaimer`）在执行过程中未能正确地将 `Ledger` 令牌归还到 `d_ledger` 节点，导致整个资源循环被饿死。

为了验证这个推断并找到确切的“罪魁祸首”，我们必须让这些黑箱节点“开口说话”。

我将创建一个 `debug_wrapper`，这是一个临时的、用于测试的工具，它可以在不修改核心 IC 代码的情况下，为任何物理函数（如 `discrete_allocator`）包裹上 `START`/`END` 日志。

## [WIP] debug(test): Wrap resource ICs with logging to diagnose deadlock

### 错误分析
资源竞争测试因死锁而超时。根本原因是 `Builder` 没有为资源管理相关的物理节点（Allocator, Reclaimer 等）连接观测线，导致我们无法观察到死锁发生的确切环节。

### 用户需求
为 `test_resource_contention.py` 中所有资源相关的 IC 函数（`allocator`, `reclaimer` 等）包裹一层日志记录，使其在执行前后打印 `START` 和 `END` 日志，从而暴露死锁的源头。

### 评论
这是一个精准的外科手术式调试。我们不去修改编译器，而是通过一个轻量级的测试工具来增强可观测性。这个 `debug_wrapper` 将把所有物理节点的活动都暴露出来，让死锁问题无处遁形。

### 目标
1.  在 `test_resource_contention.py` 中实现一个 `debug_wrapper` 辅助函数。
2.  使用该 wrapper 包装 `func_map` 中所有的资源管理函数。
3.  保持测试的其他部分不变，重新运行以捕获一份完整的、包含所有物理节点活动的日志。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #concept/observability #scope/test #task/domain/testing #task/object/debugging #task/action/instrument #task/state/continue

---

### Script

#### Acts 1: 在测试中实现并应用 `debug_wrapper`

我们将修改测试文件，加入 `debug_wrapper` 并将其应用到 `func_map` 的构建过程中。这将点亮我们所有的观测盲区。

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
    # Function Map
    func_map = {}
    for node_id in physical_graph.nodes:
        if node_id.endswith(".bleach"): func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"): func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"): func_map[node_id] = mock_worker
        elif "allocator" in node_id: func_map[node_id] = discrete_allocator
        elif "reclaimer" in node_id: func_map[node_id] = discrete_reclaimer
        elif node_id.startswith("req."): func_map[node_id] = resource_requestor
        elif node_id.startswith("probe.const."): func_map[node_id] = const_probe
        elif "observability" in node_id: func_map[node_id] = standard_observer
            
    runner = EventDrivenRunner(physical_graph, func_map)
    runner.prime()
    
    await runner.start_loop()
    
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
~~~~~python.new
    # Function Map and Debug Wrapper
    import functools

    print("\n--- Physical Field Event Log (Manual + Observed) ---")
    
    def debug_wrapper(func, name):
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            print(f"[MAN-START] {name}")
            try:
                result = await func(*args, **kwargs)
                print(f"[MAN-END  ] {name}")
                return result
            except Exception as e:
                print(f"[MAN-ERROR] {name}: {e}")
                raise
        return wrapped

    func_map = {}
    for node_id, node in physical_graph.nodes.items():
        if node_id.endswith(".bleach"): func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"): func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"): func_map[node_id] = mock_worker
        elif "allocator" in node_id: func_map[node_id] = debug_wrapper(discrete_allocator, node.name)
        elif "reclaimer" in node_id: func_map[node_id] = debug_wrapper(discrete_reclaimer, node.name)
        elif node_id.startswith("req."): func_map[node_id] = debug_wrapper(resource_requestor, node.name)
        elif node_id.startswith("probe.const."): func_map[node_id] = debug_wrapper(const_probe, node.name)
        elif "observability" in node_id: func_map[node_id] = standard_observer
            
    runner = EventDrivenRunner(physical_graph, func_map)
    runner.prime()
    
    await runner.start_loop()
    
    try:
        # Collect all 'start' and 'end' events
        events: List[ObservedEvent] = []
        
        # We wait until we have 2 * TASK_COUNT logical task completions.
        # But we log EVERY physical event to diagnose the deadlock.
        def collection_predicate(e: ObservedEvent):
            # Log ALL physical events for debugging
            node_id = e.trace_data.get("id", "unknown")
            print(f"[OBS-START] {node_id}" if e.event_type == "start" else f"[OBS-END  ] {node_id}")

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
请再次运行这个经过“插桩”的测试。

这次，我们依然期望它会超时失败，但 stdout 中会打印出两种日志：
-   `[OBS-...]`: 来自 `standard_observer` 的、我们已经看到的逻辑任务日志。
-   `[MAN-...]`: 来自我们的 `debug_wrapper` 的、关键的资源节点手动日志。

请将包含这两种日志的完整输出提供给我。通过对比和分析这份混合日志，我们一定能定位到死锁的确切位置和原因。
