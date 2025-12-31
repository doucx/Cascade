你的分析非常出色，这是一个至关重要的设计洞察。你完全正确。

将 `step()` 方法的语义从“执行一个离散步骤”变更为“执行一个完整的运行循环”是错误的设计。这违反了**最小意外原则 (Principle of Least Surprise)**，并损害了该方法在调试和精细控制场景下的核心价值。

1.  **语义清晰性 (Semantic Clarity)**: 你的提议——`step()` 用于单步，`run()` 用于循环——是业界标准且极为清晰的设计模式。
    *   `step()` 就像调试器中的“单步执行”按钮。它执行一个原子性的工作单元，然后将控制权交还给调用者，允许我们检查系统的中间状态。
    *   `run()` 就像“继续执行”按钮。它自主地、持续地驱动系统，直到达到最终状态或被外部中断。

2.  **关注点分离 (Separation of Concerns)**: 你的设计将**状态推进 (State Progression)**的逻辑与**执行循环 (Execution Loop)**的控制分离开来。
    *   `step()` 的职责是：给定当前状态，计算并执行下一个原子性的状态转换。
    *   `run()` 的职责是：只要系统还有工作要做，就持续调用 `step()`。

3.  **可测试性与可调试性 (Testability & Debuggability)**: 保留一个真正的 `step()` 方法对于测试来说是无价之宝。它允许我们编写非常精确的测试，断言在每一次“滴答”后系统的状态都符合预期，就像我们当前的测试文件正在尝试做的那样。

那么，如何在不破坏 `step()` 语义的前提下，让我们的测试通过呢？

关键在于重新定义**“一步 (a step)”**的粒度。一个“原子步骤”不应该仅仅是处理队列中的一个事件，而应该是**处理完当前所有可立即处理的事件，直到系统达到一个暂时的稳定点（即事件队列为空，没有可立即触发的新动作）**。

这引入了一个**“微循环 (micro-loop)”**的概念：

*   `step()` 方法内部应该包含一个微循环，它会持续处理事件队列中的事件，直到队列被清空。这包括处理在处理过程中新产生的事件。
*   这个微循环**不会**等待长时间运行的任务（如 `executor.submit`）。它只处理瞬时完成的状态转换。
*   这样，从外部调用者的视角看，`step()` 仍然是一个单一的、同步性的（在逻辑上）操作：它使系统从一个稳定状态转换到下一个稳定状态。

**这个精炼后的设计完美地满足了所有要求：**
1.  它让 `test_reactor_proactively_wakes_up_on_resource_release` 测试得以通过，因为 `ExecutionFinished` 事件会在同一个 `step()` 调用中被处理。
2.  它保持了 `step()` 作为单步调试工具的语义纯洁性。
3.  它为你提议的、更高级的 `run()` 方法奠定了坚实的基础。未来的 `run()` 方法可以简单地在一个 `while` 循环中调用 `step()` 并处理异步等待。

你的建议是正确的，我们必须采纳。我们将修改 `step()` 方法，使其包含一个处理所有瞬时事件的内部“微循环”，以实现“原子性反应”。

我现在将生成一个计划来实现这个修改，这将使我们的测试套件回到 **GREEN** 状态，同时保持了架构的清晰和优雅。

## [WIP] feat(vm): implement atomic tick in reactor step

### 用户需求
根据设计讨论，修改 `Reactor.step()` 方法，使其能够在一个原子性的“滴答”中处理所有即时事件，包括在处理过程中新生成的事件。

### 评论
这是一个重要的架构精炼。通过在 `step()` 内部引入一个“微循环”，我们确保了 `step()` 的行为是原子性的：它会将系统推进到一个新的稳定状态。这不仅修复了在严格测试中暴露的主动唤醒问题，也为未来实现一个干净的、基于 `step()` 的 `run()` 方法铺平了道路，同时保留了 `step()` 用于调试的价值。

### 目标
1.  在 `Reactor.step()` 方法内部添加一个 `while self._event_queue:` 循环。
2.  将事件处理和节点评估逻辑移入此循环，确保新事件可以被立即处理。

### 基本原理
当前的 `step()` 实现只遍历一次事件队列，然后评估一次 `_dirty_func_nodes`。当一个被执行的任务（通过 `_fire`）立即产生一个 `ExecutionFinished` 事件时，这个新事件要等到下一次外部调用 `step()` 才会被处理。新的实现通过一个内部循环，确保在一个 `step()` 调用返回之前，所有由此产生的、可立即处理的连锁反应都已完成。

### 标签
#intent/refine #flow/draft #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/reactor #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修改 Reactor.step() 实现原子性 Tick

我们将重构 `step()` 方法，将事件处理和节点评估/触发逻辑包裹在一个 `while` 循环中，该循环会一直运行，直到系统达到一个没有即时事件或可触发任务的“静止”状态。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
    async def step(self):
        """
        Advance the reactor by one "tick".
        A tick consists of:
        1. Processing all pending events (State Updates & Routing).
           - This includes cascading events generated during processing.
        2. Evaluating potentials of affected (dirty) nodes.
        3. Firing ready nodes (if resources allow).
        """
        # 1. Process Event Loop
        while self._event_queue:
            event = self._event_queue.popleft()
            await self._handle_event(event)

        # 2. Evaluate Potentials
        # We process both new dirty nodes AND nodes previously pending on resources
        candidates = self._dirty_func_nodes.union(self._pending_on_resource)
        
        # Reset sets for this tick
        self._dirty_func_nodes.clear()
        self._pending_on_resource.clear()

        fire_tasks = []
        
        for node in candidates:
            if not node.is_ready():
                continue
                
            # Resource Check (Potential Barrier)
            if self.resource_manager and node.resource_requirements:
                if self.resource_manager.can_acquire(node.resource_requirements):
                    # Immediate acquisition to prevent over-commitment in this loop
                    # Note: can_acquire is synchronous, but acquire is async.
                    # Since we verified with can_acquire, acquire should not block significantly
                    # unless another process stole resources (unlikely in this single-threaded loop).
                    await self.resource_manager.acquire(node.resource_requirements)
                    fire_tasks.append(self._fire(node))
                else:
                    # Resource barrier not met, keep pending
                    self._pending_on_resource.add(node)
            else:
                # No resource constraints
                fire_tasks.append(self._fire(node))

        if fire_tasks:
            # Concurrently execute all fired nodes
            await asyncio.gather(*fire_tasks)
~~~~~
~~~~~python.new
    async def step(self):
        """
        Advance the reactor by one atomic "tick".
        
        A tick is a full reaction to the current state, processing all immediately
        available events and firing all ready nodes until no more immediate work
        can be done. It does not wait for long-running tasks to complete.
        """
        # The "micro-loop": continues as long as there are events to process
        # or nodes that might become ready.
        while self._event_queue or self._dirty_func_nodes or self._pending_on_resource:
            
            # 1. Process all pending events until the queue is empty.
            # This may add nodes to _dirty_func_nodes or _pending_on_resource.
            while self._event_queue:
                event = self._event_queue.popleft()
                await self._handle_event(event)

            # 2. Evaluate all candidate nodes for firing.
            # Candidates are nodes that became dirty from events, or were previously blocked.
            candidates = self._dirty_func_nodes.union(self._pending_on_resource)
            
            # Reset sets for the next iteration of the micro-loop.
            self._dirty_func_nodes.clear()
            self._pending_on_resource.clear()

            if not candidates:
                # No candidates to check, the tick is stable.
                break

            fire_tasks = []
            
            for node in candidates:
                if not node.is_ready():
                    continue
                    
                # Resource Check (Potential Barrier)
                if self.resource_manager and node.resource_requirements:
                    if self.resource_manager.can_acquire(node.resource_requirements):
                        await self.resource_manager.acquire(node.resource_requirements)
                        fire_tasks.append(self._fire(node))
                    else:
                        # Resource barrier not met, keep it pending for the next tick/step.
                        self._pending_on_resource.add(node)
                else:
                    # No resource constraints, fire away.
                    fire_tasks.append(self._fire(node))

            if fire_tasks:
                # Asynchronously launch all fireable tasks for this iteration.
                # We do not wait for them to complete within the step.
                asyncio.gather(*fire_tasks)
            
            # If no tasks were fired AND the event queue is empty, the system is stable,
            # so the outer while loop will terminate. If tasks were fired, they might
            # immediately push new events, causing the micro-loop to continue.
~~~~~

### 下一步建议
我们已经实现了 `step()` 的原子性 “tick” 逻辑。现在，`test_reactor_proactively_wakes_up_on_resource_release` 应该会通过，因为它模拟的 `ExecutionFinished` 事件会被 `step()` 的内部循环捕获并处理，从而触发第二个任务的调度，所有这些都在同一个 `step()` 调用中完成。

在运行测试确认我们回到 **GREEN** 状态后，我们就可以继续实现 Phase 5，或者根据你的指示，实现一个完整的 `run()` 方法来完成 `Reactor` 的公共 API。
