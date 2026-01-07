好的，我们已经为重试机制奠定了信息守恒的基础。现在，我们将利用 `D_context` 通道，实现“最后一公里”——构建一个物理上的 `F_retry` 节点。

这个计划将创建一个独立的、可重用的标准库函数，它封装了重试决策的全部逻辑，将错误处理从命令式代码转变为计算图中的拓扑结构。

## [WIP] feat(core): Implement F_retry node for topological error handling

### 错误分析

无。此计划是上一个计划的延续，旨在实现一个新功能。

### 用户需求

实现一个标准的 `F_retry` 物理节点逻辑，该逻辑可以：
1.  同时消费来自 `Stainer` 的 `output_error` 端口的错误 `Token` 和来自 `D_context` 旁路通道的原始输入上下文 `Token`。
2.  根据节点自身定义的重试策略（例如 `max_attempts`）和 `Token` 中追踪的当前重试次数，做出决策。
3.  如果决定重试，则将原始输入上下文 `Token` 路由到 `retry_out` 端口，以便将其连接回原始任务的 `Bleacher`。
4.  如果达到重试上限，则将错误 `Token` 路由到 `fail_out` 端口，导向一个永久失败的终端节点。

### 评论

这是 Cascade 架构理念的一次完美体现。我们正在将一个传统的、隐藏在执行器内部的命令式控制流（`for` 循环重试）转化为一个显式的、可观测的、声明式的物理拓扑结构。`F_retry` 节点就像一个物理上的“分拣机”，它根据能量（`Token`）的属性（`trace` 中的重试次数）将其引导到不同的物理路径。这种方法使得错误处理和重试策略变得与核心业务逻辑完全解耦，并且其行为在可视化图上清晰可见。

### 目标

1.  在 `cascade-spec` 中定义一个新的物理节点类型 `RetryNode`，它继承自 `PhysicsFuncNode` 并包含 `max_attempts` 等策略属性。
2.  在 `cascade-std` 标准库中创建一个新的 `retry.py` 文件，用于存放重试逻辑。
3.  实现核心的 `standard_retry_logic` 函数，该函数将作为所有 `RetryNode` 的物理实现。
4.  更新 `Linker`，使其能够将 `RetryNode` 类型的物理节点链接到 `standard_retry_logic` 函数。
5.  将新的 `standard_retry_logic` 导出，使其成为标准库的一部分。

### 基本原理

我们将遵循“策略在节点，状态在令牌”的核心原则。
-   **策略 (Policy)**: 重试的配置（如最大次数 `max_attempts`）将被静态地存储在编译器生成的 `RetryNode` 实例中。
-   **状态 (State)**: 当前的重试次数 (`retry_count`) 将作为动态状态，在 `Token` 的 `trace` 载荷中进行传递和累加。

`standard_retry_logic` 函数将是一个纯粹的状态机，它接收代表策略的 `node` 和代表状态的 `token`，然后根据规则产生输出，决定能量的下一个流向。这种设计确保了逻辑的确定性和可测试性。

### 标签

#intent/build #flow/ready #priority/high #comp/engine #comp/std-library #concept/state #scope/core #ai/delegate #task/domain/core #task/object/retry-node #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 定义 `RetryNode` 物理节点规范

首先，我们需要在 `cascade-spec` 中为 `F_retry` 节点创建一个正式的类型定义。我们将其放在 `triad.py` 中，因为它与 Triad 结构紧密相关。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/triad.py
~~~~~
~~~~~python.old
@dataclass
class ObservabilityNode(PhysicsFuncNode):
    pass
~~~~~
~~~~~python.new
@dataclass
class ObservabilityNode(PhysicsFuncNode):
    pass


@dataclass
class RetryNode(PhysicsFuncNode):
    max_attempts: int = 3
    # Future: delay, backoff, etc.
~~~~~

并且更新 `__init__.py` 使其可被外部引用。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/__init__.py
~~~~~
~~~~~python.old
from cascade.spec.physical.triad import (
    BleachNode,
    WorkerNode,
    StainNode,
    ObservabilityNode,
)
~~~~~
~~~~~python.new
from cascade.spec.physical.triad import (
    BleachNode,
    WorkerNode,
    StainNode,
    ObservabilityNode,
    RetryNode,
)
~~~~~
~~~~~python.old
    "StainNode",
    "ObservabilityNode",
]
~~~~~
~~~~~python.new
    "StainNode",
    "ObservabilityNode",
    "RetryNode",
]
~~~~~


#### Acts 2: 创建 `standard_retry_logic` 实现

现在，我们在 `cascade-std` 中创建 `retry.py` 并实现核心重试逻辑。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/system/retry.py
~~~~~
~~~~~python
from typing import Dict, Any

from cascade.spec import RetryNode
from cascade.spec.physical.nodes import Token


def standard_retry_logic(
    inputs: Dict[str, Token], node: RetryNode, resources: Any
) -> Dict[str, Token]:
    """
    Implements topological retry logic.

    Inputs:
        - error_in: The error token from the failed task.
        - context_in: The original input context token.

    Outputs:
        - retry_out: The context token, to be routed back for retry.
        - fail_out: The error token, if retries are exhausted.
    """
    error_token = inputs["error_in"]
    context_token = inputs["context_in"]

    # State is in the token trace
    trace = context_token.trace
    retry_count = trace.get("retry_count", 0)
    retry_count += 1

    # Policy is in the node definition
    max_attempts = node.max_attempts

    if retry_count < max_attempts:
        # Retry: update state and route context token back
        trace["retry_count"] = retry_count
        return {"retry_out": context_token}
    else:
        # Fail permanently: route error token to failure sink
        return {"fail_out": error_token}
~~~~~

#### Acts 3: 在标准库中导出新函数

将新创建的 `standard_retry_logic` 函数添加到 `cascade-std.system` 的 `__init__.py` 中，使其成为公共 API。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/__init__.py
~~~~~
~~~~~python.old
# System Control ICs for graph lifecycle management (Sovereignty).
from .gate import gate_passthrough

__all__ = ["gate_passthrough"]
~~~~~
~~~~~python.new
# System Control ICs for graph lifecycle management (Sovereignty).
from .gate import gate_passthrough
from .retry import standard_retry_logic

__all__ = ["gate_passthrough", "standard_retry_logic"]
~~~~~

#### Acts 4: 更新 `Linker` 以识别 `RetryNode`

最后，也是关键的一步，我们教 `Linker` 如何将新的 `RetryNode` 类型链接到它的标准实现。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/linker.py
~~~~~
~~~~~python.old
from cascade.spec.physical.assembly import Assembly
from cascade.spec.physical.nodes import PhysicsFuncNode
from cascade.reflection import PhysicalIdGenerator

from .registry import CodeRegistry
~~~~~
~~~~~python.new
from cascade.spec.physical.assembly import Assembly
from cascade.spec.physical.nodes import PhysicsFuncNode
from cascade.spec.physical.triad import RetryNode
from cascade.reflection import PhysicalIdGenerator

from .registry import CodeRegistry
~~~~~
~~~~~python.old
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.system.egress import standard_egress
from cascade.std.system.gate import gate_passthrough
~~~~~
~~~~~python.new
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.system.egress import standard_egress
from cascade.std.system.gate import gate_passthrough
from cascade.std.system.retry import standard_retry_logic
~~~~~
~~~~~python.old
            # 2. Standard Library Nodes (via ID Heuristics)
            stdlib_func = self._resolve_stdlib(node_id)
            if stdlib_func:
                function_map[node_id] = stdlib_func
                continue

        return function_map
~~~~~
~~~~~python.new
            # 2. Standard Library Nodes (via ID Heuristics or Type)
            stdlib_func = self._resolve_stdlib(node)
            if stdlib_func:
                function_map[node.id] = stdlib_func
                continue

        return function_map
~~~~~
~~~~~python.old
    def _resolve_stdlib(self, node_id: str) -> Optional[Callable]:
        # Triad
        if node_id.endswith(".bleach"):
            return standard_bleacher
        if node_id.endswith(".stain"):
            return standard_stainer
~~~~~
~~~~~python.new
    def _resolve_stdlib(self, node: PhysicsFuncNode) -> Optional[Callable]:
        node_id = node.id
        # Type-based resolution is more robust
        if isinstance(node, RetryNode):
            return standard_retry_logic

        # Heuristic-based resolution for legacy/generic nodes
        if node_id.endswith(".bleach"):
            return standard_bleacher
        if node_id.endswith(".stain"):
            return standard_stainer
~~~~~

### 下一步建议

我们已经成功地创建了 `F_retry` 节点的核心逻辑和类型规范。它现在是标准库中一个可用的“物理元件”。

然而，它还没有被集成到我们的“宇宙”中。`LazyResult.with_retry()` 策略仍然没有被编译成使用这个节点的物理拓扑。

因此，下一步的宏观任务是：
1.  **修改编译器 `WiringPolicy`**：创建一个新的 `RetryWiringPolicy` 或增强现有的 `ControlFlowWiringPolicy`。
2.  **实现拓扑生成**：当该策略检测到 `node_ir` 中存在 `retry_policy` 时，它将：
    *   在 Triad 旁边创建一个 `RetryNode` 实例，并将策略（如 `max_attempts`）配置到该节点上。
    *   创建一个 `D_failed` 终端数据节点。
    *   **自动布线**：
        *   `Stainer:output_error` -> `RetryNode:error_in`
        *   `D_context:out` -> `RetryNode:context_in`
        *   `RetryNode:retry_out` -> `Bleacher: (new retry_in port)`
        *   `RetryNode:fail_out` -> `D_failed:in`

这个步骤将完全自动化重试逻辑的物理实现，完成从用户意图到物理现实的转换。如果你同意，我将开始制定这个编译时布线策略的计划。
