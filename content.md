简要回答
我们进入 **Phase 5: 清理与验证**。

首要任务是修正 `VMExecutionStrategy`，使其利用 Phase 4 引入的“创世注入”协议，将 Engine 上下文中的 `run_id` 传递给 Reactor。这填补了 Engine 和 VM 之间的最后一块拼图。随后，我们将通过端到端 (E2E) 测试验证整个系统的可观测性回路。

## [WIP] fix(engine): 在 VM 策略中注入 Run ID 并进行 E2E 验证 (Phase 5)

### 用户需求
1.  **连接上下文**: 修改 `VMExecutionStrategy`，使其在调用 `reactor.prime()` 时，从 `ExecutionContext` 中提取 `run_id` 并作为 `genesis_trace` 注入。
2.  **全链路验证**: 创建或更新 E2E 测试，验证使用 `use_vm=True` 运行 Engine 时，能够产生包含正确 `run_id` 的结构化日志/事件。

### 评论
这是“创世注入”模式在生产环境（Engine）中的落地。在 Phase 4 中我们升级了底层机制（VM/Reactor），现在我们需要升级上层调用者（Engine/Strategy）来利用这一机制。如果不做这一步，VM 运行的任务将丢失 `run_id`，导致遥测数据断裂。

### 目标
1.  修正 `packages/cascade-engine/src/cascade/runtime/strategies/vm.py`。
2.  创建 `packages/cascade-engine/tests/integration/test_vm_strategy_e2e.py` 以验证完整的执行链路。

### 基本原理
`VMExecutionStrategy` 是 Engine 和 VM 之间的适配器。Engine 负责生成 `run_id` 并管理资源，VM 负责执行。通过在 `prime` 阶段注入 `run_id`，我们确保了物理层的执行与逻辑层的会话 ID 绑定，而无需物理层知道 Engine 的存在。

### 标签
#intent/fix #intent/test #flow/ready #priority/high #comp/engine #comp/vm #concept/observability #task/domain/observability #task/object/context-injection #task/action/integration #task/state/begin

---

### Script

#### Acts 1: 修正 VMExecutionStrategy

我们将修改 `vm.py`，从执行上下文中提取 `run_id` 并传递给 `reactor.prime`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
        # Prime the reactor (fill constants, pulses)
        reactor.prime()

        # Result Future
~~~~~
~~~~~python.new
        # Prime the reactor (fill constants, pulses)
        # Genesis Injection: Pass the run_id from context so it propagates to all tokens
        reactor.prime(genesis_trace={"rid": context.run_id})

        # Result Future
~~~~~

#### Acts 2: 创建 E2E 验证测试

我们将创建一个集成测试，模拟用户使用 `Engine` 运行任务的场景，并验证 `MessageBus` 上收到的事件是否完整且正确。

~~~~~act
write_file
packages/cascade-engine/tests/integration/test_vm_strategy_e2e.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
from cascade.spec.task import task
from cascade.engine import Engine
from cascade.runtime.event_bus import EventBus
from cascade.runtime.events import TaskExecutionFinished, RunStarted
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


@task
def hello_task(name: str) -> str:
    return f"Hello, {name}!"


@pytest.mark.asyncio
async def test_vm_strategy_e2e_observability():
    """
    Verifies that running a task via the VM strategy:
    1. Executes correctly.
    2. Emits LifeCycle events (Started, Finished).
    3. Events contain the correct run_id (Context Injection works).
    """
    # 1. Setup Engine components
    bus = EventBus()
    executor = LocalExecutor()
    solver = NativeSolver()
    engine = Engine(solver=solver, executor=executor, bus=bus)

    # 2. Setup Event Spy
    captured_events = []
    bus.subscribe(TaskExecutionFinished, captured_events.append)
    bus.subscribe(RunStarted, captured_events.append)

    # 3. Execute Workflow using VM Strategy
    flow = hello_task("World")
    result = await engine.run(flow, use_vm=True)

    # 4. Verify Result
    assert result == "Hello, World!"

    # 5. Verify Observability
    # Check that we got a RunStarted event
    run_started = next((e for e in captured_events if isinstance(e, RunStarted)), None)
    assert run_started is not None
    run_id = run_started.run_id
    assert run_id is not None

    # Check that we got a TaskExecutionFinished event with the SAME run_id
    task_finished = next((e for e in captured_events if isinstance(e, TaskExecutionFinished)), None)
    assert task_finished is not None
    
    assert task_finished.task_name == "hello_task"
    assert task_finished.status == "Succeeded"
    
    # THE CRITICAL CHECK: Did the run_id propagate from Engine -> VM -> Token -> EventIR -> Bus -> Event?
    assert task_finished.run_id == run_id, \
        f"Context Injection Failed: Expected run_id {run_id}, got {task_finished.run_id}"

    print(f"E2E Verification Passed. Run ID: {run_id}")
~~~~~

### 下一步建议

运行此 E2E 测试。如果通过，即证明我们成功地将旧的、硬编码的追踪逻辑替换为了基于物理原理的、统一的上下文注入机制。

之后，我们可以进行最后的清理工作（如果有剩余的死代码），并更新文档。
