简要回答
测试失败揭示了 VM 执行策略中的一个**“过早退出 (Premature Exit)”**缺陷。当主任务的 `Stainer` 产生结果并触发 `result_future` 完成时，`VMExecutionStrategy` 立即终止了执行循环。然而，此时 `Stainer` 刚刚将观测令牌放入 `D_life`，负责发送遥测事件的旁路节点 `F_obs` 尚未被调度执行。导致 `TaskExecutionFinished` 事件丢失。

我将修改 `VMExecutionStrategy` 的执行循环，使其采用 **"Run Until Idle" (运行至热寂)** 模式：即使结果已产生，也要继续运行 Reactor，直到系统没有任何活动任务且不再产生新的激发，确保所有旁路逻辑（如遥测）执行完毕。

## [WIP] fix(vm): 实现 Run-Until-Idle 机制以确保遥测事件完整性

### 用户需求
修复 `test_vm_telemetry.py` 失败。确保在 VM 模式下运行工作流时，所有相关的生命周期事件（特别是 `TaskExecutionFinished`）都能被完整发出。

### 评论
这是一个经典的异步系统竞态条件。主业务流（返回结果）和旁路业务流（发送遥测）在物理层是并行的。如果主控逻辑在收到结果后立即“拉闸”，旁路逻辑就会被切断。
修复方案是实施“优雅停机”：收到结果是“准备停机”的信号，但真正的停机必须等待物理场能量耗尽（Idle）。

### 目标
修改 `VMExecutionStrategy.execute` 方法中的主循环，将退出条件从 `result_future.done()` 改为 `result_future.done() AND reactor.is_idle()`。

### 基本原理
在全对称物理场中，Observer 也是一个普通的节点 (`F_obs`)，它受物理定律约束。它需要一个 `Reactor.step()` 周期来从输入槽中摄取 Token 并执行。必须给予 Reactor 足够的周期来处理这些“遗留”的物理反应。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/observability #scope/core #task/domain/runtime #task/object/vm-strategy #task/action/drain

---

### Script

#### Acts 1: 修改 VM 执行策略的主循环

我们将重构 `packages/cascade-engine/src/cascade/runtime/strategies/vm.py` 中的执行循环。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
        # 6. Execution Loop
        # -----------------
        try:
            while not result_future.done():
                fired = await reactor.step()
                if fired == 0 and not result_future.done():
                    # If we stall but haven't got a result, check for errors or deadlocks
                    await asyncio.sleep(0.001)
        except Exception as e:
            # If reactor crashes, we fail the run
            raise e

        return result_future.result()
~~~~~
~~~~~python.new
        # 6. Execution Loop
        # -----------------
        try:
            while True:
                fired = await reactor.step()

                # Exit condition:
                # 1. We have the result (Business Goal Met)
                # 2. No tasks are running (Quiescence)
                # 3. No new tasks fired (Stability)
                # This ensures side-effects like Observability (which run in parallel/sequence)
                # have a chance to complete.
                if result_future.done() and reactor.active_task_count == 0 and fired == 0:
                    break

                if fired == 0:
                    # If we stall (or are draining), yield to loop to let active tasks finish
                    await asyncio.sleep(0.001)
        except Exception as e:
            # If reactor crashes, we fail the run
            raise e

        return result_future.result()
~~~~~

### 下一步建议
再次运行 `test_vm_telemetry.py`。既然“创世注入”和“优雅停机”都已修复，测试应该能够通过，不仅能断言 `run_id` 存在，也能断言所有任务的事件都已发出。
