## [WIP] fix(vm): correct reactor step loop and async handling

### 用户需求
1.  修复 `test_reactor_resource_awareness.py` 中的死循环。原因是 `step()` 中的 `while` 循环条件过于宽泛，导致在资源不足时无限轮询待处理任务。
2.  修复 `test_reactor_loop.py` 中的断言失败。原因是 `step()` 中移除了 `await asyncio.gather(...)`，导致任务提交变成“发后不理”，测试在任务实际提交前就执行了断言。

### 评论
这是对 `Reactor` 核心微循环逻辑的纠正。`step()` 必须是**有界**的：它应该处理当前的状态变更直到稳定，但不应在无法取得进展（例如资源阻塞）时空转。同时，`_fire` 操作必须被 `await` 以保证确定性，这对于测试和因果一致性至关重要。

### 目标
修改 `packages/cascade-vm/src/cascade/vm/reactor/core.py`：
1.  恢复 `await asyncio.gather`。
2.  优化 `step` 的微循环终止条件：只有在发生了实质性进展（处理了事件 或 激发了任务）时才继续循环，否则退出以避免忙等待。

### 基本原理
微循环 (`micro-loop`) 的定义是：在一个逻辑时间步内，处理所有的因果连锁反应。
-   **终止条件**: 当一轮循环既没有处理任何事件，也没有激发任何新任务时，说明系统已达到当前时间步的稳定态（Stable State），或者是被资源/数据阻塞。此时应立即返回。
-   **同步性**: `step()` 是一个原子操作，它承诺在返回时，所有由当前状态触发的直接副作用（如提交给 Executor）都已经发生。因此必须 `await` 提交动作。

### 标签
#intent/fix #flow/draft #priority/critical #comp/runtime #concept/executor #scope/core #ai/refine #task/domain/runtime #task/object/reactor #task/action/fix

---

### Script

#### Acts 1: 修复 Reactor.step

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
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
~~~~~python.new
    async def step(self):
        """
        Advance the reactor by one atomic "tick".
        
        A tick is a full reaction to the current state, processing all immediately
        available events and firing all ready nodes until no more immediate work
        can be done. It does not wait for long-running tasks to complete.
        """
        while True:
            progress_made = False
            
            # 1. Process all pending events
            if self._event_queue:
                while self._event_queue:
                    event = self._event_queue.popleft()
                    await self._handle_event(event)
                progress_made = True

            # 2. Evaluate Candidates
            # Candidates are newly dirty nodes + any previously pending nodes
            # We include pending nodes because an event (e.g. resource release) might have unblocked them.
            candidates = self._dirty_func_nodes.union(self._pending_on_resource)
            
            # Reset sets for this iteration. 
            # Nodes that fail to fire will be added back to _pending_on_resource.
            self._dirty_func_nodes.clear()
            self._pending_on_resource.clear()

            if not candidates:
                if not progress_made:
                    # Stable state reached: No events processed, no candidates to check.
                    break
                else:
                    # Events were processed, loop again to check if they triggered anything new
                    continue

            fire_tasks = []
            
            for node in candidates:
                if not node.is_ready():
                    continue
                    
                # Resource Check (Potential Barrier)
                can_fire = True
                if self.resource_manager and node.resource_requirements:
                    if self.resource_manager.can_acquire(node.resource_requirements):
                        await self.resource_manager.acquire(node.resource_requirements)
                    else:
                        can_fire = False
                        # Resource barrier not met, keep it pending.
                        self._pending_on_resource.add(node)
                
                if can_fire:
                    fire_tasks.append(self._fire(node))

            if fire_tasks:
                # Await submission to ensure deterministic behavior (e.g. for testing mocks).
                # This does NOT wait for the task itself to finish, just for the submission to the executor.
                await asyncio.gather(*fire_tasks)
                progress_made = True
            
            # Termination Condition:
            # If we processed candidates but fired nothing (all blocked), and processed no events,
            # we are in a resource-constrained block or stable state. Stop stepping to avoid busy loop.
            if not progress_made:
                break
~~~~~

### 下一步建议
修复已经应用。
1.  **运行测试**: 重新运行所有 reactor 相关的测试，特别是 `test_reactor_resource_awareness.py` 和 `test_reactor_loop.py`。
2.  **验证**:
    *   死循环应该消失，`test_reactor_resource_awareness` 应该 PASS。
    *   断言失败应该消失，`test_reactor_loop` 应该 PASS。
3.  **继续**: 如果一切变绿，我们可以继续实现 `run()` 方法来修复处于 RED 状态的 `test_reactor_wakeup_mechanism.py`。
