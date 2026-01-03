# [WIP] test(vm): 实现基于事件驱动的测试框架 EventDrivenRunner

## 摘要头

### 用户需求
构建一个测试辅助工具（Harness），用于替代目前脆弱的“数步数”(`await reactor.step()`) 测试模式。该工具应允许测试用例通过等待特定的**语义事件**（如 `TaskCompleted`, `ResourceAllocated`）来驱动测试流程。

### 评论
你关于 `cascade.common.messaging.bus` 的疑虑是完全正确的。目前的 `MessageBus` 是设计用于**用户界面渲染 (UI Rendering)** 的，它处理的是“国际化字符串”和“日志级别”。

将核心测试建立在 `MessageBus` 上是错误的，原因如下：
1.  **类型丢失**: 它传递的是 `**kwargs` 和 `msg_id` 字符串，而不是强类型的 Event 对象。
2.  **关注点分离**: `MessageBus` 是给人类看的（Output），测试需要的是机器可读的遥测数据（Telemetry）。
3.  **层级倒置**: 物理引擎 (`VM`) 不应该依赖于上层的 UI 库 (`common`).

因此，我们不需要修改 `common`，而是需要在测试套件中利用 `F_obs` (观察者节点) 的机制。`F_obs` 已经在设计上支持将 `ObservedEvent` 推送到一个 `asyncio.Queue`。我们的 `EventDrivenRunner` 只需要消费这个队列即可。

### 目标
1.  在 `cascade-vm` 中创建一个新的测试工具类 `EventDrivenRunner`。
2.  实现 `wait_for_event(predicate, timeout)` 方法。
3.  重构一个现有的测试用例（如 `ping_pong`）来演示这种新模式。

### 基本原理
利用 `cascade-std` 中已有的 `standard_observer` 和 `ObservedEvent`。通过 `functools.partial` 将一个测试专用的 `asyncio.Queue` 注入到 `F_obs` 的运行时实现中。这样，测试主线程就可以像读取日志流一样读取物理引擎的内部状态变化，从而实现精确的同步。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/harness #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 创建 EventDrivenRunner

我们在 `cascade-vm` 的测试工具集里创建这个新类。它封装了 Reactor 的初始化、启动和事件监听逻辑。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/test_harness.py
~~~~~
~~~~~python
import asyncio
import logging
from typing import Dict, Any, Callable, TypeVar, Optional, List
from functools import partial

from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import Token, PhysicsDataNode
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.std.triad.observer import standard_observer, ObservedEvent

logger = logging.getLogger(__name__)

T = TypeVar("T")


class EventTimeoutError(TimeoutError):
    pass


class EventDrivenRunner:
    def __init__(
        self,
        graph: BipartiteGraph,
        function_map: Dict[str, Callable],
    ):
        self.graph = graph
        self.memory = VolatileMemory()
        self.executor = PhysicsExecutor()
        
        # 1. Setup Observability Queue
        self.event_queue: asyncio.Queue[ObservedEvent] = asyncio.Queue()
        self._captured_events: List[ObservedEvent] = []
        
        # 2. Inject standard_observer with our queue
        # We look for the observer node in the graph (by convention ID)
        # or we rely on the user passing the map.
        # Here, we wrap the provided function_map to inject the queue into the observer.
        self.function_map = function_map.copy()
        
        # Auto-detect and bind observer if present in map
        obs_id = "global.observability.observer"
        if obs_id in self.function_map:
            # We assume the user passed the standard_observer function
            # We replace it with a partial that has 'queue' bound
            self.function_map[obs_id] = partial(standard_observer, queue=self.event_queue)

        self.reactor = Reactor(
            self.graph, self.memory, self.executor, self.function_map
        )
        self._loop_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def prime(self):
        self.reactor.prime()

    async def start_loop(self):
        """Starts the reactor loop in the background."""
        if self._loop_task:
            return
        self._stop_event.clear()
        self._loop_task = asyncio.create_task(self._run_loop())

    async def _run_loop(self):
        logger.info("Reactor loop started.")
        try:
            while not self._stop_event.is_set():
                fired = await self.reactor.step()
                if fired == 0:
                    # Avoid busy loop if idle
                    await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception("Reactor loop crashed")
            raise e

    async def stop_loop(self):
        if self._loop_task:
            self._stop_event.set()
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None

    def inject_input(self, node_id: str, payload: Any):
        """Helper to inject data into a node."""
        node = self.graph.nodes[node_id]
        if not isinstance(node, PhysicsDataNode):
            raise ValueError(f"Node {node_id} is not a DataNode")
        self.memory.put(node, Token(payload=payload))

    async def wait_for_event(
        self,
        predicate: Callable[[ObservedEvent], bool],
        timeout: float = 1.0,
    ) -> ObservedEvent:
        """
        Waits until an event matching the predicate arrives.
        Captures all intermediate events.
        """
        start_time = asyncio.get_event_loop().time()
        
        while True:
            # Check timeout
            now = asyncio.get_event_loop().time()
            if now - start_time > timeout:
                raise EventTimeoutError(f"Timed out waiting for event after {timeout}s")
            
            # Wait for next event
            try:
                # Calculate remaining time
                remaining = timeout - (now - start_time)
                event = await asyncio.wait_for(self.event_queue.get(), timeout=remaining)
                self._captured_events.append(event)
                
                if predicate(event):
                    return event
            except asyncio.TimeoutError:
                 raise EventTimeoutError(f"Timed out waiting for event after {timeout}s")

    async def run_until_complete(self, task_id: str, timeout: float = 2.0) -> ObservedEvent:
        """
        Convenience method to wait for a specific task to complete (End event).
        """
        def is_completion(e: ObservedEvent):
            return (
                e.event_type == "end" 
                and e.trace_data.get("id") == task_id
            )
        
        return await self.wait_for_event(is_completion, timeout=timeout)
~~~~~

#### Acts 2: 验证新模式 (Refactor Ping Pong Test)

我们将重写 `test_ping_pong.py`，使用 `EventDrivenRunner`。注意我们必须手动添加 Observer 基础设施，因为这是一个单元测试，没有 Compiler 帮我们自动生成。

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_reactor_independent_nodes():
    d1 = PhysicsDataNode(id="D1", name="In1")
    f1 = PhysicsFuncNode(
        id="F1",
        name="Proc1",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )

    d2 = PhysicsDataNode(id="D2", name="In2")
    f2 = PhysicsFuncNode(
        id="F2",
        name="Proc2",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, f1, d2, f2]}
    graph.channels.append(Channel(d1.id, "out", f1.id, target_port="in"))
    graph.channels.append(Channel(d2.id, "out", f2.id, target_port="in"))

    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f1.id: noop, f2.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)

    memory.put(d1, Token("A"))
    memory.put(d2, Token("B"))

    fired_count = await reactor.step()

    assert fired_count == 2
    assert memory.get_count(d1.id) == 0
    assert memory.get_count(d2.id) == 0
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_reactor_independent_nodes():
    d1 = PhysicsDataNode(id="D1", name="In1")
    f1 = PhysicsFuncNode(
        id="F1",
        name="Proc1",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )

    d2 = PhysicsDataNode(id="D2", name="In2")
    f2 = PhysicsFuncNode(
        id="F2",
        name="Proc2",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, f1, d2, f2]}
    graph.channels.append(Channel(d1.id, "out", f1.id, target_port="in"))
    graph.channels.append(Channel(d2.id, "out", f2.id, target_port="in"))

    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f1.id: noop, f2.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)

    memory.put(d1, Token("A"))
    memory.put(d2, Token("B"))

    fired_count = await reactor.step()

    assert fired_count == 2
    assert memory.get_count(d1.id) == 0
    assert memory.get_count(d2.id) == 0


# --- New Test demonstrating EventDrivenRunner ---

from cascade.vm.test_harness import EventDrivenRunner
from cascade.spec.triad import ObservabilityNode
from cascade.std.triad.observer import standard_observer
import sys

@pytest.mark.asyncio
async def test_event_driven_ping_pong():
    # 1. Topology with Observability
    d1 = PhysicsDataNode(id="D1", name="Input")
    f1 = PhysicsFuncNode(
        id="F1",
        name="Increment",
        input_ports={"value": PortDef("value", PortRole.DATA)},
        output_ports={
            "result": PortDef("result", PortRole.DATA),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY) # Added Obs port
        },
    )
    d2 = PhysicsDataNode(id="D2", name="Output")
    
    # Obs Infra
    d_life = PhysicsDataNode(id="global.observability.bus", name="Bus", capacity=sys.maxsize)
    f_obs = ObservabilityNode(
        id="global.observability.observer",
        name="Observer",
        input_ports={"event_token": PortDef("event_token", PortRole.OBSERVABILITY)}
    )

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, f1, d2, d_life, f_obs]}
    
    # Logic Wiring
    graph.channels.append(Channel(d1.id, "out", f1.id, "value"))
    graph.channels.append(Channel(f1.id, "result", d2.id, "in"))
    
    # Obs Wiring
    # F1 emits directly to Bus (Simulating a Bleacher/Stainer behavior roughly)
    graph.channels.append(Channel(f1.id, "obs_output", d_life.id, "in"))
    graph.channels.append(Channel(d_life.id, "out", f_obs.id, "event_token"))

    # Function Map
    def obs_enabled_logic(inputs, node):
        val = inputs["value"].payload
        # Emit Result AND Observation
        return {
            "result": Token(payload=val + 1),
            "obs_output": Token(payload=None, trace={"id": "F1", "status": "done"})
        }

    func_map = {
        "F1": obs_enabled_logic,
        "global.observability.observer": standard_observer # Runner will auto-inject queue
    }

    # 2. Use Runner
    runner = EventDrivenRunner(graph, func_map)
    runner.inject_input("D1", 10)

    # 3. Start & Wait
    await runner.start_loop()
    
    try:
        # We wait for the specific event proving F1 finished
        event = await runner.wait_for_event(
            lambda e: e.trace_data.get("id") == "F1" and e.trace_data.get("status") == "done"
        )
        assert event is not None
        
        # Verify physical side effect (Memory)
        assert runner.memory.get_count("D2") == 1
        assert runner.memory.take("D2").payload == 11
        
    finally:
        await runner.stop_loop()
~~~~~

### 下一步建议
我们现在拥有了 `WiringHarness`（构建时验证）和 `EventDrivenRunner`（白盒测试工具）。

接下来的逻辑步骤是：
1.  **整合验证**: 编写一个使用 `WiringHarness` 构建图，并使用 `EventDrivenRunner` 运行的完整测试用例，确保这两个新工具能协同工作。
2.  **图可视化**: 实施之前计划中的 `GraphDumper` 增强，让我们能直观地看到 `WiringHarness` 生成的图是否正确。
3.  **返回主线**: 回到主线任务 "Phase 5"，使用这些新工具来重新验证 `cascade-compiler` 生成的复杂图（包含 Brokers 和 Probes）。
