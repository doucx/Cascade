好的，既然 `Engine` 这个名字已被 DSL 层占用，我们将使用 **`Machine`** (`cascade.vm.machine.Machine`) 这个更具物理感的名称来命名新的顶层异步协调器。它象征着这是驱动整个 Cascade 系统的“物理机器”。

我们将继续执行“阶段 1: 直驱引擎 - `Reactor` 的重生”。

## [WIP] feat(vm): 实现 Reactor 同步直驱与 Machine 协调器

### 用户需求

1.  **Reactor 同步化**: 将 `Reactor.step()` 重构为纯同步方法，实现“扫描-执行-发射”的直驱逻辑。
2.  **Machine 协调器**: 创建一个新的 `Machine` 类（替代原计划的 `Engine`），负责在异步循环中驱动同步的 `Reactor` 并协调 `LocalComputeService`。
3.  **状态查询**: 为 `LocalComputeService` 添加 `is_idle()` 方法，以便 `Machine` 判断何时停机。
4.  **Harness 修复**: 修复 `EventDrivenRunner` 以适配移除了 `executor` 的新架构。

### 评论

这是 Cascade 内核演进中最关键的一次“心脏移植”手术。通过将 `Reactor` 降级为纯同步组件，我们极大地简化了其心智模型，并消除了线程池调度的开销。新的 `Machine` 类将清晰地界定“物理时间”（同步步进）与“计算时间”（异步等待）的边界。这种**双速架构**（Dual-Speed Architecture）是实现高性能与高可用性的基石。

### 目标

1.  修改 `packages/cascade-vm/src/cascade/vm/compute/service.py`，添加 `is_idle` 方法。
2.  修改 `packages/cascade-vm/src/cascade/vm/reactor.py`，实现同步 `step` 和 `_handle_results_immediate`。
3.  创建 `packages/cascade-vm/src/cascade/vm/machine.py`，实现 `Machine` 类。
4.  修复 `packages/cascade-vm/src/cascade/vm/harness.py`，移除对 `PhysicsExecutor` 的引用。

### 基本原理

*   **同步直驱**: 消除 `await` 和任务调度开销，让物理图的演化达到内存访问级别的速度。
*   **Machine 模式**: 将异步 I/O 和长时间运行的任务（由 Service 处理）与核心状态转换（由 Reactor 处理）物理隔离。`Machine` 是这两个世界的桥梁。
*   **Idle Detection**: 系统停机的条件不再是单纯的“没有任务”，而是“Reactor 静止”且“Compute Service 空闲”。

### 标签

#intent/architect #intent/build #flow/ready #priority/high #comp/vm #concept/state #scope/core #ai/instruct #task/domain/vm #task/object/reactor #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 为 ComputeService 添加空闲检测

我们需要让计算服务能够报告它是否处于空闲状态，以便 `Machine` 决定是否结束运行。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="cascade_compute"
        )
        self._running = False

    async def run(self) -> None:
~~~~~
~~~~~python.new
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="cascade_compute"
        )
        self._running = False
        self._active_count = 0

    def is_idle(self) -> bool:
        return self.inbound_queue.empty() and self._active_count == 0

    async def run(self) -> None:
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
    async def _process_request(self, request: ComputeRequest) -> None:
        try:
            # 1. Resolve Inputs
            inputs: Dict[str, Any] = {
                key: self.store.get(ref) for key, ref in request.input_refs.items()
            }
~~~~~
~~~~~python.new
    async def _process_request(self, request: ComputeRequest) -> None:
        self._active_count += 1
        try:
            # 1. Resolve Inputs
            inputs: Dict[str, Any] = {
                key: self.store.get(ref) for key, ref in request.input_refs.items()
            }
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
        # 5. Report Completion to Outbound Queue
        await self.outbound_queue.put((request.reply_to_nid, result_token))

    def _resolve_arguments(
        self, inputs: Dict[str, Any]
    ) -> Tuple[List[Any], Dict[str, Any]]:
~~~~~
~~~~~python.new
        # 5. Report Completion to Outbound Queue
        await self.outbound_queue.put((request.reply_to_nid, result_token))
        finally:
            self._active_count -= 1

    def _resolve_arguments(
        self, inputs: Dict[str, Any]
    ) -> Tuple[List[Any], Dict[str, Any]]:
~~~~~

#### Acts 2: 实现 Reactor 的同步直驱

这是核心变更。我们将 `step` 改为同步，并内联了结果处理逻辑。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None:
        genesis_trace = genesis_trace or {}
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                for _ in range(node.initial_tokens):
                    # Initial tokens use the node's defined payload (for constants) or None.
                    # We inject the genesis trace (e.g. run_id) into these primordial tokens.
                    self.memory.put(
                        node,
                        Token(payload=node.initial_payload, trace=genesis_trace.copy()),
                    )

    async def step(self) -> int:
        # 0. Ingress Cycle
        self._process_ingress()

        nodes_to_fire: List[PhysicsFuncNode] = []
        inputs_for_fire: Dict[str, Dict[str, Token]] = {}

        # --- ATOMIC SCAN & CONSUME ---
        # This loop is single-threaded and sequential. The state of `memory`
        # changes within the loop, ensuring that a resource token consumed by an
        # early node is unavailable for a later node in the same step.
        for f_node in self._func_nodes:
            inputs_def = self._func_inputs.get(f_node.id, [])
            if not inputs_def:
                continue

            # Check if this node CAN fire based on the CURRENT memory state
            if all(self.memory.is_excited(src_id) for src_id, _ in inputs_def):
                # It can. Atomically consume its inputs NOW.
                consumed_inputs = {
                    port: self.memory.take(src_id) for src_id, port in inputs_def
                }
                nodes_to_fire.append(f_node)
                inputs_for_fire[f_node.id] = consumed_inputs

        if not nodes_to_fire:
            return 0

        # --- EXECUTION LOGIC REMOVED ---
        # The logic to call _schedule_task was here.
        # It is removed as part of Phase 0 purification.
        # Phase 1 will implement the new direct-drive logic.

        return len(nodes_to_fire)

    def _process_ingress(self):
~~~~~
~~~~~python.new
    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None:
        genesis_trace = genesis_trace or {}
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                for _ in range(node.initial_tokens):
                    # Initial tokens use the node's defined payload (for constants) or None.
                    # We inject the genesis trace (e.g. run_id) into these primordial tokens.
                    self.memory.put(
                        node,
                        Token(payload=node.initial_payload, trace=genesis_trace.copy()),
                    )

    def step(self) -> int:
        # 0. Ingress Cycle
        self._process_ingress()

        nodes_to_fire: List[PhysicsFuncNode] = []
        inputs_for_fire: Dict[str, Dict[str, Token]] = {}

        # --- ATOMIC SCAN & CONSUME ---
        # This loop is single-threaded and sequential. The state of `memory`
        # changes within the loop, ensuring that a resource token consumed by an
        # early node is unavailable for a later node in the same step.
        for f_node in self._func_nodes:
            inputs_def = self._func_inputs.get(f_node.id, [])
            if not inputs_def:
                continue

            # Check if this node CAN fire based on the CURRENT memory state
            if all(self.memory.is_excited(src_id) for src_id, _ in inputs_def):
                # It can. Atomically consume its inputs NOW.
                consumed_inputs = {
                    port: self.memory.take(src_id) for src_id, port in inputs_def
                }
                nodes_to_fire.append(f_node)
                inputs_for_fire[f_node.id] = consumed_inputs

        if not nodes_to_fire:
            return 0

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

    def _handle_results_immediate(self, node: PhysicsFuncNode, results: Dict[str, Token]) -> None:
        if not isinstance(results, dict):
            logger.error(f"Function for node {node.id} returned {type(results)}, expected dict.")
            return

        outbound = self._outbound_channels.get(node.id, [])
        node_sinks = self.sinks.get(node.id, {})

        for port_name, token in results.items():
            if token is None:
                continue

            # A. Handle Sinks (Callbacks)
            # Note: Sinks in the physical layer MUST be non-blocking.
            # If they return a coroutine, we schedule it on the loop but do NOT await.
            if port_name in node_sinks:
                for cb in node_sinks[port_name]:
                    try:
                        res = cb(token)
                        if inspect.isawaitable(res):
                            # Fire and forget for async sinks
                            asyncio.create_task(res)
                    except Exception as e:
                        logger.exception(f"Sink callback failed for {node.id}:{port_name}: {e}")

            # B. Handle Outbound Channels (Topological Flow)
            matching_channels = [c for c in outbound if c.source_port == port_name]
            for channel in matching_channels:
                target_node = self.graph.nodes[channel.target_node_id]
                if isinstance(target_node, PhysicsDataNode):
                    self.memory.put(target_node, token)

    def _process_ingress(self):
~~~~~

#### Acts 3: 创建 Machine 协调器

实现新的顶层协调器。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python
import asyncio
import logging
from typing import Optional, Tuple
from cascade.spec.physical.nodes import Token
from cascade.vm.reactor import Reactor
from cascade.vm.compute.service import LocalComputeService

logger = logging.getLogger(__name__)


class Machine:
    """
    The Machine coordinates the synchronous Physics Kernel (Reactor) 
    and the asynchronous Compute Plane (LocalComputeService).
    """

    def __init__(
        self,
        reactor: Reactor,
        compute_service: LocalComputeService,
        ingress_queue: "asyncio.Queue[Tuple[str, Token]]",
    ):
        self.reactor = reactor
        self.compute_service = compute_service
        self.ingress_queue = ingress_queue

    async def run(self) -> None:
        """
        Starts the Machine loop. Runs until the system settles (idle).
        """
        logger.info("Machine started.")
        
        # Start the Compute Service
        service_task = asyncio.create_task(self.compute_service.run())
        
        try:
            while True:
                # 1. Drive the Physics Kernel (Synchronous Step)
                fired_count = self.reactor.step()

                # 2. Check for Quiescence
                # If the reactor did nothing, and there's no pending I/O...
                if fired_count == 0 and self.ingress_queue.empty():
                    # ...and the compute service has no active workers...
                    if self.compute_service.is_idle():
                        logger.info("Machine idle. Stopping.")
                        break
                    
                    # If we are just waiting for Compute, yield to the event loop
                    # to give the Service a chance to work.
                    await asyncio.sleep(0.001)
                else:
                    # If we did work, yield briefly to allow I/O ingress processing
                    # but return quickly to sustain high throughput.
                    await asyncio.sleep(0)
                    
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

#### Acts 4: 修复 Test Harness

修复 `harness.py` 以适应 API 变更（移除 `executor`）。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
from cascade.vm.reactor import Reactor
from cascade.vm.protocols import ReactorProtocol
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.resource_registry import ResourceRegistry
from cascade.runtime.services.observability.bus import EventBus
~~~~~
~~~~~python.new
from cascade.vm.reactor import Reactor
from cascade.vm.protocols import ReactorProtocol
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.runtime.services.observability.bus import EventBus
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
    def __init__(
        self,
        graph: BipartiteGraph,
        function_map: Dict[str, Callable],
        code_registry: CodeRegistry,
        reactor_factory: Optional[Callable[..., ReactorProtocol]] = None,
    ):
        self.graph = graph
        self.memory = VolatileMemory()
        self.executor = PhysicsExecutor()
        self.run_id = str(uuid.uuid4())

        # 1. Setup Queues for disconnected execution
~~~~~
~~~~~python.new
    def __init__(
        self,
        graph: BipartiteGraph,
        function_map: Dict[str, Callable],
        code_registry: CodeRegistry,
        reactor_factory: Optional[Callable[..., ReactorProtocol]] = None,
    ):
        self.graph = graph
        self.memory = VolatileMemory()
        self.run_id = str(uuid.uuid4())

        # 1. Setup Queues for disconnected execution
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
        # 4. Setup Reactor
        factory = reactor_factory or Reactor
        self.reactor = factory(
            self.graph,
            self.memory,
            self.executor,
            function_map,
            self.resource_registry,
            ingress_queue=self.ingress_queue,
        )
        self._loop_task: Optional[asyncio.Task] = None
~~~~~
~~~~~python.new
        # 4. Setup Reactor
        factory = reactor_factory or Reactor
        self.reactor = factory(
            self.graph,
            self.memory,
            function_map,
            self.resource_registry,
            ingress_queue=self.ingress_queue,
        )
        self._loop_task: Optional[asyncio.Task] = None
~~~~~

### 下一步建议

阶段 1 已完成。我们现在拥有了一个基于 `Machine` 驱动的同步 `Reactor`。

接下来的**“阶段 2: 桥接司法管辖区”**将专注于验证物理层与异步层之间的通信协议。
我们需要确保标准库中的 Dispatcher 和 Observer 等组件能够正确地在这个新架构下工作（即，它们应该是同步的，只负责把消息扔进队列/总线，而不执行实际等待）。

我建议接下来审查 `packages/cascade-std` 中的相关 IC，并编写一个新的集成测试来验证端到端的 `Machine` 运行。
