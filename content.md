简要回答
我们进入 Phase 5：清理与验证。

此阶段的目标是确保 VM 策略的健壮性（修复代码发现逻辑中的漏洞）并提升可观测性数据的质量（补充 task_name），最后通过端到端的集成测试验证整个系统。

## [WIP] fix(vm): 增强代码发现逻辑与遥测数据质量 (Phase 5)

### 用户需求
1.  **修复 VM 代码注册漏洞**: `VMExecutionStrategy` 目前仅通过遍历 `args/kwargs` 收集 `LazyResult`，这会导致作为 `condition` 或 `dependency` 存在的任务代码未被注册，导致运行时 crash。需要修复遍历逻辑。
2.  **增强遥测语义**: 标准库中的 `bleacher` 和 `stainer` 目前生成的 `EventIR` 缺少 `task_name`，导致日志中显示 `task_name=unknown`。需要从物理节点名称中提取并填充此字段。
3.  **E2E 验证**: 创建 `test_vm_strategy_e2e.py`，验证从 `Engine.run(use_vm=True)` 到 `HumanReadableLogSubscriber` 的完整链路，确保 `run_id` 和 `task_name` 正确传递。

### 评论
这是迈向生产就绪的关键一步。修复代码发现逻辑是保证复杂图（带条件分支）能运行的前提。完善遥测数据则是“全息投影”承诺的最后一块拼图。

### 目标
1.  修改 `cascade/runtime/strategies/vm.py` 中的 `_collect_lazy_results` 方法，使其能够递归收集 `_condition`, `_dependencies` 等隐式依赖。
2.  修改 `cascade/std/triad/bleacher.py` 和 `stainer.py`，将 `node.name`（去除了物理后缀的逻辑名）填入 `EventIR`。
3.  创建集成测试。

### 基本原理
-   **全量遍历**: `LazyResult` 构成的逻辑图不仅包含数据流（args），还包含控制流（condition, deps）。代码注册必须覆盖所有可达节点。
-   **物理名映射**: `Expander` 生成的物理节点名为 `Bleach(TaskName)`。我们可以简单解析此名称或直接使用它作为 `task_name` 的近似值，以便于人类阅读。

### 标签
#intent/fix #intent/test #flow/ready #priority/high #comp/vm #comp/std #comp/engine #concept/observability #task/domain/core #task/object/vm-strategy #task/action/cleanup #task/state/continue

---

### Script

#### Acts 1: 修复 VM 策略的代码收集逻辑

我们将增强 `_collect_lazy_results` 以支持所有类型的依赖关系。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
    def _collect_lazy_results(self, target: Any) -> Dict[str, Any]:
        results = {}
        if isinstance(target, (LazyResult, MappedLazyResult)):
            results[target._uuid] = target
            for arg in target.args:
                results.update(self._collect_lazy_results(arg))
            for k, v in target.kwargs.items():
                results.update(self._collect_lazy_results(v))
        elif isinstance(target, (list, tuple)):
            for item in target:
                results.update(self._collect_lazy_results(item))
        elif isinstance(target, dict):
            for v in target.values():
                results.update(self._collect_lazy_results(v))
        return results
~~~~~
~~~~~python.new
    def _collect_lazy_results(self, target: Any) -> Dict[str, Any]:
        # Use a visited set to handle cycles (though LR graph should be DAG) and avoid redundant work
        results = {}
        self._visit(target, results, set())
        return results

    def _visit(self, obj: Any, results: Dict[str, Any], visited: set) -> None:
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            if obj._uuid in visited:
                return
            visited.add(obj._uuid)
            results[obj._uuid] = obj

            # 1. Data Dependencies (Args/Kwargs)
            if hasattr(obj, "args"):
                for arg in obj.args:
                    self._visit(arg, results, visited)
            if hasattr(obj, "kwargs"):
                for v in obj.kwargs.values():
                    self._visit(v, results, visited)
            if hasattr(obj, "mapping_kwargs"):
                for v in obj.mapping_kwargs.values():
                    self._visit(v, results, visited)

            # 2. Control Dependencies
            if obj._condition:
                self._visit(obj._condition, results, visited)
            
            for dep in obj._dependencies:
                self._visit(dep, results, visited)

            # 3. Constraint Dependencies (Dynamic resource amounts)
            if obj._constraints:
                for req in obj._constraints.requirements.values():
                    self._visit(req, results, visited)

            # 4. Jump/Router Dependencies (Recursion/Branching)
            if hasattr(obj, "_jump_selector") and obj._jump_selector:
                selector = obj._jump_selector
                for route_lr in selector.routes.values():
                    if route_lr:
                        self._visit(route_lr, results, visited)

        elif isinstance(obj, (list, tuple)):
            for item in obj:
                self._visit(item, results, visited)
        elif isinstance(obj, dict):
            for v in obj.values():
                self._visit(v, results, visited)
~~~~~

#### Acts 2: 增强标准库的遥测数据

我们在 `EventIR` 中填充 `task_name`。物理节点的 `name` 属性通常形如 `Bleach(MyTask)`。为了更好的阅读体验，我们保留这个名称，因为它准确描述了物理执行的阶段。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": start_ts,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": EventState.RUNNING,
            "task_id": logical_id,
            # We don't have task_name easily here yet, will address in Phase 4
        },
    }
~~~~~
~~~~~python.new
    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": start_ts,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": EventState.RUNNING,
            "task_id": logical_id,
            "task_name": node.name,  # e.g., "Bleach(MyTask)"
        },
    }
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": now_wall,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": state,
            "task_id": logical_id,
            "duration_ms": duration * 1000,
            "error": error_msg,
            "result_preview": str(result_payload)[:100]
            if state == EventState.SUCCEEDED
            else None,
        },
    }
~~~~~
~~~~~python.new
    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": now_wall,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": state,
            "task_id": logical_id,
            "task_name": node.name,  # e.g., "Stain(MyTask)"
            "duration_ms": duration * 1000,
            "error": error_msg,
            "result_preview": str(result_payload)[:100]
            if state == EventState.SUCCEEDED
            else None,
        },
    }
~~~~~

#### Acts 3: 创建 E2E 验证测试

我们创建一个包含 `Engine`, `VM`, `Subscriber` 的完整测试。

~~~~~act
write_file
packages/cascade-engine/tests/integration/test_vm_strategy_e2e.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
from cascade.sdk import task
from cascade.engine import Engine, EventBus, HumanReadableLogSubscriber
from cascade.spec.protocols import Executor, Solver
from cascade.runtime.events import TaskExecutionFinished

# Mocks to satisfy Engine constructor
class MockSolver(Solver):
    def resolve(self, graph): return []

class MockExecutor(Executor):
    async def execute(self, node, func, args, kwargs): return None

@pytest.mark.asyncio
async def test_vm_strategy_e2e_observability():
    """
    Verifies that running a task via VMExecutionStrategy correctly:
    1. Propagates run_id from Engine -> VM -> Tokens -> Events.
    2. Emits Rich Events (TaskExecutionFinished) to the EventBus.
    3. Allows HumanReadableLogSubscriber to consume these events.
    """
    
    # 1. Setup Logic
    @task
    def hello(name: str) -> str:
        return f"Hello, {name}!"

    workflow = hello("World")

    # 2. Setup Engine Infrastructure
    bus = EventBus()
    
    # We use a spy to intercept what HumanReadableLogSubscriber would see
    # and also verify what the bus receives.
    captured_events = []
    def spy_subscriber(event):
        captured_events.append(event)
    
    bus.subscribe(TaskExecutionFinished, spy_subscriber)

    # Initialize Engine (Strategy selection happens inside run())
    engine = Engine(
        solver=MockSolver(),
        executor=MockExecutor(),
        bus=bus
    )

    # 3. Execute with VM Backend
    result = await engine.run(workflow, use_vm=True)

    # 4. Assertions
    assert result == "Hello, World!"
    
    # Filter for the stainer completion event (which maps to TaskExecutionFinished)
    finish_events = [e for e in captured_events if isinstance(e, TaskExecutionFinished)]
    assert len(finish_events) > 0, "No TaskExecutionFinished events captured"

    event = finish_events[0]
    
    # Context Propagation
    assert event.run_id is not None
    assert len(event.run_id) > 0
    
    # Task Name (Telemetry Quality)
    # The Stainer emits "Stain(hello)", which should be present
    assert "Stain(hello)" in event.task_name or "hello" in event.task_name
    
    # Status
    assert event.status == "Succeeded"
    assert event.result_preview is not None
    assert "Hello, World!" in event.result_preview

    print("\nE2E VM Test Passed: Context and Content propagated successfully.")
~~~~~

### 下一步建议
运行测试。如果通过，我们将拥有一个功能完备、逻辑自洽且高度可观测的物理引擎。
之后，我们可以创建一个 [COMMIT] 计划来固化 Phase 5 的成果。
