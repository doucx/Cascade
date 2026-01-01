好的，我们现在进入 TDD 流程的下一步：实现 `standard_bleacher` 函数的逻辑，使测试从 RED 变为 GREEN。

我将生成一个计划来更新 `bleacher.py` 文件，用完整的实现替换掉 `NotImplementedError` 占位符。

## [WIP] feat(vm): Implement standard_bleacher instruction

### 用户需求

根据 TDD 流程，在测试用例（RED 状态）建立后，需要编写 `standard_bleacher` 函数的具体实现，以使所有测试通过（GREEN 状态）。

### 评论

这是 TDD 周期的核心步骤。该实现将严格遵循测试用例所定义的契约，处理载荷提取、追踪信息合并和时间戳注入。这将为 Cascade VM 提供第一个可用的、健壮的微指令。

### 目标

1.  在 `packages/cascade-vm/src/cascade/vm/instructions/bleacher.py` 文件中实现 `standard_bleacher` 函数。
2.  确保实现逻辑能够正确处理输入、合并追踪数据并生成符合预期的输出令牌。
3.  使 `test_bleacher.py` 中的所有测试用例都能成功通过。

### 基本原理

我们将使用 `write_file` 操作来完整地覆写 `bleacher.py`。实现逻辑将很简单：
1.  初始化两个空的字典：`worker_payload` 和 `trace_payload`。
2.  遍历所有输入的令牌。
3.  对于每个令牌，将其 `payload` 存入 `worker_payload`，并将其 `trace` 字典更新到 `trace_payload` 中。
4.  在循环结束后，获取当前 `time.monotonic()` 时间戳并添加到 `trace_payload`。
5.  最后，将 `worker_payload` 和 `trace_payload` 分别包装成新的 `Token` 对象，并以标准格式返回。

### 标签

#intent/build #flow/ready #priority/high #comp/vm #concept/executor #scope/core #ai/instruct #task/domain/testing #task/object/bleacher-instruction #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 实现 a standard_bleacher

我们将用完整的业务逻辑覆写 `bleacher.py` 文件。

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
    worker_payload: Dict[str, any] = {}
    trace_payload: Dict[str, any] = {}

    # 1. Extract payloads and merge traces from all inputs
    for port_name, input_token in inputs.items():
        worker_payload[port_name] = input_token.payload
        trace_payload.update(input_token.trace)

    # 2. Capture the start timestamp and add it to the trace
    trace_payload["start_ts"] = time.monotonic()

    # 3. Create the output tokens
    worker_token = Token(payload=worker_payload)
    trace_token = Token(payload=trace_payload)

    return {
        "worker_input": worker_token,
        "trace_output": trace_token,
    }
~~~~~

### 下一步建议

我们已经完成了 `standard_bleacher` 的实现，现在测试套件应该处于 GREEN 状态。

根据路线图，**阶段 2** 的下一项任务是 **任务 2.2：实现标准 Stainer ($F_{post}$)**。这将是执行三连体的收尾环节，负责染色和路由。

我建议我们开始为 `standard_stainer` 创建测试用例，继续我们的 TDD 流程。
