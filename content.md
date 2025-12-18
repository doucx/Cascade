好的，分析收悉。你的观察非常敏锐，这两个现象都指向了我们运行时（`Engine`）核心调度逻辑中的关键缺陷。

根据 `d2-skill-generate-quipu-plan` 流程，我将首先生成一个修复这两个问题的计划，然后在计划的元数据部分提供详尽的根本原因分析。

这是一个非常重要的修复。我将生成一个计划来解决这两个问题。

## [WIP] fix: 修复引擎启动时的遥测竞态问题与运行时约束更新延迟

### 错误分析

你发现的两个问题是独立的，但都非常关键。

#### 现象 1: `Attempted to publish without an active MQTT connection.`

**根本原因：启动时序颠倒导致的竞态条件 (Race Condition)。**

`Engine.run` 方法当前的执行顺序存在逻辑缺陷：

1.  **事件先行**: 方法一开始，就立刻发布了 `RunStarted` 事件。
2.  **订阅者响应**: `TelemetrySubscriber` 立即捕获此事件，并创建一个“即发即忘 (fire-and-forget)”的 `asyncio` 任务来调用 `connector.publish()`。
3.  **连接滞后**: 与此同时，`Engine.run` 方法继续执行，**在发布事件之后**，才调用 `await self.connector.connect()`。
4.  **竞态发生**: `asyncio` 的事件循环调度器很可能在 `connect()` 方法完成并建立 MQTT 客户端 (`self._client`) 之前，就执行了那个“即发即忘”的 `publish` 任务。
5.  **结果**: `MqttConnector.publish` 方法在执行时发现 `self._client` 仍然是 `None`，因此打印出你看到的警告。稍后，`connect()` 完成，后续的事件（如 `TaskExecutionStarted`）就能被正常发布了。这完美解释了为何只有启动时的第一个事件出现警告，而后续一切正常。

#### 现象 2: 执行中途无法感知 MQTT 约束变化

**根本原因：引擎的“批处理”调度模型使其在任务执行期间处于阻塞状态。**

这并非设计疏忽，而是当前调度循环实现方式的一个严重缺陷。

1.  **调度决策**: `Engine._execute_graph` 的主循环会遍历一个阶段（stage）中所有待处理的任务。它会检查每个任务的权限 (`constraint_manager.check_permission`)，将所有**当前可执行**的任务收集到一个列表（`executable_this_pass`）中。
2.  **长期阻塞**: 然后，引擎调用 `await asyncio.gather(*tasks_to_run)` 来并发执行这个列表中的**所有**任务。关键在于，`gather` 是一个阻塞操作，它会一直等待，直到这个批次中的**所有任务全部完成**。
3.  **错过信号**: 如果在 `gather` 等待期间（可能持续数秒或数分钟），你通过 MQTT 发布了一个新的 `pause` 约束，`Engine` 的 `_on_constraint_update` 回调确实会被事件循环触发，`ConstraintManager` 的状态也确实更新了。但是，`Engine` 的主协程正“卡在” `await asyncio.gather(...)` 这一行，它无法响应这个变化，也无法检查新的约束，直到当前整个批次的任务都结束后才能继续向下执行。
4.  **有限的唤醒逻辑**: 你可能注意到了代码中的 `await self._wakeup_event.wait()`。但这行代码只有在一个非常特定的条件下才会执行：**当一个批次中没有任何任务可以执行时**。它无法中断一个正在执行中的批次。

**结论**: 当前的引擎是一个“批处理调度器”，而非“实时响应调度器”。它在一个批次开始时做出所有决策，然后就“蒙眼狂奔”，直到批次结束，这导致了你观察到的运行时响应延迟。

### 用户需求
1.  修复 `Engine` 启动时的竞态条件，确保 `connector.connect()` 总是在任何可能触发 `publish` 的事件之前完成。
2.  重构 `Engine` 的核心调度循环，使其能够近乎实时地响应运行期间的外部约束变化，而不是等待当前批次的所有任务都完成后才响应。

### 评论
这是对 Cascade 核心引擎稳定性和响应能力的一次关键修复。现象 1 是一个典型的异步编程错误，必须修复。现象 2 则暴露了我们调度模型的根本性弱点，修复它将使 Cascade 真正成为一个动态的、可控制的自适应执行环境，完全兑现我们在路线图第三阶段的承诺。

### 目标
1.  调整 `Engine.run` 方法的启动顺序，将 `connector.connect()` 的调用提前到 `RunStarted` 事件发布之前。
2.  修改 `Engine._execute_graph` 的执行逻辑，将 `asyncio.gather` 替换为一个更具响应性的循环机制，该机制能在单个任务完成后立即重新评估待处理任务的约束，从而对外部变化做出快速反应。

### 基本原理
1.  **修复竞态问题**: 通过简单的代码顺序调整，我们可以从逻辑上保证在任何 `publish` 尝试发生之前，连接都已建立完毕，从而根除此竞态条件。
2.  **修复响应延迟**: 我们将用一个基于 `asyncio.wait()` 和 `FIRST_COMPLETED` 返回条件的循环来取代 `asyncio.gather()`。这将把调度循环从“每批任务一次”的频率提升到“每个任务完成一次”，使引擎能够在单个任务的间隙检查 `_wakeup_event` 并重新评估约束，实现近乎实时的响应能力。

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #concept/executor #scope/core #ai/brainstorm #task/domain/runtime #task/object/engine-lifecycle #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修复启动竞态与调度循环

我们将通过两个 `patch_file` 操作来完成修复。

首先，修复 `Engine.run` 方法中的启动时序问题。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        self.bus.publish(
            RunStarted(run_id=run_id, target_tasks=[target_name], params=params or {})
        )

        state_backend = self.state_backend_cls(run_id=run_id)

        try:
            if self.connector:
                await self.connector.connect()
                self.bus.publish(ConnectorConnected(run_id=run_id))
                # Subscribe to constraint updates
                await self.connector.subscribe(
                    "cascade/constraints/#", self._on_constraint_update
                )
~~~~~
~~~~~python
        state_backend = self.state_backend_cls(run_id=run_id)

        try:
            if self.connector:
                await self.connector.connect()
                self.bus.publish(ConnectorConnected(run_id=run_id))
                # Subscribe to constraint updates
                await self.connector.subscribe(
                    "cascade/constraints/#", self._on_constraint_update
                )

            self.bus.publish(
                RunStarted(run_id=run_id, target_tasks=[target_name], params=params or {})
            )
~~~~~

其次，重构 `_execute_graph` 的核心调度循环，使其具备实时响应能力。这是一个更结构性的变更。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue  # Skip params, they don't execute

                    skip_reason = self.flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        state_backend.mark_skipped(node.id, skip_reason)
                        self.bus.publish(
                            TaskSkipped(
                                run_id=run_id,
                                task_id=node.id,
                                task_name=node.name,
                                reason=skip_reason,
                            )
                        )
                        # Node is resolved (skipped), so not pending for next pass
                        continue

                    if self.constraint_manager.check_permission(node):
                        executable_this_pass.append(node)
                    else:
                        deferred_this_pass.append(node)

                if executable_this_pass:
                    tasks_to_run = [
                        self._execute_node_with_policies(
                            node, graph, state_backend, active_resources, run_id, params
                        )
                        for node in executable_this_pass
                    ]

                    pass_results = await asyncio.gather(*tasks_to_run)

                    for node, res in zip(executable_this_pass, pass_results):
                        state_backend.put_result(node.id, res)
                        if self.flow_manager:
                            self.flow_manager.register_result(
                                node.id, res, state_backend
                            )

                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
                    # All remaining nodes are blocked by constraints. Wait for a wakeup
                    # signal (e.g., from a constraint change or TTL expiration) before retrying.
                    await self._wakeup_event.wait()
                    self._wakeup_event.clear()
                    self.constraint_manager.cleanup_expired_constraints()
~~~~~
~~~~~python
        for stage in plan:
            # Nodes to be processed in the current stage
            pending_nodes = {node.id: node for node in stage}
            # Tasks currently running in asyncio
            running_tasks: Dict[asyncio.Task, str] = {}
            # Wakeup task for constraint changes
            wakeup_task = asyncio.create_task(self._wakeup_event.wait())

            while pending_nodes or running_tasks:
                # 1. Schedule new tasks if possible
                if pending_nodes:
                    # Find nodes whose dependencies are met and are not constrained
                    schedulable_nodes = []
                    deferred_nodes = {}
                    for node_id, node in pending_nodes.items():
                        if self.constraint_manager.check_permission(node):
                            schedulable_nodes.append(node)
                        else:
                            deferred_nodes[node_id] = node

                    for node in schedulable_nodes:
                        # Skip params, they don't execute
                        if node.node_type == "param":
                            del pending_nodes[node.id]
                            continue
                        
                        # Check for skips (run_if, etc.)
                        skip_reason = self.flow_manager.should_skip(node, state_backend)
                        if skip_reason:
                            state_backend.mark_skipped(node.id, skip_reason)
                            self.bus.publish(
                                TaskSkipped(run_id=run_id, task_id=node.id, task_name=node.name, reason=skip_reason)
                            )
                            del pending_nodes[node.id]
                            continue

                        # Create and track the task
                        coro = self._execute_node_with_policies(
                            node, graph, state_backend, active_resources, run_id, params
                        )
                        task = asyncio.create_task(coro)
                        running_tasks[task] = node.id
                        del pending_nodes[node.id]

                    pending_nodes = deferred_nodes

                if not running_tasks and not pending_nodes:
                    break

                # 2. Wait for something to happen
                tasks_to_wait = list(running_tasks.keys()) + [wakeup_task]
                done, pending = await asyncio.wait(
                    tasks_to_wait, return_when=asyncio.FIRST_COMPLETED
                )

                # 3. Process completed tasks
                for task in done:
                    if task is wakeup_task:
                        self._wakeup_event.clear()
                        wakeup_task = asyncio.create_task(self._wakeup_event.wait())
                        self.constraint_manager.cleanup_expired_constraints()
                        # Re-add deferred nodes to pending to re-check permissions
                        for node_id, node in pending_nodes.items():
                             pending_nodes[node_id] = node
                        continue

                    node_id = running_tasks.pop(task)
                    try:
                        result = task.result()
                        state_backend.put_result(node_id, result)
                        if self.flow_manager:
                            self.flow_manager.register_result(
                                node_id, result, state_backend
                            )
                    except Exception as e:
                        # The exception will be re-raised at the end by engine.run()
                        # We just need to stop tracking it.
                        # Error events are already published inside _execute_node...
                        pass
            
            # Clean up the wakeup task if the stage finishes
            if not wakeup_task.done():
                wakeup_task.cancel()
~~~~~

### 下一步建议

我们已经对引擎的核心逻辑进行了重大修改。现在最关键的步骤是为这两个修复创建健壮的、专门的端到端（E2E）回归测试：

1.  **测试竞态条件**: 创建一个测试，在 `Engine` 启动后立即检查 `TelemetrySubscriber` 是否成功发布了 `RunStarted` 事件，而不产生任何警告。
2.  **测试运行时响应**:
    *   创建一个包含多个长时间运行任务（例如，`asyncio.sleep(1)`）的工作流。
    *   在 `Engine` 启动后，但在任务完成前，使用一个模拟的 `Controller` 发布一个 `pause` 约束。
    *   断言引擎能够在新任务开始前暂停执行，并且在收到 `resume` 命令后能继续执行。
    *   这可以借鉴 `tests/py/e2e/test_e2e_control_plane.py` 的模式。

确保这些问题永不复发。如果你同意，我将着手生成这些测试用例的计划。
