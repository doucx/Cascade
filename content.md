好的，我们将开始执行 **Phase 3.3: VM 增强**。

此计划的核心是废除脆弱的 `Machine` 空闲退出机制，转而采用确定的信号驱动模型。我们将引入 `SystemControlToken` 和专门的系统总线，确保 `Machine` 只有在明确收到 `HALT`、`DRAIN` 信号或发生系统级错误时才会停止。这将根除“假死”问题。

[简要回答]
我将立即实施 Phase 3.3。此计划将引入 `SystemControlToken` 作为控制信号的载体，并在 `Reactor` 中实现对这些信号的优先处理。`Machine` 将被重构为一个基于信号的状态机，其生命周期将严格由 `shutdown_event` 控制，而不再依赖不可靠的空闲推测。

## [WIP] feat(vm): 引入信号驱动的 Machine 生命周期管理

### 用户需求
当前的 `Machine` 依赖“空闲检测”（Reactor 无动作且队列为空）来决定何时退出。这导致系统在启动初期或任务间隙可能因短暂空闲而意外“假死”。
用户需要一种确定性的生命周期管理机制，即 `Machine` 应当一直运行，直到收到明确的 `HALT` 或 `DRAIN` 信号。

### 评论
这是架构上从“批处理思维”向“守护进程思维”的转变。通过引入系统控制平面（Control Plane），我们将数据流（Token）与控制流（Signal）解耦，使系统在面对复杂的异步交互时更加稳健。

### 目标
1.  在 `cascade.spec.runtime.system` 中完善 `SystemControlToken` 定义，增加 `ControlCommand` 枚举。
2.  更新 `Reactor` 以识别和处理 `SystemControlToken`。
    *   增加 `shutdown_event` (asyncio.Event) 供 Machine 监听。
    *   在 `_handle_results_immediate` 中拦截控制 Token 并触发相应事件。
3.  重构 `Machine.run`。
    *   移除 `while True: ... if idle: break` 逻辑。
    *   改为 `while not self.shutdown_event.is_set(): ...`。
    *   保留 `idle` 检测仅用于动态调整 `sleep` 时间（自适应节流）。
4.  更新 `tests/unit/vm/test_machine.py`（如果存在，否则新建）以验证信号驱动的退出机制。

### 基本原理
-   **显式优于隐式**: 退出是一个重大状态变更，必须由显式的指令触发，而不能由“没事做”这种隐式状态推导出来。
-   **控制与数据分离**: 使用特殊的 Token 类型来承载控制指令，既利用了现有的拓扑传输机制，又能在执行层面上被特殊对待。

### 标签
#intent/architect #intent/refine #flow/ready #priority/high
#comp/runtime #scope/core
#task/domain/vm #task/object/machine #task/action/lifecycle-management
#task/state/continue

---

### Script

#### Acts 1: 完善 SystemControlToken 定义

首先，我们定义明确的控制命令枚举，并更新 `SystemControlToken`。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/runtime/system.py
~~~~~
~~~~~python.old
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SystemControlToken:
    command: str
    payload: Any = None
~~~~~
~~~~~python.new
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ControlCommand(StrEnum):
    HALT = "HALT"  # Immediate shutdown
    DRAIN = "DRAIN"  # Shutdown after current tasks complete (Not yet implemented)
    ERROR = "ERROR"  # System-level critical error


@dataclass(frozen=True)
class SystemControlToken:
    command: ControlCommand
    payload: Any = None
~~~~~

#### Acts 2: 更新 Terminators (Halt & Drain)

更新标准库中的终结器以使用新的枚举。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/terminator.py
~~~~~
~~~~~python.old
from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.runtime.system import SystemControlToken


def halt_signal(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # The output token is a special system type, not a standard data Token.
    # The VM will need to have a special port/handler for these.
    # We wrap it in a standard token for transport through a standard channel.
    control_token = SystemControlToken(command="HALT")
    return {"out": Token(payload=control_token)}
~~~~~
~~~~~python.new
from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.runtime.system import SystemControlToken, ControlCommand


def halt_signal(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # The output token is a special system type, not a standard data Token.
    # The VM will need to have a special port/handler for these.
    # We wrap it in a standard token for transport through a standard channel.
    control_token = SystemControlToken(command=ControlCommand.HALT)
    return {"out": Token(payload=control_token)}
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/drainer.py
~~~~~
~~~~~python.old
from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.runtime.system import SystemControlToken


def drain_signal(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    control_token = SystemControlToken(command="DRAIN")
    return {"out": Token(payload=control_token)}
~~~~~
~~~~~python.new
from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.runtime.system import SystemControlToken, ControlCommand


def drain_signal(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    control_token = SystemControlToken(command=ControlCommand.DRAIN)
    return {"out": Token(payload=control_token)}
~~~~~

#### Acts 3: 增强 Reactor 处理控制信号

我们将 `shutdown_event` 添加到 `Reactor`，并在处理结果时检查 `SystemControlToken`。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry

logger = logging.getLogger(__name__)


class Reactor:
    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        function_map: Dict[str, Callable],
        resource_registry: Optional[ResourceRegistry] = None,
        ingress_queue: Optional[asyncio.Queue] = None,
    ):
        self.graph = graph
        self.memory = memory
        self.function_map = function_map
        self.resource_registry = resource_registry or ResourceRegistry()
        self.ingress_queue = ingress_queue

        # State
        # node_id -> port_name -> list of callbacks
        self.sinks: Dict[str, Dict[str, List[Callable[[Token], Awaitable[None]]]]] = {}

        # Indexing for O(1) lookups during step/fire
        self._func_nodes: List[PhysicsFuncNode] = []
~~~~~
~~~~~python.new
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry

logger = logging.getLogger(__name__)


class Reactor:
    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        function_map: Dict[str, Callable],
        resource_registry: Optional[ResourceRegistry] = None,
        ingress_queue: Optional[asyncio.Queue] = None,
    ):
        self.graph = graph
        self.memory = memory
        self.function_map = function_map
        self.resource_registry = resource_registry or ResourceRegistry()
        self.ingress_queue = ingress_queue
        
        # Lifecycle Signals
        self.shutdown_event = asyncio.Event()

        # State
        # node_id -> port_name -> list of callbacks
        self.sinks: Dict[str, Dict[str, List[Callable[[Token], Awaitable[None]]]]] = {}

        # Indexing for O(1) lookups during step/fire
        self._func_nodes: List[PhysicsFuncNode] = []
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
    def _handle_results_immediate(
        self, node: PhysicsFuncNode, results: Dict[str, Token]
    ) -> None:
        if not isinstance(results, dict):
            logger.error(
                f"Function for node {node.id} returned {type(results)}, expected dict."
            )
            return

        outbound = self._outbound_channels.get(node.id, [])
        node_sinks = self.sinks.get(node.id, {})

        for port_name, token in results.items():
            if token is None:
                continue

            # A. Handle Sinks (Callbacks)
            # Note: Sinks in the physical layer MUST be non-blocking.
~~~~~
~~~~~python.new
    def _handle_results_immediate(
        self, node: PhysicsFuncNode, results: Dict[str, Token]
    ) -> None:
        if not isinstance(results, dict):
            logger.error(
                f"Function for node {node.id} returned {type(results)}, expected dict."
            )
            return

        outbound = self._outbound_channels.get(node.id, [])
        node_sinks = self.sinks.get(node.id, {})

        for port_name, token in results.items():
            if token is None:
                continue
            
            # 0. Intercept System Control Tokens
            if isinstance(token.payload, SystemControlToken):
                self._handle_control_signal(token.payload)

            # A. Handle Sinks (Callbacks)
            # Note: Sinks in the physical layer MUST be non-blocking.
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
            except asyncio.QueueEmpty:
                break
~~~~~
~~~~~python.new
            except asyncio.QueueEmpty:
                break

    def _handle_control_signal(self, ctrl: SystemControlToken) -> None:
        logger.info(f"Reactor received control signal: {ctrl.command}")
        if ctrl.command == ControlCommand.HALT:
            self.shutdown_event.set()
        elif ctrl.command == ControlCommand.DRAIN:
            # TODO: Implement drain logic (wait for active tasks to zero out)
            # For now, treat as Halt for safety
            logger.warning("DRAIN not fully implemented, treating as HALT.")
            self.shutdown_event.set()
        elif ctrl.command == ControlCommand.ERROR:
            logger.error(f"System Critical Error: {ctrl.payload}")
            self.shutdown_event.set()
~~~~~

#### Acts 4: 重构 Machine 的运行循环

修改 `Machine.run` 以使用信号控制，并提供自适应节流。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
    async def run(self) -> None:
        logger.info("Machine started.")

        # Start the Compute Service
        service_task = asyncio.create_task(self.compute_service.run())

        try:
            while True:
                # 1. Drive the Physics Kernel (Synchronous Step)
                fired_count = self.reactor.step()

                # 2. Check for Quiescence
                ingress_empty = self.ingress_queue.empty()
                compute_idle = self.compute_service.is_idle()

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"Machine Step: fired={fired_count}, "
                        f"ingress_empty={ingress_empty}, "
                        f"compute_idle={compute_idle} "
                        f"(inbound={self.compute_service.inbound_queue.qsize()}, "
                        f"active={self.compute_service._active_count})"
                    )

                # If the reactor did nothing, and there's no pending I/O...
                if fired_count == 0 and ingress_empty:
                    # ...and the compute service has no active workers...
                    if compute_idle:
                        logger.info("Machine idle. Stopping.")
                        break

                    # If we are just waiting for Compute, yield to the event loop
                    # to give the Service a chance to work.
                    await asyncio.sleep(0.001)
                else:
                    # If we did work, yield briefly to allow I/O ingress processing
                    # but return quickly to sustain high throughput.
                    await asyncio.sleep(0)
~~~~~
~~~~~python.new
    async def run(self) -> None:
        logger.info("Machine started.")

        # Start the Compute Service
        service_task = asyncio.create_task(self.compute_service.run())

        try:
            # Run until explicit shutdown signal
            while not self.reactor.shutdown_event.is_set():
                # 1. Drive the Physics Kernel (Synchronous Step)
                fired_count = self.reactor.step()

                # 2. Adaptive Throttling
                # If the reactor did work, we yield briefly to allow I/O but return ASAP.
                # If it was idle, we sleep longer to save CPU.
                if fired_count > 0:
                    await asyncio.sleep(0)
                else:
                    # Check if there is pending ingress work not yet processed?
                    # Reactor.step() handles ingress, so if fired_count is 0,
                    # it means ingress was empty or didn't trigger any firing.
                    
                    # We can sleep a bit longer to be nice to the CPU, 
                    # but check ingress_queue emptiness to be responsive.
                    if not self.ingress_queue.empty():
                         await asyncio.sleep(0)
                    else:
                         # Truly idle loop
                         await asyncio.sleep(0.001)

            logger.info("Machine shutdown signal received.")

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

#### Acts 5: 临时修复集成测试

由于 `Machine` 现在需要显式信号才能退出，我们现有的集成测试（依赖空闲退出）将会挂起。
我们需要为 `tests/integration/test_machine_integration.py` 注入一个 `HALT` 信号，或者暂时使用 `Machine` 的子类来恢复空闲退出行为以保持测试兼容性，直到我们全面更新测试套件。

为了保持测试的绿色（Green），我将在 `test_machine_integration.py` 中模拟一个发送 Halt 信号的机制。

**策略**: 修改测试图，在 `d_out` 收到结果后，触发一个 `HaltNode`。但这需要重新连线。
**更简单的策略**: 在测试中，启动一个并行的 `asyncio.task`，它监视 `d_out`，一旦有 Token，就手动设置 `reactor.shutdown_event.set()`。这模拟了外部观测系统决定任务完成并停止 Machine。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_machine_integration.py
~~~~~
~~~~~python.old
    # 3. Execute: Run the machine until it becomes idle
    await machine.run()

    # 4. Assert: Verify the final state
~~~~~
~~~~~python.new
    # 3. Execute: Run the machine until explicit shutdown
    # Since we removed idle-exit, we must simulate an external observer stopping the machine
    # when the result is ready.
    async def stop_when_done():
        while True:
            if memory.get_count("d_out") > 0:
                reactor.shutdown_event.set()
                break
            await asyncio.sleep(0.01)
    
    # Run observer and machine concurrently
    observer_task = asyncio.create_task(stop_when_done())
    await machine.run()
    await observer_task

    # 4. Assert: Verify the final state
~~~~~

### 下一步建议
VM 的生命周期现在由信号控制，更加健壮。
下一步，我们将执行 **Phase 3.5: 微观物理验证**。我们将编写针对 `Reactor` 的微观单元测试，覆盖信号处理、异常路由（Error Token）以及基本的物理激发规则，确保这些核心机制按预期工作。
(注意：Phase 3.4 错误流的一等公民化将在 Phase 3.5 的测试编写过程中一并实现，如果测试需要它的话)。
