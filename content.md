好的，我将创建一个 `[WIP]` 计划，以实现从忙等待 (`asyncio.sleep`) 到基于 `asyncio.Event` 的确定性等待机制的转换。

这是一个至关重要的架构优化，它将显著提升 `Engine` 在任务被约束推迟时的效率和健壮性。

## [WIP] refactor(runtime): 以事件驱动的唤醒机制取代 Engine 中的忙等待

### 用户需求
将 `Engine` 主调度循环中，因任务被约束推迟而产生的 `asyncio.sleep(0.1)` 忙等待，替换为一个高效的、基于 `asyncio.Event` 的精确唤醒机制。

### 评论
当前的忙等待实现是一个典型的反模式。当大量任务被全局约束（如`pause`）阻塞时，它会导致 `Engine` 持续消耗不必要的 CPU 周期进行轮询。

迁移到事件驱动的等待/唤醒模型是一次关键的架构升级。它使得 `Engine` 在没有可执行任务时能够进入真正的“静默”等待状态，只有在可能改变调度决策的外部事件（即约束变更）发生时才被唤醒。这不仅极大地提升了系统效率，也使调度行为更加确定和可靠。

### 目标
1.  在 `Engine` 类中引入一个 `asyncio.Event` 实例 (`_wakeup_event`)，作为调度循环的唤醒信号。
2.  修改 `_execute_graph` 方法中的主循环，当所有待处理任务都被约束阻塞时，使其 `await` 这个 `_wakeup_event`，而不是固定时间的 `sleep`。
3.  增强 `_on_constraint_update` MQTT 回调方法，使其在成功处理任何约束变更（增加或移除）后，调用 `_wakeup_event.set()` 来唤醒可能正在等待的调度循环。

### 基本原理
我们将 `Engine` 的调度模型从**轮询（Polling）**转变为**事件驱动（Event-Driven）**。

`Engine` 的主循环在遇到所有任务都被阻塞的局面时，不再盲目地等待一个固定的时间片，而是 `await` 一个内部的 `asyncio.Event`。这个 `await` 会使其挂起，不消耗任何CPU，直到事件被设置。

唯一能让被阻塞任务变为可执行的外部事件是约束的变更。因此，我们让处理 MQTT 消息的 `_on_constraint_update` 回调函数，在每次成功更新约束状态后，负责调用 `_wakeup_event.set()`。

这就建立了一个清晰的因果链：**约束变更 -> 信号发出 -> 调度器被唤醒 -> 重新评估任务**。这个机制既高效又确定。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/scheduler #task/action/optimization #task/state/begin

---

### Script

#### Acts 1: 在 Engine 中引入唤醒事件

首先，我们在 `Engine` 的 `__init__` 方法中初始化 `asyncio.Event`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(self.resource_manager)
        self.constraint_manager.register_handler(PauseConstraintHandler())
        self.constraint_manager.register_handler(ConcurrencyConstraintHandler())

        self._resource_providers: Dict[str, Callable] = {}
~~~~~
~~~~~python
        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(self.resource_manager)
        self.constraint_manager.register_handler(PauseConstraintHandler())
        self.constraint_manager.register_handler(ConcurrencyConstraintHandler())

        self._wakeup_event = asyncio.Event()

        self._resource_providers: Dict[str, Callable] = {}
~~~~~

#### Acts 2: 实现唤醒信号的触发

接下来，我们修改 MQTT 回调 `_on_constraint_update`，让它在每次约束状态变更后，设置唤醒事件。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        try:
            # Basic validation, could be improved with a schema library
            constraint = GlobalConstraint(
                id=payload["id"],
                scope=payload["scope"],
                type=payload["type"],
                params=payload["params"],
                expires_at=payload.get("expires_at"),
            )
            self.constraint_manager.update_constraint(constraint)
        except (KeyError, TypeError) as e:
            # In a real system, we'd use a proper logger.
            # For now, print to stderr to avoid crashing the engine.
            print(
                f"[Engine] Error processing constraint on topic '{topic}': {e}",
                file=sys.stderr,
            )
~~~~~
~~~~~python
        try:
            # Basic validation, could be improved with a schema library
            constraint = GlobalConstraint(
                id=payload["id"],
                scope=payload["scope"],
                type=payload["type"],
                params=payload["params"],
                expires_at=payload.get("expires_at"),
            )
            self.constraint_manager.update_constraint(constraint)
        except (KeyError, TypeError) as e:
            # In a real system, we'd use a proper logger.
            # For now, print to stderr to avoid crashing the engine.
            print(
                f"[Engine] Error processing constraint on topic '{topic}': {e}",
                file=sys.stderr,
            )
        finally:
            # After any change, wake up the engine loop if it's waiting
            self._wakeup_event.set()
~~~~~

#### Acts 3: 替换忙等待为事件等待

最后，我们将 `_execute_graph` 中的 `asyncio.sleep` 替换为对 `_wakeup_event` 的等待。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
                    # All remaining nodes are blocked by constraints, wait before retrying.
                    await asyncio.sleep(0.1)  # TODO: Make backoff configurable
~~~~~
~~~~~python
                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
                    # All remaining nodes are blocked by constraints. Wait for a wakeup
                    # signal (e.g., from a constraint change) before retrying.
                    await self._wakeup_event.wait()
                    self._wakeup_event.clear()
~~~~~

### 下一步建议
我们已经完成了核心逻辑的重构。下一步至关重要，是为此新机制编写一个**健壮的集成测试**。

这个测试需要：
1.  使用一个 Mock Connector (`InProcessConnector`)。
2.  启动一个工作流，其中包含一个会被初始约束（例如 `pause`）阻塞的任务。
3.  断言该任务**没有**被执行。
4.  通过 Mock Connector 发布一个新的约束（例如 `resume`）。
5.  断言 `Engine` 被唤醒，并且被阻塞的任务现在成功执行了。

这个测试将验证我们的事件驱动机制是正确且可靠的，为后续更复杂的约束实现奠定坚实的基础。如果你同意，我将开始制定这个测试计划。
