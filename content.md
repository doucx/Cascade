好的，我们开始实施 **阶段 2：微指令集构建**。

第一项任务是实现标准的 **Bleacher ($F_{pre}$)**。遵循 TDD 流程，我将首先创建一个计划来定义其 API 和行为，并通过编写测试用例来进入 RED 状态。此计划将创建所需的文件结构和测试文件，但不会包含实现代码。

## [WIP] feat: 为标准的 Bleacher 指令创建测试

### 用户需求

根据 [Cascade 3.0 重构路线图](Cascade%203.0%20重构路线图：迈向全对称计算物理场.md)，我们需要实现标准的 Bleacher ($F_{pre}$) 微指令。这个指令是执行三连体（Execution Triad）的第一环。

### 评论

这是构建物理虚拟机（VM）核心逻辑的关键一步。通过测试驱动开发（TDD），我们可以首先清晰地定义 Bleacher 的契约（API）和行为，确保其设计的健壮性，然后再进行具体实现。

一个标准的 Bleacher 必须完成两个核心任务：
1.  **漂白 (Bleaching)**: 从所有输入令牌（`Token`）中提取纯净的业务载荷（`payload`），并将它们组装成一个 `kwargs` 字典，供后续的执行节点（`WorkerNode`）使用。
2.  **打点 (Timestamping)**: 捕获当前的物理时间戳 `start_ts`，并将其与其他从输入令牌中收集的追踪信息（`trace`）合并，然后放入一个专用的追踪令牌中，供后处理节点（`StainNode`）使用。

### 目标

1.  创建 `cascade-vm` 包中存放微指令集的目录结构。
2.  定义 `standard_bleacher` 函数的 API。
3.  编写一套全面的单元测试，覆盖其核心功能、边界情况和追踪信息合并逻辑。
4.  将测试套件置于 RED 状态，为下一步的实现做好准备。

### 基本原理

我们将创建一个新的测试文件 `tests/unit/instructions/test_bleacher.py`。该文件将直接导入 `cascade.vm.instructions.bleacher` 模块。为了让导入能够成功，我们也会创建 `bleacher.py` 文件，但其中的 `standard_bleacher` 函数只会抛出 `NotImplementedError`。

这种方法确保了我们的 TDD 流程是纯粹的：测试因为缺少实现而失败，而不是因为导入错误等环境问题。

### 标签

#intent/tooling #flow/ready #priority/high #comp/tests #comp/vm #concept/executor #scope/core #ai/instruct #task/domain/testing #task/object/bleacher-instruction #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建目录和文件结构

首先，我们为 VM 的微指令集创建标准的目录结构，并建立对应的测试文件。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-vm/src/cascade/vm/instructions
touch packages/cascade-vm/src/cascade/vm/instructions/__init__.py
mkdir -p packages/cascade-vm/tests/unit/instructions
touch packages/cascade-vm/tests/unit/instructions/__init__.py
~~~~~

#### Acts 2: 创建 Bleacher 占位符实现

为了让测试文件能够成功导入，我们创建 `bleacher.py` 并加入一个会立即失败的占位符函数。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/instructions/bleacher.py
~~~~~
~~~~~python
from typing import Dict
import time

from cascade.spec.physics import Token


def standard_bleacher(inputs: Dict[str, Token]) -> Dict[str, Token]:
    """
    The standard implementation for a Pre-process Node (F_pre).

    It "bleaches" input tokens by stripping metadata to create a pure payload
    for the worker, and it prepares trace information for the post-processor.

    Args:
        inputs: A dictionary mapping input port names to their corresponding Tokens.

    Returns:
        A dictionary mapping output port names to newly created Tokens.
        Expected ports:
        - 'worker_input': A Token whose payload is a kwargs dict for F_exec.
        - 'trace_output': A Token whose payload contains merged trace info
                          and a new 'start_ts'.
    """
    raise NotImplementedError

~~~~~

#### Acts 3: 编写 Bleacher 的单元测试

现在，我们编写完整的测试用例，这些测试用例将驱动下一步的开发。

~~~~~act
write_file
packages/cascade-vm/tests/unit/instructions/test_bleacher.py
~~~~~
~~~~~python
import pytest
import time
from unittest.mock import patch

from cascade.spec.physics import Token
from cascade.vm.instructions.bleacher import standard_bleacher


def test_standard_bleacher_extracts_payloads():
    """
    Tests that the bleacher correctly extracts payloads from input tokens
    and assembles them into a kwargs dictionary for the worker.
    """
    inputs = {
        "arg1": Token(payload="hello"),
        "arg2": Token(payload=123),
    }

    outputs = standard_bleacher(inputs)

    assert "worker_input" in outputs
    worker_token = outputs["worker_input"]
    assert isinstance(worker_token, Token)
    assert worker_token.payload == {"arg1": "hello", "arg2": 123}


def test_standard_bleacher_generates_trace_with_timestamp():
    """
    Tests that the bleacher captures a start timestamp and places it in a
    separate trace token.
    """
    MOCK_TIMESTAMP = 12345.6789
    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = standard_bleacher({"data": Token(payload=1)})

    assert "trace_output" in outputs
    trace_token = outputs["trace_output"]
    assert isinstance(trace_token, Token)
    assert isinstance(trace_token.payload, dict)
    assert trace_token.payload.get("start_ts") == MOCK_TIMESTAMP


def test_standard_bleacher_with_empty_inputs():
    """
    Even with no inputs, the bleacher should produce a valid trace token
    and an empty kwargs payload for the worker.
    """
    MOCK_TIMESTAMP = 100.0
    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = standard_bleacher({})

    assert "worker_input" in outputs
    assert outputs["worker_input"].payload == {}

    assert "trace_output" in outputs
    assert outputs["trace_output"].payload == {"start_ts": MOCK_TIMESTAMP}


def test_standard_bleacher_merges_traces():
    """
    Tests that the bleacher merges trace information from all input tokens
    before adding its own timestamp. The last-seen key should win on conflict.
    """
    inputs = {
        "token_a": Token(payload=1, trace={"id": "A", "source": "X"}),
        "token_b": Token(payload=2, trace={"id": "B", "retry": 1}),
    }

    MOCK_TIMESTAMP = 200.0
    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = standard_bleacher(inputs)

    assert "trace_output" in outputs
    trace_payload = outputs["trace_output"].payload

    # Check for merged data
    assert trace_payload.get("id") == "B"  # Last write wins on conflict
    assert trace_payload.get("source") == "X"
    assert trace_payload.get("retry") == 1

    # Check for new timestamp
    assert trace_payload.get("start_ts") == MOCK_TIMESTAMP

~~~~~

### 下一步建议

我们已经成功地为 `standard_bleacher` 定义了行为并创建了失败的测试（RED 状态）。

下一步是实现 `standard_bleacher` 函数的逻辑，使其能够通过所有这些测试，进入 GREEN 状态。如果你同意，我将生成执行此实现的计划。
