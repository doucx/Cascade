Got it. Per your instruction to accelerate, I will combine the creation of tests and the implementation into a single plan. This will deliver a fully functional and tested `standard_stainer` micro-instruction in one step.

## [WIP] feat(vm): Implement standard_stainer instruction and tests

### 用户需求

根据 [Cascade 3.0 重构路线图](Cascade%203.0%20重构路线图：迈向全对称计算物理场.md) 加速完成 **任务 2.2**，在同一步骤中实现标准的 Stainer ($F_{post}$) 微指令及其单元测试。

### 评论

这是对 TDD 流程的合理加速。Stainer 作为执行三连体的最后一环，其职责至关重要：它接收来自 Worker ($F_{exec}$) 的纯净结果和来自 Bleacher ($F_{pre}$) 的追踪元数据，然后“染色”——即将结果包装成一个新的、带有完整上下文（如执行耗时、成功/失败标签）的物理令牌，并将其路由到下游。

### 目标

1.  在 `cascade.vm.instructions` 中创建 `stainer.py` 并包含 `standard_stainer` 的完整实现。
2.  创建 `tests/unit/instructions/test_stainer.py` 并包含覆盖成功、失败和元数据处理场景的测试用例。
3.  确保新编写的实现能够通过所有新编写的测试。

### 基本原理

我们将同时创建 `stainer.py` 和 `test_stainer.py` 两个文件。`standard_stainer` 函数的 API 将接收一个包含两个关键令牌的字典：
-   `worker_result`: 来自 $F_{exec}$ 的执行结果。
-   `trace_input`: 来自 $F_{pre}$ 的、包含 `start_ts` 的追踪信息。

函数将根据 `worker_result` 的类型（是否为 `Exception`）来决定输出令牌的 `tag`，计算执行耗时，并更新追踪信息，最终返回一个包含了完整上下文的输出令牌。

### 标签

#intent/build #flow/ready #priority/high #comp/vm #comp/tests #concept/executor #scope/core #ai/instruct #task/domain/vm #task/object/stainer-instruction #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 Stainer 实现

我们创建 `stainer.py` 文件并直接写入其完整实现。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/instructions/stainer.py
~~~~~
~~~~~python
from typing import Dict
import time

from cascade.spec.physics import Token


def standard_stainer(inputs: Dict[str, Token]) -> Dict[str, Token]:
    """
    The standard implementation for a Post-process Node (F_post).

    It "stains" a pure result from a worker by wrapping it in a new Token
    with appropriate tags and updated trace information (like duration).

    Args:
        inputs: A dictionary mapping input port names to their corresponding Tokens.
                Expected ports:
                - 'worker_result': Token containing the pure result from F_exec.
                - 'trace_input': Token from F_pre containing 'start_ts' and other
                                 initial trace data.

    Returns:
        A dictionary mapping the output port name ('output') to the final
        stained Token.
    """
    end_ts = time.monotonic()

    # 1. Extract inputs
    worker_result_token = inputs["worker_result"]
    trace_input_token = inputs["trace_input"]

    result_payload = worker_result_token.payload
    # Use a copy to avoid mutating the original trace dict
    trace_payload = trace_input_token.payload.copy()

    # 2. Determine tag based on result (error or success)
    tag = "error" if isinstance(result_payload, Exception) else "default"

    # 3. Calculate duration and update trace
    start_ts = trace_payload.get("start_ts", end_ts)  # Default to end_ts for duration=0
    duration = end_ts - start_ts
    trace_payload["duration"] = duration
    trace_payload["end_ts"] = end_ts

    # 4. Create the final "stained" token
    output_token = Token(payload=result_payload, tag=tag, trace=trace_payload)

    return {"output": output_token}

~~~~~

#### Acts 2: 编写 Stainer 的单元测试

现在，我们创建 `test_stainer.py` 文件，其中包含验证上述实现的测试用例。

~~~~~act
write_file
packages/cascade-vm/tests/unit/instructions/test_stainer.py
~~~~~
~~~~~python
import pytest
import time
from unittest.mock import patch

from cascade.spec.physics import Token
from cascade.vm.instructions.stainer import standard_stainer


def test_stainer_success_case():
    """
    Tests the standard success path: result is processed, tag is 'default',
    and trace is correctly updated with duration.
    """
    start_ts = 1000.0
    end_ts = 1002.5

    inputs = {
        "worker_result": Token(payload="SuccessData"),
        "trace_input": Token(payload={"start_ts": start_ts, "id": "task_A"}),
    }

    with patch("time.monotonic", return_value=end_ts):
        outputs = standard_stainer(inputs)

    assert "output" in outputs
    output_token = outputs["output"]

    assert output_token.payload == "SuccessData"
    assert output_token.tag == "default"
    assert output_token.trace["id"] == "task_A"
    assert output_token.trace["start_ts"] == start_ts
    assert output_token.trace["end_ts"] == end_ts
    assert output_token.trace["duration"] == 2.5


def test_stainer_error_case():
    """
    Tests the failure path: result is an exception, tag is 'error',
    and trace is still correctly updated.
    """
    start_ts = 2000.0
    end_ts = 2000.1
    error = ValueError("Something went wrong")

    inputs = {
        "worker_result": Token(payload=error),
        "trace_input": Token(payload={"start_ts": start_ts}),
    }

    with patch("time.monotonic", return_value=end_ts):
        outputs = standard_stainer(inputs)

    assert "output" in outputs
    output_token = outputs["output"]

    assert output_token.payload is error  # Should be the same exception instance
    assert output_token.tag == "error"
    assert output_token.trace["end_ts"] == end_ts
    assert pytest.approx(output_token.trace["duration"]) == 0.1


def test_stainer_handles_missing_start_ts_gracefully():
    """
    If start_ts is missing from the trace for some reason, duration should be 0.
    """
    end_ts = 3000.0
    inputs = {
        "worker_result": Token(payload="data"),
        "trace_input": Token(payload={}),  # No start_ts
    }

    with patch("time.monotonic", return_value=end_ts):
        outputs = standard_stainer(inputs)

    output_token = outputs["output"]
    assert output_token.trace["duration"] == 0.0
    assert output_token.trace["end_ts"] == end_ts

~~~~~

### 下一步建议

我们已经同时完成了 `standard_stainer` 的实现和测试。

根据路线图，**阶段 2** 的最后一项任务是 **任务 2.3：实现标准 Observer ($F_{obs}$)**。这个微指令负责将内部的物理令牌转换为外部可见的、标准化的遥测事件。

我建议我们立即开始为 `standard_observer` 创建实现和测试。
