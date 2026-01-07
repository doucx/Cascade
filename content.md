You are absolutely correct. The test failures indicate that my previous refactoring was incomplete. I failed to update a few crucial test files that were still operating under the old "magic string" contract. My apologies.

The errors are clear:
1.  **`test_telemetry_contract.py`**: The test is creating a `TaskExecutionFinished` event with a raw string `status="Succeeded"`, which breaks the logic in the `TelemetrySubscriber` that now expects an `EventState` enum.
2.  **`test_observability.py`**: The unit tests for the `EventState` enum itself are now outdated, as they still assert against the old lowercase string values.

I will now fix these remaining inconsistencies to finalize the "Concord" proposal.

## [WIP] fix(tests): Finalize EventState enum contract across all tests

### 错误分析

The remaining test failures are due to two specific oversights in the previous refactoring:
1.  The integration test for the `TelemetrySubscriber` (`test_telemetry_contract.py`) was still instantiating `TaskExecutionFinished` with a string literal (`"Succeeded"`), causing the subscriber's type-safe logic to fail.
2.  The unit tests for the `EventState` enum itself (`test_observability.py`) were not updated to reflect the change from lowercase to capitalized string values, leading to direct assertion failures.

### 用户需求

To fully implement the "Enum-First Contract" by correcting all remaining test files that fail due to the new, stricter `EventState` contract.

### 評論

This is the final and necessary step to complete the architectural refactoring. Fixing these last few tests will ensure the entire codebase is internally consistent with the new type-safe contract, making the system more robust and the test suite more reliable.

### 目标

1.  Modify `test_telemetry_contract.py` to use `EventState.SUCCEEDED` when creating the `TaskExecutionFinished` event.
2.  Update the assertions in `test_observability.py` to match the new capitalized values of the `EventState` enum.

### 基本原理

By updating these last few files, we ensure that every part of the system that produces, consumes, or tests event states now adheres to the single source of truth defined by the `EventState` enum. This completes the transition from an implicit, brittle string-based contract to an explicit, robust, type-safe one.

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #concept/state #scope/core #ai/instruct #task/domain/architecture #task/object/event-contracts #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正遥测契约测试 (Fix Telemetry Contract Test)

我将首先修复 `test_telemetry_contract.py`，确保它使用 `EventState` 枚举来创建事件，从而遵守我们设定的新契约。

~~~~~act
patch_file
packages/cascade-cli-observer/tests/integration/test_telemetry_contract.py
~~~~~
~~~~~python.old
from cascade.runtime.services.observability.events import TaskExecutionFinished
from cascade.runtime.services.observability.subscribers import TelemetrySubscriber
~~~~~
~~~~~python.new
import pytest
import asyncio
from unittest.mock import MagicMock

from cascade.runtime.services.observability.events import TaskExecutionFinished
from cascade.runtime.services.observability.subscribers import TelemetrySubscriber
from cascade.cli.observer.app import on_message
from cascade.testing import MockConnector
from cascade.spec import EventState
~~~~~

~~~~~act
patch_file
packages/cascade-cli-observer/tests/integration/test_telemetry_contract.py
~~~~~
~~~~~python.old
    # 2. PRODUCE: Create a runtime event and have the subscriber process it
    event = TaskExecutionFinished(
        run_id="run-contract-test",
        task_id="task-abc",
        task_name="contract_task",
        status="Succeeded",
        duration=0.123,
    )
~~~~~
~~~~~python.new
    # 2. PRODUCE: Create a runtime event and have the subscriber process it
    event = TaskExecutionFinished(
        run_id="run-contract-test",
        task_id="task-abc",
        task_name="contract_task",
        status=EventState.SUCCEEDED,
        duration=0.123,
    )
~~~~~

#### Acts 2: 更新规范单元测试 (Update Spec Unit Tests)

现在，我将更新 `cascade-spec` 中的单元测试，使其断言与 `EventState` 枚举的新值（大写）保持一致。

~~~~~act
patch_file
packages/cascade-spec/tests/unit/test_observability.py
~~~~~
~~~~~python.old
def test_event_state_enums():
    assert EventState.RUNNING == "running"
    assert EventState.FAILED == "failed"
~~~~~
~~~~~python.new
def test_event_state_enums():
    assert EventState.RUNNING == "Running"
    assert EventState.FAILED == "Failed"
~~~~~

~~~~~act
patch_file
packages/cascade-spec/tests/unit/test_observability.py
~~~~~
~~~~~python.old
    assert event["data"]["state"] == "running"
~~~~~
~~~~~python.new
    assert event["data"]["state"] == "Running"
~~~~~

### 下一步建议

所有已知的测试失败都已修正。我们现在已经完成了从生产者 (`stainer`)、中间件 (`events`, `subscribers`) 到消费者 (`tests`) 的端到端契约统一。

我建议立即运行 `pytest`。如果所有测试都通过，请指示我生成一个 `[COMMIT]` 计划，将这个重要的架构改进合并到代码库中。
