好的，我来分析一下。

你的分析非常敏锐，直接指向了问题的核心：**是的，我们的测试编写方式有误，但这个错误恰好暴露了 Reactor 设计中一个更深层次的战略性缺陷。**

## [WIP] fix(vm): Correct intrinsic node resource lifecycle

### 错误分析

我们遇到了两个层面的问题：

1.  **战术层面：测试代码中的 `CancelledError` 处理不当**
    *   `asyncio.wait_for(task, timeout)` 的工作机制是：当超时发生时，它会**取消 (cancel)** 传入的 `task`，然后抛出 `asyncio.TimeoutError`。
    *   我们的测试在 `except asyncio.TimeoutError:` 块中捕获了这个异常，然后尝试 `await run_task`。
    *   此时 `run_task` 已经被 `wait_for` 取消了。`await` 一个已取消的任务会立即再次抛出 `asyncio.CancelledError`，这正是我们看到的最终错误。这是一个测试逻辑上的 bug。

2.  **战略层面：内在节点（Intrinsic Node）的资源生命周期管理存在死锁**
    *   **更根本的问题是：为什么会超时？** 测试本应在 `TerminatorNode` 激发后正常结束。超时意味着 `TerminatorNode` 从未被激发。
    *   **原因追溯**:
        1.  在测试中，`EmitterNode` 和 `TerminatorNode` 都需要 1 个 `"slot"` 资源，而系统总共只有 1 个 `"slot"`。
        2.  当 `d_in` 收到令牌后，`EmitterNode` 和 `TerminatorNode` 都变成了就绪状态（`is_ready()`）。
        3.  由于 `set` 的无序性，Reactor 在处理候选节点时，**可能会先处理 `EmitterNode`**。
        4.  `EmitterNode` **成功获取**了唯一的 `"slot"` 资源。
        5.  `_fire` 方法被调用，它识别出 `EmitterNode` 是一个“内在节点”，**同步地**调用了 sink，然后返回。
        6.  **核心缺陷**：`_fire` 方法没有释放它刚刚占用的资源！资源的释放逻辑被设计在 `_handle_execution_finished` 中，它依赖一个由 `Executor` 异步发回的 `ExecutionFinished` 事件。但内在节点永远不会被交给 `Executor`，因此这个事件永远不会发生。
        7.  `TerminatorNode` 现在尝试获取资源，但唯一的 `"slot"` 被 `EmitterNode` 永久占用，导致 `TerminatorNode` 永远处于等待状态，造成死锁，最终导致测试超时。

### 用户需求
修复内在节点（`EmitterNode`, `TerminatorNode`）的资源管理逻辑，确保其资源生命周期是同步的，并修正测试中的异常处理。

### 评论
这个 bug 是一个绝佳的例子，说明了为什么 TDD 如此重要。一个看似简单的测试失败，揭示了系统物理模型中关于“同步”与“异步”交互的根本性矛盾。修复这个问题将使 Reactor 的资源管理更加健壮和可预测。

### 目标
1.  在 `Reactor.step` 循环中，为内在节点（`EmitterNode`, `TerminatorNode`）实现同步的“获取-执行-释放”资源模式。
2.  修复 `test_result_emission.py` 中对 `CancelledError` 的处理。

### 基本原理
我们将修改 `Reactor.step` 的主循环。当一个就绪的节点被识别为内在节点时，我们将不再把它放入待提交列表，而是立即在一个 `try...finally` 块中执行它：获取资源，调用 `_fire`，然后在 `finally` 中释放资源。这确保了内在节点的资源生命周期与其同步执行的特性保持一致。

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #concept/lifecycle #concept/resource #task/domain/runtime #task/object/reactor #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 Reactor 中内在节点的资源死锁

修改 `Reactor.step` 方法，为内在节点实现同步的资源释放逻辑。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
            fire_tasks = []
            
            for node in candidates:
                if not node.is_ready():
                    continue
                
                # Intrinsic nodes have a synchronous resource lifecycle
                if isinstance(node, (TerminatorNode, EmitterNode)):
                    can_fire_intrinsic = True
                    if self.resource_manager and node.resource_requirements:
                        if not self.resource_manager.can_acquire(node.resource_requirements):
                            can_fire_intrinsic = False
                            self._pending_on_resource.add(node)
                    
                    if can_fire_intrinsic:
                        # Synchronous Acquire-Fire-Release
                        try:
                            if self.resource_manager and node.resource_requirements:
                                await self.resource_manager.acquire(node.resource_requirements)
                            # _fire for intrinsics is sync and fast
                            await self._fire(node)
                            progress_made = True
                        finally:
                            if self.resource_manager and node.resource_requirements:
                                await self.resource_manager.release(node.resource_requirements)
                    continue

                # Standard async nodes
                can_fire_async = True
                if self.resource_manager and node.resource_requirements:
                    if self.resource_manager.can_acquire(node.resource_requirements):
                        await self.resource_manager.acquire(node.resource_requirements)
                    else:
                        can_fire_async = False
                        # Resource barrier not met, keep it pending.
                        self._pending_on_resource.add(node)
                
                if can_fire_async:
                    fire_tasks.append(self._fire(node))

            if fire_tasks:
                # Await submission to ensure deterministic behavior (e.g. for testing mocks).
                # This does NOT wait for the task itself to finish, just for the submission to the executor.
                await asyncio.gather(*fire_tasks)
                progress_made = True
~~~~~

#### Acts 2: 修复测试中的异常处理

更新 `test_result_emission.py` 以正确处理超时场景，并使断言逻辑更清晰。

~~~~~act
patch_file
packages/cascade-vm/tests/reactor/test_result_emission.py
~~~~~
~~~~~python.old
    # 5. Wait for completion
    try:
        # Wait for reactor to stop (triggered by Terminator)
        await asyncio.wait_for(run_task, timeout=1.0)
    except asyncio.TimeoutError:
        reactor.stop()
        await run_task
        # If it timed out, it means Terminator didn't fire, which is a separate issue 
        # (or resource contention). But here we assume Terminator works (Phase 5.1).
    
    # 6. Verify Result
    # This is the core assertion. Did the sink receive the data?
    try:
        result = result_future.result()
        assert result == "Hello World"
    except asyncio.InvalidStateError:
        pytest.fail("Sink was never called with the result")
~~~~~
~~~~~python.new
    # 5. Wait for completion
    try:
        # Wait for reactor to stop (triggered by Terminator)
        await asyncio.wait_for(run_task, timeout=1.0)
    except asyncio.TimeoutError:
        # The test failed because the reactor didn't stop in time.
        # The run_task is already cancelled by wait_for.
        reactor.stop()
        try:
            # Awaiting a cancelled task raises CancelledError, we absorb it.
            await run_task
        except asyncio.CancelledError:
            pass
        pytest.fail("Reactor failed to terminate automatically")
    
    # 6. Verify Result
    # This logic now correctly executes for both success and failure paths,
    # but the fail path is handled by pytest.fail above.
    assert result_future.done(), "Future was not resolved"
    assert result_future.result() == "Hello World"
~~~~~

### 下一步建议
我们已经修复了内在节点的资源死锁问题。现在 Reactor 的核心物理模型更加稳固。我们可以安全地进入 **阶段 5.3**，将 `TerminatorNode` 和 `EmitterNode` 集成到 `VMExecutionStrategy` 中，完成从“外部控制”到“内部自治”的架构转型。
