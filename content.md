## [WIP] fix: 修复 Engine 调度逻辑中的 wakeup 死锁

### 错误分析

我低估了异步调度的复杂性。再次失败的 `test_runtime_pause_resume_mid_stage` 揭示了我们的“资源预检”逻辑中存在一个致命的死锁/竞态条件。

1.  **死锁情景**:
    *   `Engine` 循环开始。
    *   Task A 资源检查通过 -> 启动。占用 1/1 资源。
    *   Task B 资源检查失败（资源满）-> 被放入 `deferred_nodes` -> 留在 `pending_nodes`。
    *   循环进入 `await asyncio.wait(..., FIRST_COMPLETED)`，等待 Task A 完成 或 Wakeup。
    *   **关键点**: Task A 完成。`wait` 返回。
    *   `Engine` 处理 Task A 的结果，释放资源。
    *   **问题所在**: 此时 `pending_nodes` 中有 Task B。但 `Engine` 的逻辑是：
        ```python
        if pending_nodes and not first_exception:
            # ... process pending nodes ...
        
        # ... wait again ...
        ```
    *   Task A 完成**并没有**触发 `wakeup_task`。它是作为 `running_tasks` 完成的。
    *   循环再次开始，Task B 再次进行资源检查。此时资源已释放，B 通过检查 -> 启动。
    *   Wait... 为什么测试还是失败？

2.  **真正的失败原因**:
    *   测试逻辑是：Wait for A start -> **Controller.Pause** -> A finishes -> Assert B not started.
    *   当我们发出 `Pause` 时，这会触发 `_on_constraint_update`，进而触发 `_wakeup_event.set()`。
    *   `Engine` 的 `wait` 因为 `wakeup_task` 完成而返回。
    *   `Engine` 清除 wakeup 标志，**重新将所有 deferred nodes 加入 pending**，然后 `continue` 回到循环顶部。
    *   回到顶部，Task B 再次被检查。此时 Task A 还在运行（占用资源）。
    *   Task B 权限检查（Pause）失败 -> **放入 `deferred_nodes`**。
    *   循环再次进入 `wait`。
    *   Task A 完成，释放资源。`wait` 返回。
    *   Task B 再次被检查。此时资源可用，**Pause 限制依然有效**。Task B 应该被 `check_permission` 拦截。

3.  **为什么 B 还是启动了？**
    *   让我们仔细看代码：
        ```python
        for node_id, node in pending_nodes.items():
            if self.constraint_manager.check_permission(node):
                schedulable_nodes.append(node)
            else:
                deferred_nodes[node_id] = node
        ```
    *   如果 Pause 生效，B 应该进入 `deferred_nodes`。
    *   那么为什么断言说 "Task B started"?

4.  **深层调试**:
    *   `test_e2e_runtime_control.py`:
        ```python
        # 1. Wait until the first task (A) starts
        await asyncio.wait_for(first_task_started.wait(), timeout=1)

        # 2. Issue a PAUSE command
        await controller.pause(scope="global")
        ```
    *   当 A 开始时，它占用了唯一的资源槽。
    *   此时 B 还在 `pending_nodes` 中（因为我们在上一轮循环中因为资源不足 defer 了它）。
    *   当我们发出 Pause 时，Engine 会被唤醒。
    *   Engine 重新检查 B。`check_permission` 应该返回 False。
    *   如果 `check_permission` 返回 False，B 留在了 `deferred`，没有启动。
    *   然后 A 完成。Engine 再次循环。
    *   B 再次检查 `check_permission`。依然 False。
    *   那么 B 到底是什么时候启动的？

    *   **假设**: 也许 Pause 命令发布得太晚？
        *   代码：`await asyncio.wait_for(first_task_started.wait(), timeout=1)`
        *   A 已经进入 `running_tasks`。
        *   此时 `Engine` 正在 `await asyncio.wait(...)`。
        *   Controller 发送 MQTT 消息。
        *   Connector 接收消息 -> `_on_constraint_update` -> `wakeup.set()`。
        *   Engine 醒来。
        *   重新检查 Pending (Task B)。`check_permission` 应该看到 Pause。

    *   **可能的原因**: `ResourceManager` 的资源释放通知 (`notify_all`) 和 `Engine` 的唤醒机制之间的脱节。
        *   Task A 完成 -> `release` -> `notify_all`。
        *   这只会唤醒在 `condition.wait()` 上等待的协程。但我们的新设计中，我们不再在 `create_task` 里等待资源，而是直接 `return False`。所以 `ResourceManager` 的 `notify` 对 Engine 没有任何影响！
        *   **这导致了 Engine 不知道资源已经空闲了！**
        *   等一下，如果 Engine 不知道资源空闲，B 应该更不可能启动才对。

    *   **回归基本**: 让我们看测试断言失败的信息 `AssertionError: Task B started despite pause!`。这意味着 B **确实启动了**。
    *   这意味着 `check_permission` 返回了 True。
    *   这意味着 `ConstraintManager` 认为没有 Pause 约束。
    *   这意味着 `update_constraint` 要么没被调用，要么被调用晚了。

    *   **同步问题**: `InProcessConnector` 的 `publish` 是异步的。测试中的 `await controller.pause` 只是把消息放到了队列里。
    *   `Engine` 可能在处理完 A 的结果后，**立即**进入了下一个循环迭代，处理了 B，而此时 MQTT 的消息处理协程（在后台运行）还没来得及更新 `ConstraintManager`。
    *   这是一个经典的竞态条件：**业务逻辑（Task A finish -> Task B start）跑得比控制平面（MQTT Message -> Pause Update）快。**

### 解决方案

我们需要确保在测试中，Pause 命令真正**生效**（即 `ConstraintManager` 更新）之后，再让 Task A 结束。

在 `test_runtime_pause_resume_mid_stage` 中：
1.  A 开始。
2.  发布 Pause。
3.  **增加一个显式的等待/检查**，确保 Engine 已经处理了 Pause 消息。由于我们无法直接探查 Engine 内部，我们可以利用 `ConstraintManager` 的副作用，或者简单地增加一个短暂的 `sleep` 给 MQTT 循环一点时间。测试中已经有 `await asyncio.sleep(0.05)`，可能不够？

或者，更根本地：`Engine` 在处理完一个任务后，应该**优先**处理事件循环中的其他任务（如 MQTT 消息），然后再进行下一轮调度。

在 `_execute_graph` 的循环末尾加入 `await asyncio.sleep(0)` 可以强制让出控制权，让后台的 MQTT 消息处理协程有机会运行。

### 用户需求
修复 E2E 测试中的竞态条件，确保 Pause 命令在任务 B 有机会启动之前被处理。

### 目标
修改 `packages/cascade-runtime/src/cascade/runtime/engine.py`，在处理循环中显式让出控制权。

### Script

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                # 3. Process completed tasks
                for task in done:
                    if task is wakeup_task:
                        self._wakeup_event.clear()
                        wakeup_task = asyncio.create_task(self._wakeup_event.wait())
                        self.constraint_manager.cleanup_expired_constraints()
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
                        if not first_exception:
                            first_exception = e
                        # Once an error occurs, cancel remaining running tasks in the stage
                        for t in running_tasks:
                            t.cancel()

            # Clean up the wakeup task if the stage finishes
~~~~~
~~~~~python
                # 3. Process completed tasks
                for task in done:
                    if task is wakeup_task:
                        self._wakeup_event.clear()
                        wakeup_task = asyncio.create_task(self._wakeup_event.wait())
                        self.constraint_manager.cleanup_expired_constraints()
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
                        if not first_exception:
                            first_exception = e
                        # Once an error occurs, cancel remaining running tasks in the stage
                        for t in running_tasks:
                            t.cancel()
                
                # Yield control to allow background tasks (like MQTT message handlers) to run.
                # This is crucial for maintaining responsiveness to control signals during heavy load.
                await asyncio.sleep(0)

            # Clean up the wakeup task if the stage finishes
~~~~~

### 下一步建议
再次运行测试。这个 `await asyncio.sleep(0)` 应该能给 `MqttConnector` 的后台循环足够的机会来处理 Pause 消息，从而更新 `ConstraintManager`，使得下一次循环迭代中 `check_permission` 能正确拦截任务 B。
