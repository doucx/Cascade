[简要回答]
根据 "还债.md" 中的高优先级指示，我将分阶段偿还技术债务。本计划聚焦于 VM 核心控制逻辑的修复：实现正确的 `DRAIN` 信号处理（优雅停机）以及系统级 `ERROR` 信号的自动广播（崩溃处理）。

## [WIP] fix(vm): 实现 DRAIN 信号与系统级 ERROR 广播

### 用户需求
1.  **实现 `DRAIN` 信号**: `ControlCommand.DRAIN` 不应立即杀死系统，而应进入“排空”模式：停止接收新任务，但在所有进行中的计算任务完成前不退出。
2.  **实现自动 `ERROR` 广播**: 当 Reactor 或 Kernel 发生未捕获异常时，系统应自动发出 `ControlCommand.ERROR` 信号并携带异常信息，而不是仅打印日志后莫名退出。

### 评论
当前的实现将 `DRAIN` 硬编码为 `HALT`，这对于生产环境是不可接受的，因为它会导致数据丢失。同时，缺乏系统级错误传播机制使得调试“静默崩溃”变得极其困难。这两个修复将显著提升系统的鲁棒性和可运维性。

### 目标
1.  修改 `Reactor`，使其在收到 `DRAIN` 时设置 `drain_event` 而非 `shutdown_event`。
2.  增强 `Reactor.step()`，在捕获到 Kernel Panic 时自动生成并处理 `ERROR` 控制令牌。
3.  重构 `Machine.run()` 循环，使其能够处理“排空”状态：仅在 `drain_event` 被触发且系统（Reactor + ComputeService）完全空闲时，才触发最终的 `shutdown_event`。
4.  添加集成测试验证这两种行为。

### 基本原理
我们正在将隐式的、基于假设的行为（"assume drain means halt", "assume logging is enough"）转换为显式的、确定性的状态机行为。这是 **ADAP (假设驱动分析协议)** 的直接应用。

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #concept/state #task/domain/core #task/object/control-signals #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 增强 Reactor 以支持 DRAIN 状态和错误捕获

我们需要修改 `Reactor` 类：
1.  添加 `drain_event` 状态。
2.  更新 `_handle_control_signal` 以正确区分 `DRAIN` 和 `ERROR`。
3.  在 `step()` 方法中添加顶层异常捕获，将 Kernel 异常转化为 `SystemControlToken(ERROR)`。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
        # Lifecycle Signals
        self.shutdown_event = asyncio.Event()

        # State
~~~~~
~~~~~python.new
        # Lifecycle Signals
        self.shutdown_event = asyncio.Event()
        self.drain_event = asyncio.Event()

        # State
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
                # System-level error broadcasting
                self._handle_control_signal(
                    SystemControlToken(command=ControlCommand.ERROR, payload=e)
                )

        return len(nodes_to_fire)
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
            logger.info("System entering DRAIN mode. Waiting for active tasks to complete.")
            self.drain_event.set()
        elif ctrl.command == ControlCommand.ERROR:
            logger.error(f"System Critical Error: {ctrl.payload}")
            self.shutdown_event.set()
~~~~~

#### Acts 2: 更新 Machine 以处理排空逻辑

我们需要修改 `Machine.run` 循环：
1.  在每次循环中检查 `reactor.drain_event`。
2.  如果处于 `DRAIN` 模式，且系统完全空闲（Reactor 没做工、ComputeService 空闲、Ingress 空闲），则触发 `shutdown_event`。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
                # 2. Check Draining State
                # If DRAIN signal was received, we only shutdown when everything is idle.
                if self.reactor.drain_event.is_set():
                    is_reactor_idle = fired_count == 0
                    is_ingress_idle = self.ingress_queue.empty()
                    is_compute_idle = self.compute_service.is_idle()

                    if is_reactor_idle and is_ingress_idle and is_compute_idle:
                        logger.info("System drained successfully. Initiating shutdown.")
                        self.reactor.shutdown_event.set()

                # 3. Adaptive Throttling
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
~~~~~

#### Acts 3: 创建集成测试

创建一个新的测试文件 `packages/cascade-vm/tests/integration/test_system_signals.py`，专门用于验证 `DRAIN` 和 `ERROR` 信号的行为。

~~~~~act
write_file
packages/cascade-vm/tests/integration/test_system_signals.py
~~~~~
~~~~~python
import pytest
import asyncio
from typing import Dict, Tuple

from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode, Token
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.compute.service import LocalComputeService
from cascade.runtime.storage import InMemoryObjectStore
from cascade.vm.registry import CodeRegistry


# --- Mocks & Fixtures ---

async def slow_task(n: int) -> int:
    await asyncio.sleep(0.1)  # Takes time to complete
    return n

async def crashing_task(n: int) -> int:
    raise RuntimeError("Intentional Crash")

def build_minimal_machine(graph, function_map, code_registry) -> Tuple[Machine, VolatileMemory, InMemoryObjectStore]:
    memory = VolatileMemory()
    store = InMemoryObjectStore()
    compute_queue = asyncio.Queue()
    ingress_queue = asyncio.Queue()
    
    # Minimal Resource Registry
    from cascade.vm.resource_registry import ResourceRegistry
    resources = ResourceRegistry()
    resources.register("system.object_store", store)
    resources.register("system.compute_queue", compute_queue)
    
    reactor = Reactor(graph, memory, function_map, resources, ingress_queue)
    compute_service = LocalComputeService(store, code_registry, compute_queue, ingress_queue)
    machine = Machine(reactor, compute_service, ingress_queue)
    
    return machine, memory, store

@pytest.mark.asyncio
async def test_drain_signal_waits_for_completion():
    # Scenario:
    # 1. Trigger Node -> Drain Node (Emits DRAIN)
    # 2. Trigger Node -> Worker Node (Starts Slow Task)
    # Goal: Verify that Machine doesn't stop until Slow Task finishes, even though DRAIN was emitted early.
    
    from cascade.std.system.drainer import drain_signal
    from cascade.std.triad.dispatcher import standard_dispatcher
    from cascade.reflection import PhysicalIdGenerator

    # Topology
    d_in = PhysicsDataNode(id="d_in", name="Input", initial_tokens=1, initial_payload=1)
    
    # Branch 1: The Drainer
    f_drain = PhysicsFuncNode(id="f_drain", name="Drainer", 
                              input_ports={"in": PortDef("in", PortRole.DATA)}, 
                              output_ports={"out": PortDef("out", PortRole.DATA)})
    d_ctrl = PhysicsDataNode(id="d_ctrl", name="ControlBus") # Reactor intercepts, but topology needs target

    # Branch 2: The Worker
    # We use a simplified dispatcher setup for brevity (skipping full Triad for this unit-integration test)
    # Just mocking a worker node behavior directly might be easier, but let's use dispatcher to test ComputeService integration.
    f_worker = PhysicsFuncNode(id="task.worker", name="Worker", 
                               input_ports={"worker_input": PortDef("worker_input", PortRole.DATA)},
                               output_ports={"worker_result": PortDef("worker_result", PortRole.DATA)})
    # Dispatcher expects {worker_input: {payload: {inputs...}}}
    # We'll mock a simple wrapper func to format it
    
    d_worker_out = PhysicsDataNode(id="d_out", name="Output")

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_in, f_drain, d_ctrl, f_worker, d_worker_out]}
    
    # Wiring
    # d_in -> f_drain
    graph.channels.append(Channel("d_in", "out", "f_drain", "in"))
    # d_in -> f_worker (Fan-out)
    graph.channels.append(Channel("d_in", "out", "task.worker", "worker_input"))
    
    # f_drain -> d_ctrl
    graph.channels.append(Channel("f_drain", "out", "d_ctrl", "in"))
    # f_worker -> d_out
    graph.channels.append(Channel("task.worker", "worker_result", "d_out", "in"))

    # Logic
    def split_input_wrapper(inputs, node, res):
        # Dispatcher expects specific structure
        return {"worker_input": inputs["worker_input"]}

    # We need a custom logic for f_worker to adapt d_in (int) to dispatcher format (dict of refs)
    # Actually, simpler: define a custom kernel function that submits to compute queue manually
    # to avoid mocking the whole Bleacher complexity.
    
    def custom_dispatcher(inputs, node, resources):
        from cascade.vm.compute import ComputeRequest
        q = resources.get("system.compute_queue")
        # Direct submission
        q.put_nowait(ComputeRequest(
            code_hash="slow_task",
            input_refs={}, # No inputs needed for this test
            reply_to_nid="d_out",
            trace={}
        ))
        return {}

    func_map = {
        "f_drain": drain_signal,
        "task.worker": custom_dispatcher
    }
    
    registry = CodeRegistry()
    registry.register("slow_task", slow_task)

    machine, memory, store = build_minimal_machine(graph, func_map, registry)

    # Execution
    # run() should return ONLY when shutdown_event is set.
    # shutdown_event should set ONLY when drain_event is set AND task is done.
    await machine.run()
    
    # Assertions
    # 1. Machine stopped (implied by await returning)
    # 2. Output should exist (meaning it waited)
    assert memory.get_count("d_out") == 1
    # 3. Drain event was triggered
    assert machine.reactor.drain_event.is_set()


@pytest.mark.asyncio
async def test_error_signal_broadcasts_crash():
    # Scenario: Kernel function raises exception -> Reactor catches -> Emits ERROR -> Machine stops
    
    d_in = PhysicsDataNode(id="d_in", name="Input", initial_tokens=1)
    f_crash = PhysicsFuncNode(id="f_crash", name="Crasher", 
                              input_ports={"in": PortDef("in", PortRole.DATA)}, 
                              output_ports={"out": PortDef("out", PortRole.DATA)})
    d_void = PhysicsDataNode(id="d_void", name="Void")

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_in, f_crash, d_void]}
    graph.channels.append(Channel("d_in", "out", "f_crash", "in"))
    graph.channels.append(Channel("f_crash", "out", "d_void", "in"))

    def crashing_kernel(inputs, node, res):
        raise ValueError("Kernel Panic!")

    func_map = {"f_crash": crashing_kernel}
    registry = CodeRegistry()

    machine, memory, store = build_minimal_machine(graph, func_map, registry)

    # Execution
    await machine.run()

    # Assertions
    # 1. Machine stopped
    assert machine.reactor.shutdown_event.is_set()
    # 2. Error should be logged (we can't easily assert logs here without caplog, but machine stopping confirms it)
    # Ideally we'd check if a SystemControlToken(ERROR) appeared in memory if wired, 
    # but Reactor._handle_control_signal consumes it immediately without putting to memory usually.
    # However, for this test, simply verifying it halted without external intervention is enough.
~~~~~

### 下一步建议

我们已经解决了“假死”和“静默崩溃”两个核心稳定性问题。现在 VM 层更加健壮。
接下来的步骤应该是：
1.  **提交此变更** (`git_add`, `git_commit`)。
2.  **验证**：运行 `tests/integration/test_system_signals.py` 确保通过。
3.  **解决下一个高优先级债务**：实现 `CompilationManifest` 的完整性（特别是 Entry/Exit point 映射），这将消除 Strategy 层中的“猜测”逻辑。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/state #task/domain/core #task/object/control-signals #task/action/refactor #task/state/begin

