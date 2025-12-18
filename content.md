## [WIP] fix: 增强资源感知调度与修复测试

### 错误分析

测试失败揭示了当前调度逻辑的一个微秒但关键的缺陷：**过早调度 (Premature Scheduling)**。

1.  **现象**: 在 `test_runtime_pause_resume_mid_stage` 中，任务 B 尽管因为资源不足（由任务 A 占用）而无法实际运行，但 `Engine` 仍然为它创建了一个 `asyncio.Task`。
2.  **后果**: 一旦任务被创建并进入 `asyncio` 的调度队列，它就脱离了 `Engine` 主循环的 `pending_nodes` 集合。这意味着它不再接受 `check_permission`（即 Pause 检查）的管辖。
3.  **漏洞**: 当任务 A 完成并释放资源时，任务 B（已经在 `asyncio` 层面等待资源锁）会立即获得资源并开始执行，完全绕过了我们在 A 运行期间发出的 Pause 指令。这就是为什么测试断言“B 启动了”尽管我们已经 Pause 了。
4.  **Failure 2**: `test_startup_telemetry_no_race_condition` 失败是因为 `AsyncMock` 替换的方法不再具有 `assert_called` 属性，这是一个简单的测试编写错误。

### 用户需求
1.  修改 `ResourceManager`，公开 `can_acquire` 方法，允许非阻塞地检查资源可用性。
2.  修改 `Engine._execute_graph`，在创建任务之前进行“资源预检”。如果资源不足，应将节点保留在 `pending_nodes` 中，而不是过早地创建会被阻塞的任务。这确保了节点始终处于 `Engine` 的控制之下，能够响应 Pause 等约束。
3.  修复 `test_startup_telemetry_no_race_condition` 中的断言错误。

### 评论
这是一个非常深刻的架构改进。通过推迟任务创建直到资源真正可用，我们实际上将 `Engine` 从一个“发射后不管”的调度器转变为一个“精确即时 (Just-In-Time)”调度器。这不仅修复了 Pause 功能，也提高了系统对高负载的韧性，因为我们不再在 `asyncio` 循环中堆积成千上万个阻塞在资源锁上的协程。

### 目标
1.  更新 `packages/cascade-runtime/src/cascade/runtime/resource_manager.py`。
2.  更新 `packages/cascade-runtime/src/cascade/runtime/engine.py`。
3.  更新 `tests/py/e2e/test_e2e_runtime_control.py`。

### 基本原理
同上分析。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/scheduler #scope/core #ai/instruct #task/domain/runtime #task/object/engine #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 公开 `ResourceManager.can_acquire`

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resource_manager.py
~~~~~
~~~~~python
    def _can_acquire(self, requirements: Dict[str, Union[int, float]]) -> bool:
        """Internal check to see if resources are currently available."""
        for res, amount in requirements.items():
            if res not in self._capacity:
                continue  # Unmanaged resources are always available

            if self._usage[res] + float(amount) > self._capacity[res]:
                return False
        return True
~~~~~
~~~~~python
    def can_acquire(self, requirements: Dict[str, Union[int, float]]) -> bool:
        """Checks if resources are currently available without acquiring them."""
        for res, amount in requirements.items():
            if res not in self._capacity:
                continue  # Unmanaged resources are always available

            if self._usage[res] + float(amount) > self._capacity[res]:
                return False
        return True
~~~~~
~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resource_manager.py
~~~~~
~~~~~python
            while not self._can_acquire(requirements):
                await self._condition.wait()
~~~~~
~~~~~python
            while not self.can_acquire(requirements):
                await self._condition.wait()
~~~~~

#### Acts 2: 在 Engine 中实施资源预检

修改调度循环，在 `create_task` 之前检查资源。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                        coro = self._execute_node_with_policies(
                            node, graph, state_backend, active_resources, run_id, params
                        )
                        task = asyncio.create_task(coro)
                        running_tasks[task] = node.id
                        del pending_nodes[node.id]

                    pending_nodes = deferred_nodes
~~~~~
~~~~~python
                        # Pre-check resources to prevent premature scheduling
                        # This ensures tasks stay in 'pending' (and thus under control of Pause/Permission checks)
                        # until resources are actually available.
                        requirements = self.constraint_resolver.resolve(
                            node, graph, state_backend, self.constraint_manager
                        )
                        
                        if not self.resource_manager.can_acquire(requirements):
                            # Not enough resources yet. Keep it pending.
                            deferred_nodes[node.id] = node
                            continue

                        coro = self._execute_node_with_policies(
                            node, graph, state_backend, active_resources, run_id, params
                        )
                        task = asyncio.create_task(coro)
                        running_tasks[task] = node.id
                        del pending_nodes[node.id]

                    pending_nodes = deferred_nodes
~~~~~

#### Acts 3: 修复测试断言

~~~~~act
patch_file
tests/py/e2e/test_e2e_runtime_control.py
~~~~~
~~~~~python
    # ASSERT
    # We expect 'connect' to be the first call to the connector
    assert call_order[0] == "connect"
    # Followed by a publish (from RunStarted event)
    assert "publish" in call_order
    
    mock_connector.connect.assert_awaited_once()
    # At least one publish should have happened (RunStarted)
    mock_connector.publish.assert_called()
~~~~~
~~~~~python
    # ASSERT
    # We expect 'connect' to be the first call to the connector
    assert call_order[0] == "connect"
    # Followed by a publish (from RunStarted event)
    assert "publish" in call_order
    
    mock_connector.connect.assert_awaited_once()
    # At least one publish should have happened (RunStarted)
    # mock_connector.publish is now a normal function, so we check call_order instead
    assert call_order.count("publish") >= 1
~~~~~

### 下一步建议
运行测试。这次变更从根本上解决了 Pause 时效性的问题，应该能让测试通过。通过后，我们将正式开始 Phase 5 的开发。
