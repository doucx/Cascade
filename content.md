好的，我们来执行路线图的第二步。

这个计划将引入 `ChronosService`，一个专门处理异步时间延迟的后台服务。它将与 `Reactor` 和 `ComputeService` 一起被 `Machine` 管理，通过专用的队列接收延迟请求，并将完成信号通过 `ingress_queue` 注入回物理层。

这使得物理层在请求一个“等待”操作时，自身可以保持完全同步和非阻塞。

## [WIP] feat(vm): 引入 ChronosService 以处理异步时间延迟

### 用户需求
1.  创建一个 `ChronosService`，用于处理时间延迟请求。
2.  将该服务集成到 `Machine` 的生命周期中，使其与 `Reactor` 和 `ComputeService` 协同工作。
3.  建立一个通信机制，允许物理层的 Kernel 函数向 `ChronosService` 发送延迟请求。

### 评论
这是 Cascade 架构中一个优雅的飞跃。通过将“时间”抽象为一个外部服务，我们彻底解决了同步物理引擎与异步现实世界之间的矛盾。`ChronosService` 就像是物理层的一个外部“晶振”，为系统提供了时间脉冲，而物理层本身则保持了其纯粹的、基于因果律的离散步进模型。

### 目标
1.  在 `cascade.vm` 中定义一个新的 `DelayRequest` 数据契约。
2.  创建 `ChronosService` 类，它监听一个请求队列，执行 `asyncio.sleep`，然后将结果发送到 `Reactor` 的 `ingress_queue`。
3.  修改 `Machine` 以管理 `ChronosService` 的启动和关闭。
4.  更新测试工具 `EventDrivenRunner`，将 `ChronosService` 和其所需的 `chronos_queue` 正确地装配进测试环境。

### 基本原理
`Reactor` 必须保持同步。时间延迟是异步的。为了解耦这两者，我们引入 `ChronosService` 作为中介。Kernel 函数（物理层）通过向 `system.chronos_queue` 发送一个 `DelayRequest` 来“请求”一个延迟。`ChronosService`（环境层）接收此请求，执行异步等待，然后将一个完成信号（Token）注入回 `Reactor` 的 `ingress_queue`。对于 `Reactor` 来说，它无法区分这个 Token 是来自 `ComputeService` 的计算结果，还是来自 `ChronosService` 的时间信号，从而保持了其核心逻辑的纯粹性。

### 标签
#intent/build #flow/ready #priority/high #comp/vm #concept/time #task/domain/physics #task/object/time-service #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 定义 DelayRequest 契约

我们首先需要一个标准的数据结构来描述延迟请求。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/services/contracts.py
~~~~~
~~~~~python
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token


@dataclass(frozen=True)
class DelayRequest:
    """
    A request sent to the ChronosService to delay a token.
    """

    delay_seconds: float
    target_nid: str
    token: Token
~~~~~

#### Acts 2: 实现 ChronosService

现在，我们创建核心的时间服务。它是一个简单的异步循环，监听请求并处理它们。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/services/chronos.py
~~~~~
~~~~~python
import asyncio
import logging
from typing import Tuple

from cascade.spec.physical.nodes import Token
from cascade.vm.services.contracts import DelayRequest

logger = logging.getLogger(__name__)


class ChronosService:
    """
    A service that handles time-based delays asynchronously.
    """

    def __init__(
        self,
        inbound_queue: "asyncio.Queue[DelayRequest]",
        outbound_queue: "asyncio.Queue[Tuple[str, Token]]",
        wakeup_event: asyncio.Event,
    ):
        self.inbound_queue = inbound_queue
        self.outbound_queue = outbound_queue
        self.wakeup_event = wakeup_event
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info("ChronosService started.")
        try:
            while self._running:
                request = await self.inbound_queue.get()
                asyncio.create_task(self._handle_request(request))
        finally:
            logger.info("ChronosService stopped.")

    def stop(self) -> None:
        self._running = False

    async def _handle_request(self, request: DelayRequest) -> None:
        try:
            await asyncio.sleep(request.delay_seconds)
            await self.outbound_queue.put((request.target_nid, request.token))
            self.wakeup_event.set()
        except asyncio.CancelledError:
            logger.debug("Delay request cancelled.")
        except Exception:
            logger.exception(
                f"ChronosService failed to handle delay request for {request.target_nid}"
            )
~~~~~

#### Acts 3: 将 ChronosService 集成到 Machine

`Machine` 是所有后台服务的总协调器。我们需要让它来管理 `ChronosService` 的生命周期。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
import asyncio
import logging
from cascade.vm.reactor import Reactor
from cascade.vm.compute.service import LocalComputeService

logger = logging.getLogger(__name__)


class Machine:
    def __init__(
        self,
        reactor: Reactor,
        compute_service: LocalComputeService,
        wakeup_event: asyncio.Event,
    ):
        self.reactor = reactor
        self.compute_service = compute_service
        self.wakeup_event = wakeup_event
        # We can get the queue from the reactor, which is the canonical consumer
        self.ingress_queue = reactor.ingress_queue

    async def run(self) -> None:
        logger.info("Machine started.")

        # Start the Compute Service
        service_task = asyncio.create_task(self.compute_service.run())

        try:
            # Run until explicit shutdown signal
~~~~~
~~~~~python.new
import asyncio
import logging
from cascade.vm.reactor import Reactor
from cascade.vm.compute.service import LocalComputeService
from cascade.vm.services.chronos import ChronosService

logger = logging.getLogger(__name__)


class Machine:
    def __init__(
        self,
        reactor: Reactor,
        compute_service: LocalComputeService,
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
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
        finally:
            # Shutdown sequence
            self.compute_service.stop()
            service_task.cancel()
            try:
                await service_task
            except asyncio.CancelledError:
                pass
            logger.info("Machine stopped.")
~~~~~
~~~~~python.new
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

#### Acts 4: 在测试工具中装配 ChronosService

最后，我们需要更新 `EventDrivenRunner`，这个测试工具负责创建和连接所有服务。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
from cascade.runtime.services.observability.events import Event, TaskExecutionFinished
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.vm.registry import CodeRegistry
from cascade.vm.linker import Linker
~~~~~
~~~~~python.new
from cascade.runtime.services.observability.events import Event, TaskExecutionFinished
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.vm.services.chronos import ChronosService
from cascade.vm.services.contracts import DelayRequest
from cascade.vm.registry import CodeRegistry
from cascade.vm.linker import Linker
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
        # 1. Setup Queues for disconnected execution
        self.compute_queue: asyncio.Queue[ComputeRequest] = asyncio.Queue()
        self.ingress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()

        # 2. Setup Services
        # In a real system, store would be a separate entity.
~~~~~
~~~~~python.new
        # 1. Setup Queues for disconnected execution
        self.compute_queue: asyncio.Queue[ComputeRequest] = asyncio.Queue()
        self.chronos_queue: asyncio.Queue[DelayRequest] = asyncio.Queue()
        self.ingress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()

        # 2. Setup Services
        # In a real system, store would be a separate entity.
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
            inbound_queue=self.compute_queue,
            outbound_queue=self.ingress_queue,
            wakeup_event=self.wakeup_event,
        )

        # 3. Setup Event Bus & Resource Registry
        self.event_bus = EventBus()
~~~~~
~~~~~python.new
            inbound_queue=self.compute_queue,
            outbound_queue=self.ingress_queue,
            wakeup_event=self.wakeup_event,
        )
        self.chronos_service = ChronosService(
            inbound_queue=self.chronos_queue,
            outbound_queue=self.ingress_queue,
            wakeup_event=self.wakeup_event,
        )

        # 3. Setup Event Bus & Resource Registry
        self.event_bus = EventBus()
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
        self.resource_registry = ResourceRegistry()
        self.resource_registry.register("system.event_bus", self.event_bus)
        self.resource_registry.register("system.compute_queue", self.compute_queue)
        self.resource_registry.register("system.object_store", self.object_store)

        # 4. Setup Reactor
        factory = reactor_factory or Reactor
~~~~~
~~~~~python.new
        self.resource_registry = ResourceRegistry()
        self.resource_registry.register("system.event_bus", self.event_bus)
        self.resource_registry.register("system.compute_queue", self.compute_queue)
        self.resource_registry.register("system.chronos_queue", self.chronos_queue)
        self.resource_registry.register("system.object_store", self.object_store)

        # 4. Setup Reactor
        factory = reactor_factory or Reactor
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
        # The Machine is now a component managed by the harness
        from cascade.vm.machine import Machine

        self.machine = Machine(self.reactor, self.compute_service, self.wakeup_event)
        self._loop_task: Optional[asyncio.Task] = None
        self._service_task: Optional[asyncio.Task] = None
~~~~~
~~~~~python.new
        # The Machine is now a component managed by the harness
        from cascade.vm.machine import Machine

        self.machine = Machine(
            self.reactor, self.compute_service, self.chronos_service, self.wakeup_event
        )
        self._loop_task: Optional[asyncio.Task] = None
        self._service_task: Optional[asyncio.Task] = None
~~~~~

### 下一步建议
基础设施已经就位。我们现在可以继续执行路线图的第三步：**实现 `std.system.sleep` IC**。

这将是一个非常简单的 Kernel 函数，它的唯一作用就是从 `ResourceRegistry` 中获取 `system.chronos_queue`，然后将一个 `DelayRequest` 放入其中。这将是第一个真正利用到我们新构建的时间服务的物理层组件。
