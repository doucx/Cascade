Excellent. We've laid the groundwork, and now it's time to build upon it.

This plan implements the `std.system.sleep` Integrated Circuit (IC). This is a kernel function that acts as the physical layer's interface to the time dimension. It doesn't perform the wait itself; rather, it sends a request to the `ChronosService` and specifies a "wake-up" address where the signal should be returned after the delay.

## [WIP] feat(std): 实现 std.system.sleep 时间延迟 IC

### 用户需求
1.  在 `cascade-std` 中创建一个 `standard_sleep` kernel function。
2.  该函数应能向 `ChronosService` 发送一个包含延迟时间和返回地址的 `DelayRequest`。
3.  更新 `Linker` 以识别并链接这个新的标准库函数。

### 评论
这是将时间概念物理化的关键一步。通过 `standard_sleep`，我们将一个抽象的“等待”操作，转化为一个具体的、可路由的物理信号——`DelayRequest`。这保持了 `Reactor` 的纯粹性，因为它只看到了一个“发往外部”的请求，而将异步等待的复杂性完全委托给了环境服务。

### 目标
1.  在 `cascade.spec.physical.constants` 中为 `sleep` 和 `wakeup` 节点添加新的 `NodePrefix`。
2.  更新 `PhysicalIdGenerator` 以支持确定性地生成 `sleep` 和 `wakeup` 节点的 ID。
3.  在 `cascade.std.system` 中创建 `time.py` 并实现 `standard_sleep` kernel function。
4.  修改 `Linker`，使其能够自动将物理图中 `*.sleep` 后缀的节点链接到 `standard_sleep` 实现。

### 基本原理
`standard_sleep` IC 的工作模式是“请求-响应”。当 `Reactor` 执行到一个 `F_sleep` 节点时，`standard_sleep` 函数会被调用。它会：
1.  从输入 Token 中读取延迟时间 (`delay_in`) 和需要传递的数据 (`data_in`)。
2.  通过自己的节点 ID (`node.id`)，确定性地计算出对应的返回数据节点 `D_wakeup` 的 ID。
3.  将延迟时间、要传递的 Token 以及 `D_wakeup` 的 ID 打包成一个 `DelayRequest`。
4.  将此请求放入 `system.chronos_queue`。
5.  函数返回 `{}`, 在物理图中蒸发。
稍后，`ChronosService` 完成等待，会将 `data_in` Token 注入回 `Reactor` 的 `ingress_queue`，目标地址就是 `D_wakeup` 节点，从而继续执行后续流程。

### 标签
#intent/build #flow/ready #priority/high #comp/vm #comp/std #concept/time #task/domain/physics #task/object/sleep-ic #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 更新 Spec 常量

我们首先扩展 `NodePrefix` 以包含 `sleep` 和 `wakeup` 的类型。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/constants.py
~~~~~
~~~~~python.old
    STAIN = "stain"    # Triad: Post-process
    REQ = "req"        # Resource Requestor
    GATE = "gate"      # Control Gate
    PROBE = "probe"    # Introspection Probe

    # Global/System
    GLOBAL = "global"  # Global singleton
~~~~~
~~~~~python.new
    STAIN = "stain"    # Triad: Post-process
    REQ = "req"        # Resource Requestor
    GATE = "gate"      # Control Gate
    PROBE = "probe"    # Introspection Probe
    SLEEP = "sleep"    # Time delay requestor

    # Data Node Subtypes
    WAKEUP = "wakeup"  # Return point for a sleep operation

    # Global/System
    GLOBAL = "global"  # Global singleton
~~~~~

#### Acts 2: 扩展 ID 生成器

`PhysicalIdGenerator` 需要知道如何创建 `sleep` 和 `wakeup` 节点的 ID。

~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/naming.py
~~~~~
~~~~~python.old
    @staticmethod
    def stain_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.STAIN}"

    @staticmethod
    def worker_in_data(logical_node_id: str) -> str:
~~~~~
~~~~~python.new
    @staticmethod
    def stain_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.STAIN}"

    @staticmethod
    def sleep_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.SLEEP}"

    @staticmethod
    def wakeup_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.WAKEUP}"

    @staticmethod
    def worker_in_data(logical_node_id: str) -> str:
~~~~~

#### Acts 3: 实现 `standard_sleep` IC

现在，我们在 `cascade-std` 中创建新的 `time.py` 模块并实现核心逻辑。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/system/time.py
~~~~~
~~~~~python
import logging
from typing import Dict

from cascade.spec.physical.nodes import Token, PhysicsFuncNode
from cascade.vm.services.contracts import DelayRequest
from cascade.reflection import PhysicalIdGenerator

logger = logging.getLogger(__name__)


def standard_sleep(
    inputs: Dict[str, Token], node: PhysicsFuncNode, resources: any
) -> Dict[str, Token]:
    """
    Kernel function to request a time delay.

    It sends a DelayRequest to the ChronosService and returns nothing,
    effectively pausing a branch of execution until the ChronosService
    re-injects the token at a later time.

    Inputs:
        - 'delay_in': Token with a float payload for seconds to wait.
        - 'data_in': The token to be returned after the delay.
    """
    try:
        chronos_queue = resources.get("system.chronos_queue")

        delay_token = inputs["delay_in"]
        data_token = inputs["data_in"]

        delay_seconds = float(delay_token.payload)

        # The logical_id is the base part of our own node ID.
        # e.g., for "task123.sleep", the logical_id is "task123"
        logical_id = node.id.rsplit(".", 1)[0]
        target_nid = PhysicalIdGenerator.wakeup_data(logical_id)

        request = DelayRequest(
            delay_seconds=delay_seconds,
            target_nid=target_nid,
            token=data_token,
        )

        chronos_queue.put_nowait(request)

    except KeyError as e:
        logger.error(f"Sleep IC failed: resource '{e}' not found.")
    except Exception:
        logger.exception(f"Error in standard_sleep for node {node.id}")

    # This function returns no tokens to the graph. The flow is paused.
    return {}
~~~~~

#### Acts 4: 导出新的 IC

我们将新函数导出，使其成为 `cascade-std` 公开 API 的一部分。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/__init__.py
~~~~~
~~~~~python.old
# System Control ICs for graph lifecycle management (Sovereignty).
from .gate import gate_passthrough
from .retry import standard_retry_logic

__all__ = ["gate_passthrough", "standard_retry_logic"]
~~~~~
~~~~~python.new
# System Control ICs for graph lifecycle management (Sovereignty).
from .gate import gate_passthrough
from .retry import standard_retry_logic
from .time import standard_sleep

__all__ = ["gate_passthrough", "standard_retry_logic", "standard_sleep"]
~~~~~

#### Acts 5: 更新 Linker

最后，我们教 `Linker` 如何识别 `F_sleep` 节点。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/linker.py
~~~~~
~~~~~python.old
# Standard Library Imports (Micro-Kernel)
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.system.egress import standard_egress
from cascade.std.system.gate import gate_passthrough
~~~~~
~~~~~python.new
# Standard Library Imports (Micro-Kernel)
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.system.egress import standard_egress
from cascade.std.system.gate import gate_passthrough
from cascade.std.system.time import standard_sleep
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/linker.py
~~~~~
~~~~~python.old
    def _resolve_stdlib(self, node_id: str) -> Optional[Callable]:
        # Triad
        if node_id.endswith(f".{NodePrefix.BLEACH}"):
            return standard_bleacher
        if node_id.endswith(f".{NodePrefix.STAIN}"):
            return standard_stainer

        # Observability
~~~~~
~~~~~python.new
    def _resolve_stdlib(self, node_id: str) -> Optional[Callable]:
        # Triad & Time
        if node_id.endswith(f".{NodePrefix.BLEACH}"):
            return standard_bleacher
        if node_id.endswith(f".{NodePrefix.STAIN}"):
            return standard_stainer
        if node_id.endswith(f".{NodePrefix.SLEEP}"):
            return standard_sleep

        # Observability
~~~~~

### 下一步建议
我们已经完成了 `sleep` IC 的实现。现在最重要的事情是**验证**。

我建议创建一个新的集成测试 `packages/cascade-vm/tests/integration/test_time_services.py`。这个测试将：
1.  手动构建一个包含 `F_sleep` 和 `D_wakeup` 节点的物理图。
2.  使用 `EventDrivenRunner` 运行它。
3.  通过测量真实世界的时间（`time.monotonic`）来断言 `D_wakeup` 节点确实在延迟之后才接收到 Token。

这将是验证我们整个时间架构正确性的关键测试。
