好的，我来修复这两个类型错误。

1.  **`builder.py`**: 错误在于 `policy.expand()` 方法期望接收一个 `ExpansionContext` 类型的参数，但我们传递了 `WiringContext`。尽管这两个类的结构几乎相同，但它们没有继承关系，因此类型检查器会报错。最优雅的解决方案是让 `WiringContext` 继承自 `ExpansionContext`，因为 `WiringContext` 在功能上是 `ExpansionContext` 的超集（它包含了额外的方法）。

2.  **`vm.py`**: 错误在于 `Machine` 类的构造函数 `__init__` 明确要求 `compute_service` 参数的类型为 `LocalComputeService`，但我们传递的是一个 `BridgedComputeService` 实例。这两个类实现了相同的接口（`run`, `stop` 等），但不属于同一个继承树。正确的做法是定义一个 `Protocol` 来描述这个共享接口，并让 `Machine` 接受该协议类型，从而解耦具体实现。

我将按以上分析生成修复计划。

## [WIP] fix: 修复两个 Pyright 类型不兼容错误

### 错误分析

如上所述，两个类型错误均源于结构相似但无继承关系的类之间的不兼容性。

### 用户需求

修复 Pyright 报告的两个 `reportArgumentType` 错误。

### 评论

这是一个常见的类型系统问题。通过引入继承和协议，我们可以使类型关系更加明确，从而解决这些错误，并使代码架构更加健壮和清晰。

### 目标

1.  重构 `WiringContext`，使其继承自 `ExpansionContext`。
2.  创建一个新的 `ComputeServiceProtocol` 来抽象 `LocalComputeService` 和 `BridgedComputeService` 的共同接口。
3.  更新 `Machine.__init__` 以接受新的 `ComputeServiceProtocol`。

### 基本原理

*   **对于 Context**：`WiringContext` 和 `ExpansionContext` 共享完全相同的字段。通过让 `WiringContext` 继承 `ExpansionContext` 并移除其内部重复的字段定义，我们可以建立一个清晰的 "is-a" 关系，满足类型检查器的要求。
*   **对于 ComputeService**：`LocalComputeService` 和 `BridgedComputeService` 实现了相同的行为（`run`, `stop` 等）。定义一个 `Protocol` 是 Python 中实现结构化类型（或称“鸭子类型”）的最佳方式，它能让 `Machine` 类依赖于行为接口而非具体实现。

### 标签
#intent/fix #flow/ready #priority/high #comp/compiler #comp/runtime #scope/core #ai/instruct #task/domain/typing #task/object/type-errors #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修复 `WiringContext` 类型不兼容问题

首先，我们将修改 `WiringContext` 的定义，使其继承自 `ExpansionContext`，并移除冗余的字段声明。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/context.py
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Dict

from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.expansion.context import ExpansionContext


@dataclass
class WiringContext(ExpansionContext):
    def register_subgraph(self, node_id: str, subgraph: SubGraph) -> None:
        self.subgraphs[node_id] = subgraph
        self.wire.add_subgraph(subgraph)

    def get_subgraph(self, node_id: str) -> SubGraph:
        if node_id not in self.subgraphs:
            raise KeyError(f"Subgraph for node '{node_id}' not found in context.")
        return self.subgraphs[node_id]
~~~~~

#### Acts 2: 引入 `ComputeServiceProtocol`

接下来，我们在 `vm/protocols.py` 文件中定义一个新的协议，用于抽象所有计算服务的公共接口。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/protocols.py
~~~~~
~~~~~python
import asyncio
from typing import Protocol, Dict, Any, Optional


class ComputeServiceProtocol(Protocol):
    @property
    def active_count(self) -> int: ...

    def is_idle(self) -> bool: ...

    async def run(self) -> None: ...

    def stop(self) -> None: ...


class ReactorProtocol(Protocol):
    shutdown_event: asyncio.Event
    drain_event: asyncio.Event
    ingress_queue: Optional[asyncio.Queue]

    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None: ...

    def step(self) -> int: ...
~~~~~

#### Acts 3: 更新 `Machine` 以使用新协议

最后，我们更新 `Machine` 类的定义，使其构造函数接受新的 `ComputeServiceProtocol`，从而解决第二个类型错误。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python
import asyncio
import logging
from cascade.vm.protocols import ReactorProtocol, ComputeServiceProtocol
from cascade.vm.services.chronos import ChronosService

logger = logging.getLogger(__name__)


class Machine:
    def __init__(
        self,
        reactor: ReactorProtocol,
        compute_service: ComputeServiceProtocol,
        chronos_service: ChronosService,
        wakeup_event: asyncio.Event,
    ):
        self.reactor = reactor
        self.compute_service = compute_service
        self.chronos_service = chronos_service
        self.wakeup_event = wakeup_event
        # We can get the queue from the reactor, which is the canonical consumer
        self.ingress_queue = reactor.ingress_queue

    async def run(self) -> None:
        logger.info("Machine started.")

        # Start Services
        compute_task = asyncio.create_task(self.compute_service.run())
        chronos_task = asyncio.create_task(self.chronos_service.run())

        try:
            # Run until explicit shutdown signal
            while not self.reactor.shutdown_event.is_set():
                try:
                    # 1. Drive the Physics Kernel (Synchronous Step)
                    fired_count = self.reactor.step()

                    # 2. DRAIN Logic: Check for Quiescence
                    if self.reactor.drain_event.is_set():
                        # System is quiescent if:
                        # - No physics transitions occurred (fired_count == 0)
                        # - No compute tasks are running (active_count == 0)
                        # - No results are pending ingress (ingress_queue empty)
                        is_ingress_pending = (
                            self.ingress_queue and not self.ingress_queue.empty()
                        )
                        if (
                            fired_count == 0
                            and self.compute_service.active_count == 0
                            and not is_ingress_pending
                        ):
                            logger.info("System drained (Quiescent). Shutting down.")
                            self.reactor.shutdown_event.set()
                            continue

                    # 3. Adaptive Throttling / Waiting
                    if fired_count > 0 or (
                        self.ingress_queue and not self.ingress_queue.empty()
                    ):
                        # If physics fired or ingress is pending, yield but loop again immediately.
                        await asyncio.sleep(0)
                    else:
                        # System is physically idle. Wait for new ingress.
                        try:
                            # Use a timeout to periodically re-check for drain completion
                            await asyncio.wait_for(
                                self.wakeup_event.wait(), timeout=0.1
                            )
                            self.wakeup_event.clear()
                        except asyncio.TimeoutError:
                            pass  # Loop again to check state

                except Exception as e:
                    logger.critical(f"Machine loop crashed: {e}", exc_info=True)
                    # Force shutdown on machine loop crash
                    self.reactor.shutdown_event.set()

            logger.info("Machine shutdown signal received.")

        finally:
            # Shutdown sequence
            self.compute_service.stop()
            self.chronos_service.stop()
            compute_task.cancel()
            chronos_task.cancel()
            try:
                await asyncio.gather(compute_task, chronos_task)
            except asyncio.CancelledError:
                pass
            logger.info("Machine stopped.")
~~~~~

### 下一步建议

现在代码修改已经完成。我建议你执行 `[COMMIT]` 计划，将这些修复提交到版本控制中。这样，我们就完成了一个完整的修复周期。
