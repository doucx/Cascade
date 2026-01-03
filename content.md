好的，我完全理解。

这个重构是实现**“图与环境的绝对分离”**这一核心愿景的关键一步，完全符合我们在《统一上下文与资源管理路线图》中定义的**阶段 2** 目标。我们将用一个明确的、基于引用的依赖注入框架来彻底取代当前通过 `functools.partial` 将环境“偷渡”到图内部的模式。

我将生成一个计划，精确地执行这个重构。

## [WIP] refactor: 使用 ResourceRegistry 为 EventDrivenRunner 注入队列

### 用户需求
重构 `EventDrivenRunner`，使其不再使用 `functools.partial` 来向 `standard_observer` 注入 `event_queue`。取而代之，`EventDrivenRunner` 应在其内部创建一个 `ResourceRegistry`，将队列以 `"system.observer.queue"` 为 ID 注册进去，并改造 `standard_observer` 以通过 `resources.get()` 来获取该队列。

### 评论
这是一个至关重要的架构改进。它用一个声明式的、透明的资源查找机制，取代了之前命令式的、隐晦的 `partial` 注入魔法。这使得 `standard_observer` 这样的物理函数变得更加纯粹和可移植，因为它只依赖于一个标准的 `resources` 接口，而不再关心队列是如何被创建或传递的。此举也为未来统一所有运行时上下文（参数、资源、配置）奠定了坚实的基础。

### 目标
1.  修改 `Reactor._execute_task` 的核心调用逻辑，使其向所有物理函数统一传递 `(inputs, node, resources)` 三个参数。
2.  重构 `EventDrivenRunner`，在其 `__init__` 方法中创建 `ResourceRegistry`，注册 `event_queue`，并将其传递给 `Reactor`。
3.  重构 `standard_observer`，使其函数签名符合新的三参数协议，并从 `resources` 参数中获取队列。
4.  修复 `test_event_driven_ping_pong` 测试，使其遵循新的、无 `partial` 的设置流程。

### 基本原理
我们将遵循路线图中的计划。首先，通过修改 `Reactor` 来升级物理函数的调用契约，使其普遍具备访问资源注册表的能力。然后，我们将 `EventDrivenRunner` 定位为 `ResourceRegistry` 的所有者和配置者，它负责创建实例并注册核心资源（在此场景中是 `event_queue`）。`Reactor` 在初始化时接收这个注册表，并在执行循环中将其作为第三个参数传递给所有函数节点。最后，`standard_observer` 作为消费者，利用这个新参数通过一个稳定的 ID 来查找它所依赖的队列，从而完成解耦。

### 标签
#intent/refine #flow/ready #priority/high #comp/vm #comp/tests #concept/executor #scope/dx #ai/instruct #task/domain/architecture #task/object/dependency-injection #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 升级 VM 核心调用契约

首先，我们将修改 `Reactor` 的 `_execute_task` 方法，使其在调用物理函数时，除了 `inputs` 和 `node`，还传递 `self.resource_registry`。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
            if inspect.iscoroutinefunction(func):
                result_tokens = await func(input_data, node, self.resource_registry)
            else:
                result_tokens = await self.executor.submit(
                    func, (input_data, node, self.resource_registry)
                )
~~~~~
~~~~~python.new
            # The new standard signature for all physical functions is (inputs, node, resources)
            if inspect.iscoroutinefunction(func):
                result_tokens = await func(input_data, node, self.resource_registry)
            else:
                result_tokens = await self.executor.submit(
                    func, (input_data, node, self.resource_registry)
                )
~~~~~

#### Acts 2: 重构 `standard_observer` 以使用新契约

现在，我们更新 `standard_observer`，使其从新的 `resources` 参数中获取队列，而不是从 `kwargs` 中。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/observer.py
~~~~~
~~~~~python.old
async def standard_observer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any, *, queue: Queue
) -> None:
    event_token = inputs["event_token"]
    trace = event_token.trace

    # Determine event type based on the presence of 'end_ts', which is only
    # added by the Stainer node at the end of a lifecycle.
    event_type = "end" if "end_ts" in trace else "start"

    event = ObservedEvent(event_type=event_type, trace_data=trace)
    await queue.put(event)
~~~~~
~~~~~python.new
async def standard_observer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # 1. Get queue from the resource registry
    # In a real run, this would be a proper ResourceRegistry instance.
    # In tests, it might be a mock or a simple dict-like object.
    queue = resources.get("system.observer.queue")

    event_token = inputs["event_token"]
    trace = event_token.trace

    # Determine event type based on the presence of 'end_ts', which is only
    # added by the Stainer node at the end of a lifecycle.
    event_type = "end" if "end_ts" in trace else "start"

    event = ObservedEvent(event_type=event_type, trace_data=trace)
    await queue.put(event)

    # Observers do not return tokens into the graph
    return {}
~~~~~

#### Acts 3: 重构 `EventDrivenRunner` 以提供资源

这是核心修改。我们将重写 `EventDrivenRunner`，移除 `partial` 逻辑，并引入 `ResourceRegistry`。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python
import asyncio
import logging
from typing import Dict, Any, Callable, TypeVar, Optional, List

from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import Token, PhysicsDataNode
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.resource_registry import ResourceRegistry
from cascade.std.triad.observer import ObservedEvent

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

        # 1. Setup Resource Registry and Observability Queue
        self.event_queue: asyncio.Queue[ObservedEvent] = asyncio.Queue()
        self._captured_events: List[ObservedEvent] = []
        self.resource_registry = ResourceRegistry()
        self.resource_registry.register("system.observer.queue", self.event_queue)

        # 2. The function map is now used directly
        self.function_map = function_map

        # 3. Inject the registry into the Reactor
        self.reactor = Reactor(
            self.graph,
            self.memory,
            self.executor,
            self.function_map,
            self.resource_registry,
        )
        self._loop_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def prime(self):
        self.reactor.prime()

    async def start_loop(self):
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
        node = self.graph.nodes[node_id]
        if not isinstance(node, PhysicsDataNode):
            raise ValueError(f"Node {node_id} is not a DataNode")
        self.memory.put(node, Token(payload=payload))

    async def wait_for_event(
        self,
        predicate: Callable[[ObservedEvent], bool],
        timeout: float = 1.0,
    ) -> ObservedEvent:
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
                event = await asyncio.wait_for(
                    self.event_queue.get(), timeout=remaining
                )
                self._captured_events.append(event)

                if predicate(event):
                    return event
            except asyncio.TimeoutError:
                raise EventTimeoutError(f"Timed out waiting for event after {timeout}s")

    async def run_until_complete(
        self, task_id: str, timeout: float = 2.0
    ) -> ObservedEvent:

        def is_completion(e: ObservedEvent):
            return e.event_type == "end" and e.trace_data.get("id") == task_id

        return await self.wait_for_event(is_completion, timeout=timeout)
~~~~~

#### Acts 4: 更新测试用例以验证新模型

最后，我们更新 `test_event_driven_ping_pong` 测试，移除所有 `partial` 相关的设置，使其直接使用新的、更简洁的 `EventDrivenRunner` API。

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
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
            "obs_output": PortDef(
                "obs_output", PortRole.OBSERVABILITY
            ),  # Added Obs port
        },
    )
    d2 = PhysicsDataNode(id="D2", name="Output")

    # Obs Infra
    d_life = PhysicsDataNode(
        id="global.observability.bus", name="Bus", capacity=sys.maxsize
    )
    f_obs = ObservabilityNode(
        id="global.observability.observer",
        name="Observer",
        input_ports={"event_token": PortDef("event_token", PortRole.OBSERVABILITY)},
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
    def obs_enabled_logic(inputs, node, resources):
        val = inputs["value"].payload
        # Emit Result AND Observation
        return {
            "result": Token(payload=val + 1),
            "obs_output": Token(payload=None, trace={"id": "F1", "status": "done"}),
        }

    func_map = {
        "F1": obs_enabled_logic,
        "global.observability.observer": standard_observer,  # Runner will auto-inject queue
    }

    # 2. Use Runner
    runner = EventDrivenRunner(graph, func_map)
    runner.inject_input("D1", 10)

    # 3. Start & Wait
    await runner.start_loop()

    try:
        # We wait for the specific event proving F1 finished
        event = await runner.wait_for_event(
            lambda e: e.trace_data.get("id") == "F1"
            and e.trace_data.get("status") == "done"
        )
        assert event is not None

        # Verify physical side effect (Memory)
        assert runner.memory.get_count("D2") == 1
        assert runner.memory.take("D2").payload == 11

    finally:
        await runner.stop_loop()
~~~~~
~~~~~python.new
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
            "obs_output": PortDef(
                "obs_output", PortRole.OBSERVABILITY
            ),  # Added Obs port
        },
    )
    d2 = PhysicsDataNode(id="D2", name="Output")

    # Obs Infra
    d_life = PhysicsDataNode(
        id="global.observability.bus", name="Bus", capacity=sys.maxsize
    )
    f_obs = ObservabilityNode(
        id="global.observability.observer",
        name="Observer",
        input_ports={"event_token": PortDef("event_token", PortRole.OBSERVABILITY)},
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
    def obs_enabled_logic(inputs, node, resources):
        val = inputs["value"].payload
        # Emit Result AND Observation
        return {
            "result": Token(payload=val + 1),
            "obs_output": Token(payload=None, trace={"id": "F1", "status": "done"}),
        }

    func_map = {
        "F1": obs_enabled_logic,
        "global.observability.observer": standard_observer,
    }

    # 2. Use Runner
    runner = EventDrivenRunner(graph, func_map)
    runner.inject_input("D1", 10)

    # 3. Start & Wait
    await runner.start_loop()

    try:
        # We wait for the specific event proving F1 finished
        event = await runner.wait_for_event(
            lambda e: e.trace_data.get("id") == "F1"
            and e.trace_data.get("status") == "done"
        )
        assert event is not None

        # Verify physical side effect (Memory)
        assert runner.memory.get_count("D2") == 1
        assert runner.memory.take("D2").payload == 11

    finally:
        await runner.stop_loop()
~~~~~

### 下一步建议
我们已经成功地将 `ResourceRegistry` 模型应用到了测试工具中。现在，我们已经为路线图的**阶段 3：统一所有上下文**做好了准备。下一步，我建议我们开始设计统一的 `ExecutionContext` 对象，并重构 `Engine`，使其能够扫描图、解析参数，并最终创建这个统一的上下文，彻底废除 `cascade.common.context` 的隐式 `ContextVar` 模式。
