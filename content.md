简要回答
我们正在处理两个关键的技术债务：实现真正的 `DRAIN` 优雅停机逻辑，以及集成系统级的 `ERROR` 信号处理。这将增强系统在生产环境中的可靠性和可观测性。

## [WIP] fix(runtime): 实现 DRAIN 优雅停机与系统级 ERROR 信号捕获

### 用户需求
1.  **`DRAIN` 信号实现**: 收到 `DRAIN` 信号时，系统不应立即停止，而应等待所有当前活动的计算任务完成（即系统达到静止状态）后再关闭。
2.  **系统级 `ERROR` 处理**: `Reactor` 和 `Machine` 应当捕获未处理的异常（如 `MemoryFullError`），将其转换为标准的 `SystemControlToken(ERROR)` 进行广播，并安全关闭系统。

### 评论
当前的 `DRAIN` 只是 `HALT` 的别名，这在生产环境中是不可接受的，因为它会丢失正在处理的数据。将其改为“等待静止 (Quiescence)”是标准的流处理模式。同时，将 Python 异常转换为系统内的控制流 Token，使得错误处理符合“物理场”的统一隐喻。

### 目标
1.  修改 `LocalComputeService` 以暴露 `active_count`。
2.  修改 `Reactor` 以支持 `drain_event` 状态，并在发生恐慌（Panic）时生成 `ERROR` Token。
3.  修改 `Machine` 以实现“DRAIN 时检测静止”的循环逻辑，并增加顶层异常捕获。
4.  添加集成测试验证上述行为。

### 基本原理
我们利用 `Machine` 作为协调者，因为它拥有 `Reactor`（物理状态）和 `ComputeService`（计算状态）的全局视图。
*   **DRAIN**: `Machine` 循环检查 `reactor.drain_event`。如果置位，它将轮询直到 `reactor.step() == 0` 且 `compute_service.active_count == 0` 且 `ingress_queue` 为空，确信系统完全静止后，才触发 `shutdown`。
*   **ERROR**: `Reactor.step()` 内的 `try...except` 块确保了内核级错误不会炸毁整个进程，而是转化为一个可被路由、观测的信号。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/runtime #task/object/lifecycle-signals #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 公开 `LocalComputeService.active_count`

我们需要让 Machine 能够查询当前正在运行的异步任务数量。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
        self._running = False
        self._active_count = 0

    def is_idle(self) -> bool:
        return self.inbound_queue.empty() and self._active_count == 0

    async def run(self) -> None:
~~~~~
~~~~~python.new
        self._running = False
        self._active_count = 0

    @property
    def active_count(self) -> int:
        return self._active_count

    def is_idle(self) -> bool:
        return self.inbound_queue.empty() and self._active_count == 0

    async def run(self) -> None:
~~~~~

#### Acts 2: 增强 `Reactor` 处理 DRAIN 和 ERROR

修改 `Reactor` 初始化 `drain_event`，更新信号处理逻辑，并在 `step` 中捕获异常。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
        # Lifecycle Signals
        self.shutdown_event = asyncio.Event()

        # State
        # node_id -> port_name -> list of callbacks
~~~~~
~~~~~python.new
        # Lifecycle Signals
        self.shutdown_event = asyncio.Event()
        self.drain_event = asyncio.Event()

        # State
        # node_id -> port_name -> list of callbacks
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
        # --- DIRECT DRIVE EXECUTION ---
        for node in nodes_to_fire:
            inputs = inputs_for_fire[node.id]
            try:
                # 1. Synchronous Execution
                func = self.function_map.get(node.id)
                if not func:
                    raise ValueError(f"No function mapped for node {node.id}")

                results = func(inputs, node, self.resource_registry)

                # 2. Immediate Result Handling
                self._handle_results_immediate(node, results)

            except Exception as e:
                logger.exception(f"Kernel panic at node '{node.id}': {e}")
                # TODO: In v3.2, implement exception tokens for fault tolerance.
                # For now, we log and suppress to keep the reactor alive.

        return len(nodes_to_fire)

    def _handle_results_immediate(
~~~~~
~~~~~python.new
        # --- DIRECT DRIVE EXECUTION ---
        for node in nodes_to_fire:
            inputs = inputs_for_fire[node.id]
            try:
                # 1. Synchronous Execution
                func = self.function_map.get(node.id)
                if not func:
                    raise ValueError(f"No function mapped for node {node.id}")

                results = func(inputs, node, self.resource_registry)

                # 2. Immediate Result Handling
                self._handle_results_immediate(node, results)

            except Exception as e:
                logger.exception(f"Kernel panic at node '{node.id}': {e}")
                # Upgrade kernel panic to System Error Signal
                self._handle_control_signal(
                    SystemControlToken(command=ControlCommand.ERROR, payload=e)
                )

        return len(nodes_to_fire)

    def _handle_results_immediate(
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
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
~~~~~python.new
    def _handle_control_signal(self, ctrl: SystemControlToken) -> None:
        logger.info(f"Reactor received control signal: {ctrl.command}")
        if ctrl.command == ControlCommand.HALT:
            self.shutdown_event.set()
        elif ctrl.command == ControlCommand.DRAIN:
            logger.info("DRAIN signal received. System entering draining mode.")
            self.drain_event.set()
        elif ctrl.command == ControlCommand.ERROR:
            logger.error(f"System Critical Error: {ctrl.payload}")
            self.shutdown_event.set()
~~~~~

#### Acts 3: 升级 `Machine` 循环逻辑

实现 DRAIN 状态下的静止检测，并增加顶层异常防护。

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
~~~~~
~~~~~python.new
    async def run(self) -> None:
        logger.info("Machine started.")

        # Start the Compute Service
        service_task = asyncio.create_task(self.compute_service.run())

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
                        if (
                            fired_count == 0
                            and self.compute_service.active_count == 0
                            and self.ingress_queue.empty()
                        ):
                            logger.info("System drained (Quiescent). Shutting down.")
                            self.reactor.shutdown_event.set()
                            continue

                    # 3. Adaptive Throttling
                    if fired_count > 0:
                        await asyncio.sleep(0)
                    else:
                        if not self.ingress_queue.empty():
                            await asyncio.sleep(0)
                        else:
                            await asyncio.sleep(0.001)

                except Exception as e:
                    logger.critical(f"Machine loop crashed: {e}", exc_info=True)
                    # Force shutdown on machine loop crash
                    self.reactor.shutdown_event.set()

            logger.info("Machine shutdown signal received.")

        finally:
~~~~~

#### Acts 4: 添加测试用例

创建一个新的测试文件 `tests/integration/test_lifecycle_signals.py` 来验证 DRAIN 和 ERROR 行为。

~~~~~act
write_file
packages/cascade-vm/tests/integration/test_lifecycle_signals.py
~~~~~
~~~~~python
import asyncio
import pytest
from typing import Dict, Tuple

from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode, Token
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.runtime.storage import InMemoryObjectStore

# --- DRAIN Test Helpers ---

async def slow_worker_func(n: int) -> int:
    # Sleeps to ensure DRAIN signal arrives while task is active
    await asyncio.sleep(0.1)
    return n * n

def drain_trigger_kernel(inputs, node, resources):
    # Emits a DRAIN signal immediately
    return {"out": Token(payload=SystemControlToken(ControlCommand.DRAIN))}

def mock_dispatcher_kernel(inputs, node, resources):
    # Dispatches the slow task
    compute_queue = resources.get("system.compute_queue")
    input_val = inputs["in"].payload # Assumed Ref for simplicity in full stack, but here we can cheat for micro-test
    # We construct a fake request just to trigger the service
    req = ComputeRequest(
        code_hash="slow_task",
        input_refs={}, # Ignored by our registry mock wrapper below
        reply_to_nid="D_out",
        trace={}
    )
    compute_queue.put_nowait(req)
    return {}

# --- ERROR Test Helpers ---

def crashing_kernel(inputs, node, resources):
    raise ValueError("Intentional Kernel Panic")

# --- Fixtures ---

@pytest.fixture
def machine_components():
    memory = VolatileMemory()
    object_store = InMemoryObjectStore()
    compute_queue = asyncio.Queue()
    ingress_queue = asyncio.Queue()
    
    code_registry = CodeRegistry()
    # Mocking execution to skip Ref resolution complexity for this specific test
    # We intercept the _process_request in a real integration, or just ensure 
    # the service's registry call works.
    # Let's use the real service but trick the registry.
    code_registry.register("slow_task", slow_worker_func)

    resource_registry = ResourceRegistry()
    resource_registry.register("system.object_store", object_store)
    resource_registry.register("system.compute_queue", compute_queue)

    compute_service = LocalComputeService(
        store=object_store,
        registry=code_registry,
        inbound_queue=compute_queue,
        outbound_queue=ingress_queue
    )

    return memory, resource_registry, ingress_queue, compute_service

# --- Tests ---

@pytest.mark.asyncio
async def test_drain_waits_for_active_task(machine_components):
    memory, resource_registry, ingress_queue, compute_service = machine_components
    
    # Topology: 
    # 1. D_start -> F_launch (starts slow task) -> D_out
    # 2. D_drain -> F_drain (sends DRAIN)
    
    d_start = PhysicsDataNode(id="D_start", name="Start")
    d_out = PhysicsDataNode(id="D_out", name="Out")
    f_launch = PhysicsFuncNode(id="F_launch", name="Launch", input_ports={"in": PortDef("in", PortRole.DATA)})
    
    d_drain = PhysicsDataNode(id="D_drain", name="DrainTrigger")
    f_drain = PhysicsFuncNode(id="F_drain", name="Drainer", input_ports={"in": PortDef("in", PortRole.DATA)})
    # F_drain output is intercepted by Reactor, no target D needed
    
    graph = BipartiteGraph()
    for n in [d_start, d_out, f_launch, d_drain, f_drain]:
        graph.nodes[n.id] = n
        
    graph.channels.append(Channel("D_start", "out", "F_launch", "in"))
    graph.channels.append(Channel("D_drain", "out", "F_drain", "in"))
    
    func_map = {
        "F_launch": mock_dispatcher_kernel,
        "F_drain": drain_trigger_kernel
    }
    
    reactor = Reactor(graph, memory, func_map, resource_registry, ingress_queue)
    machine = Machine(reactor, compute_service, ingress_queue)
    
    # Inject inputs
    memory.put(d_start, Token(payload="go"))
    memory.put(d_drain, Token(payload="stop"))
    
    # Run
    # The machine should:
    # 1. Fire F_launch (starts slow task in background)
    # 2. Fire F_drain (sets DRAIN flag)
    # 3. Wait approx 0.1s for slow task to finish
    # 4. Process result in D_out
    # 5. Detect Quiescence -> Shutdown
    
    await asyncio.wait_for(machine.run(), timeout=1.0)
    
    # Assertions
    assert memory.get_count("D_out") == 1
    assert reactor.shutdown_event.is_set()
    assert reactor.drain_event.is_set()


@pytest.mark.asyncio
async def test_error_signal_shuts_down_machine(machine_components):
    memory, resource_registry, ingress_queue, compute_service = machine_components
    
    d_err = PhysicsDataNode(id="D_err", name="ErrTrigger")
    f_crash = PhysicsFuncNode(id="F_crash", name="Crasher", input_ports={"in": PortDef("in", PortRole.DATA)})
    
    graph = BipartiteGraph()
    graph.nodes[d_err.id] = d_err
    graph.nodes[f_crash.id] = f_crash
    graph.channels.append(Channel("D_err", "out", "F_crash", "in"))
    
    func_map = { "F_crash": crashing_kernel }
    
    reactor = Reactor(graph, memory, func_map, resource_registry, ingress_queue)
    machine = Machine(reactor, compute_service, ingress_queue)
    
    memory.put(d_err, Token("die"))
    
    await asyncio.wait_for(machine.run(), timeout=1.0)
    
    assert reactor.shutdown_event.is_set()
    # The system should have stopped cleanly despite the exception
~~~~~

### 下一步建议
我们已经完成了 DRAIN 信号和 ERROR 信号的核心支持。

下一步应该：
1.  **实现 `SystemControlToken` 的专用通道**：目前控制 Token 是混在普通数据通道中返回的，这依赖于 `Reactor` 检查每一个输出。为了性能和清晰度，应该考虑引入专用的控制端口或总线。
2.  **实现 `F_retry` 逻辑**：现在错误虽然被捕获了，但导致了系统关闭。我们需要一个能消费 ERROR 信号并决定是否重试的节点。
3.  **完善 `Manifest`**：解决编译产物缺失 Entry Point 和 Exit Point 映射的问题。

建议继续执行：**完善 CompilationManifest 的内容**。
---
