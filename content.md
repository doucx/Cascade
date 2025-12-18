## [WIP] fix: 修复目标名称解析并校正 E2E 测试逻辑

### 错误分析

1.  **无效的修复 (Invalid Fix)**: 上一个计划尝试修复 `MappedLazyResult` 的目标名称解析错误，但修改了错误的文件 (`cascade-py/src/cascade/__init__.py`)。正如你指出的，该逻辑实际上位于 `packages/cascade-runtime/src/cascade/runtime/engine.py` 中。这是一个由于代码迁移记忆偏差导致的低级错误。

2.  **测试失败: `test_runtime_pause_resume_mid_stage`**:
    *   **原因**: 测试用例假设两个并行任务（A 和 B）在同一阶段会有时间差启动。然而，`Engine` 的调度器是“贪婪”的，在没有资源限制的情况下，它会在一次循环迭代中将所有符合条件的任务提交给 `asyncio.gather`。因此，当我们发出 `pause` 指令时，任务 B 已经被提交执行了。
    *   **解决方案**: 必须引入资源限制（例如 `slots=1`），强制并行任务串行化执行。这样，任务 B 就会在任务 A 执行期间停留在待处理队列中，从而给 `pause` 指令生效的时间窗口。

3.  **测试失败: `test_startup_telemetry_no_race_condition`**:
    *   **原因**: 测试手动实例化了 `Engine`，但**忘记实例化 `TelemetrySubscriber`**。`TelemetrySubscriber` 是负责监听 `RunStarted` 并调用 `connector.publish` 的组件。在 `cascade.run()` 帮助函数中它会被自动创建，但在手动组装 `Engine` 的测试中必须显式创建。

### 用户需求
1.  在正确的文件 (`engine.py`) 中应用目标名称解析的修复。
2.  重写 `test_runtime_pause_resume_mid_stage`，利用资源限制来创造可测试的暂停时机。
3.  修复 `test_startup_telemetry_no_race_condition`，确保 `TelemetrySubscriber` 被正确连接。

### 评论
这次修复将解决代码中的实际 bug 和测试代码中的逻辑缺陷。通过引入资源限制来测试暂停功能，我们实际上模拟了一个更真实的生产场景（即系统在负载下运行，此时进行干预）。

### 目标
1.  修正 `packages/cascade-runtime/src/cascade/runtime/engine.py` 中的目标解析逻辑。
2.  更新 `tests/py/e2e/test_e2e_runtime_control.py`，修正两个失败的测试用例。

### 基本原理
同上分析。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/runtime #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/e2e-tests #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 在正确的文件中修复目标名称解析

这是之前应用错误位置的修复，现在应用到 `engine.py`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        # Robustly determine target name
        if hasattr(target, "task"):
            target_name = getattr(target.task, "name", "unknown")
        elif hasattr(target, "factory"):
            target_name = f"map({getattr(target.factory, 'name', 'unknown')})"
        else:
            target_name = "unknown"

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
~~~~~python
        # Robustly determine target name
        target_names = []
        if isinstance(target, (list, tuple)):
            for t in target:
                if hasattr(t, "task"):
                    target_names.append(getattr(t.task, "name", "unknown"))
                elif hasattr(t, "factory"):
                    target_names.append(f"map({getattr(t.factory, 'name', 'unknown')})")
                else:
                    target_names.append("unknown")
        elif hasattr(target, "task"):
            target_names.append(getattr(target.task, "name", "unknown"))
        elif hasattr(target, "factory"):
            target_names.append(f"map({getattr(target.factory, 'name', 'unknown')})")
        else:
            target_names.append("unknown")

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
                RunStarted(run_id=run_id, target_tasks=target_names, params=params or {})
            )
~~~~~

#### Acts 2: 修复 E2E 测试逻辑

我们将完全重写 `tests/py/e2e/test_e2e_runtime_control.py`，引入正确的资源限制逻辑和 Subscriber 初始化。

~~~~~act
write_file
tests/py/e2e/test_e2e_runtime_control.py
~~~~~
~~~~~python
import asyncio
import pytest
from unittest.mock import AsyncMock

import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.subscribers import TelemetrySubscriber
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.events import TaskExecutionStarted

from .harness import InProcessConnector, ControllerTestApp


@pytest.mark.asyncio
async def test_runtime_pause_resume_mid_stage(bus_and_spy):
    """
    Validates that the engine can be paused and resumed while a stage is in-flight.
    We use resource limits to force sequential execution of parallel tasks,
    creating a window to inject the pause command.
    """
    bus, spy = bus_and_spy
    connector = InProcessConnector()
    controller = ControllerTestApp(connector)

    first_task_started = asyncio.Event()

    @cs.task
    async def long_task(name: str):
        if name == "A":
            first_task_started.set()
            # Task A takes some time to finish, holding the resource
            await asyncio.sleep(0.1)
        return f"Done {name}"

    # Two tasks that COULD run in parallel, but will be limited by resources
    # We require 'slots=1', and system will have 'slots=1'
    task_a = long_task("A").with_constraints(slots=1)
    task_b = long_task("B").with_constraints(slots=1)

    @cs.task
    def gather(a, b):
        return [a, b]

    workflow = gather(task_a, task_b)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=connector,
        system_resources={"slots": 1} # Force serial execution
    )

    # Start the engine in the background
    engine_run_task = asyncio.create_task(engine.run(workflow))

    # 1. Wait until the first task (A) starts
    await asyncio.wait_for(first_task_started.wait(), timeout=1)

    # 2. Issue a PAUSE command while A is running. 
    # Because B is waiting for the 'slot', it is still in the pending queue.
    await controller.pause(scope="global")
    
    # 3. Wait enough time for A to finish and release the resource.
    # Normally B would start now, but PAUSE should prevent it.
    await asyncio.sleep(0.2)

    # 4. ASSERT: Only A should have started. B should be blocked by PAUSE.
    started_events = spy.events_of_type(TaskExecutionStarted)
    # Note: Depending on timing, gather might not have started, or long_task A started.
    # We filter for 'long_task'.
    long_task_starts = [e for e in started_events if e.task_name == "long_task"]
    assert len(long_task_starts) == 1, "Task B started despite pause!"
    assert long_task_starts[0].task_id == task_a._uuid

    # 5. Issue a RESUME command
    await controller.resume(scope="global")

    # 6. ASSERT: The workflow now completes
    final_result = await asyncio.wait_for(engine_run_task, timeout=1)
    assert sorted(final_result) == ["Done A", "Done B"]

    # Verify that B eventually ran
    started_events = spy.events_of_type(TaskExecutionStarted)
    long_task_starts = [e for e in started_events if e.task_name == "long_task"]
    assert len(long_task_starts) == 2


@pytest.mark.asyncio
async def test_startup_telemetry_no_race_condition(bus_and_spy):
    """
    Validates that the connector.connect() is called before any attempt
    to publish the RunStarted event, preventing a race condition.
    """
    bus, spy = bus_and_spy

    # Mock the connector to spy on its method calls
    mock_connector = AsyncMock(spec=InProcessConnector)
    
    # Track call order
    call_order = []
    mock_connector.connect.side_effect = lambda: call_order.append("connect")
    
    original_publish = mock_connector.publish
    
    async def patched_publish(*args, **kwargs):
        call_order.append("publish")
        return await original_publish(*args, **kwargs)

    mock_connector.publish = patched_publish

    # Crucial: Must manually attach the subscriber because we are building Engine manually
    TelemetrySubscriber(bus, mock_connector)

    @cs.task
    def simple_task():
        return "ok"
    
    workflow = simple_task()

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=mock_connector,
    )
    
    await engine.run(workflow)

    # ASSERT
    # We expect 'connect' to be the first call to the connector
    assert call_order[0] == "connect"
    # Followed by a publish (from RunStarted event)
    assert "publish" in call_order
    
    mock_connector.connect.assert_awaited_once()
    # At least one publish should have happened (RunStarted)
    mock_connector.publish.assert_called()
~~~~~

### 下一步建议
现在代码和测试应该都正确了。请再次运行测试。如果通过，我们将准备好进入第五阶段的开发。
