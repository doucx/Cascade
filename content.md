## [WIP] fix: 增加 MockExecutor 执行延迟以消除测试竞争条件

### 错误分析
测试失败的原因是 `MockExecutor` 执行速度过快，导致 `Engine` 在测试代码有机会注入暂停指令之前，就已经完成了任务 A 并进入 Stage 2 启动了任务 B。

具体来说：
1.  `MockExecutor.execute` 是一个立即返回的协程。
2.  虽然测试代码使用了 `wait_for_task_start`，但该函数的轮询间隔（0.01s）可能比 `Engine` 完成 A 并启动 B 的整个过程还要长。
3.  因此，当测试代码醒来准备注入指令时，B 已经在运行了。

由于 `MockExecutor` 的当前实现完全忽略了任务定义的代码（它只返回固定字符串），我们在任务函数中添加 `sleep` 是无效的。必须直接在 `MockExecutor` 中模拟执行耗时。

### 用户需求
修复测试竞争条件，确保在任务 A 执行期间有足够的时间窗口注入暂停指令。

### 评论
在并发测试中，模拟真实的“耗时操作”是协调时序的常用手段。给 Mock 对象添加少量的延迟，可以迫使事件循环进行上下文切换，从而让测试逻辑有机会介入。

### 目标
1.  修改 `tests/py/runtime/test_engine_constraints.py` 中的 `MockExecutor`。
2.  在 `execute` 方法中添加 `await asyncio.sleep(0.05)`。

### 基本原理
通过在执行器层面引入延迟，我们强制 `Engine` 在 `await asyncio.gather(...)` 这一行停留至少 0.05 秒。这为测试主协程（它在等待 A 开始后立即行动）提供了充足的时间窗口，通过 `MockConnector` 注入全局暂停指令。当 `Engine` 从 `gather` 返回并准备进入 Stage 2 时，它将看到更新后的约束状态。

### 标签
#intent/fix #flow/ready #priority/high
#comp/tests #concept/concurrency
#ai/instruct
#task/domain/testing #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 为 MockExecutor 添加延迟

~~~~~act
patch_file
tests/py/runtime/test_engine_constraints.py
~~~~~
~~~~~python
class MockExecutor(Executor):
    async def execute(self, node, args, kwargs):
        return f"Result for {node.name}"
~~~~~
~~~~~python
class MockExecutor(Executor):
    async def execute(self, node, args, kwargs):
        # Simulate execution time to allow test control flow to inject constraints
        # while the engine is "busy" waiting for this task.
        await asyncio.sleep(0.05)
        return f"Result for {node.name}"
~~~~~
