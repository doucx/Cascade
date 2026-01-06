好的，我们将开始集成工作。这是一个核心重构，涉及编译器、链接器和测试Harness，以将我们新创建的异步执行模型完全接入系统。

我将生成一个计划，分步执行这些集成任务。

## [WIP] refactor(vm): 集成 dispatcher 和 compute service

### 用户需求

将新创建的 `standard_dispatcher` 和 `LocalComputeService` 集成到核心工具链中，以启用v3.1架构所定义的、基于消息队列的断连式异步执行模型。

### 评论

这是实现 v3.1 架构愿景的决定性一步。通过这次重构，我们将 `Reactor`（物理层）从繁重的用户代码执行中解放出来，使其成为一个纯粹的、高速的拓扑状态机。所有的业务逻辑计算都被卸载到 `LocalComputeService`（数据层）中异步执行。这从根本上消除了用户代码阻塞 `Reactor` 主循环的可能性，是实现高性能和可伸缩性的基石。

### 目标

1.  **更新编译器 (`Expander`)**: 修改 `Expander`，在创建 `WorkerNode` 物理节点时，将任务的规范代码哈希 (`canonical_code_structure_hash`) 填充到新增加的字段中。
2.  **更新链接器 (`Linker`)**: 修改 `Linker`，使其不再为用户任务创建专用的函数包装器，而是将所有用户 `WorkerNode` 统一链接到 `standard_dispatcher`。
3.  **更新测试Harness (`EventDrivenRunner`)**: 大幅修改测试Harness，使其能够初始化并管理 `LocalComputeService` 的生命周期，创建所需的通信队列，并模拟 `Reactor` 从结果队列中“收割”已完成任务的机制。

### 基本原理

1.  **`Expander`**: `NodeIR` 中包含了 `TaskDef`，而 `TaskDef.fingerprint` 中有我们需要的 `canonical_code_structure_hash`。我们只需在 `Expander` 创建 `WorkerNode` 实例时，将这个哈希值传递给构造函数即可。
2.  **`Linker`**: `Linker` 的职责是映射物理节点ID到可执行函数。我们将简化其逻辑：当它遇到一个在 `assembly.symbol_table` 中有记录的节点（即用户定义的 `WorkerNode`）时，直接将其映射到 `standard_dispatcher`。这将使所有用户任务在物理层共享完全相同的、统一的“发射”行为。
3.  **`EventDrivenRunner`**: 这是本次集成最核心的部分。新的 `Harness` 将扮演一个完整的微型运行时环境。它会创建两个 `asyncio.Queue`：一个用于 `dispatcher` 发射请求，另一个用于 `service` 返回结果。它会启动 `LocalComputeService.run()` 作为一个后台任务。最关键的是，它的主循环 `_run_loop` 将被重构，以同时等待 `reactor.step()` 和结果队列中的新消息，从而模拟完整的“出境-入境”数据流。

### 标签

#intent/refine #flow/ready #priority/high #comp/vm #comp/compiler #comp/std #concept/executor #scope/core #ai/instruct #task/state/continue

---

### Script

#### Acts 1: 更新 `Expander` 以填充 `code_hash`

我们修改 `expander.py`，在创建 `WorkerNode` 时，从 `NodeIR` 中提取代码哈希并填充它。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # F_worker: The actual execution logic
        # It conceptually takes *args/**kwargs, but physically takes one 'worker_input' dict
        f_worker = WorkerNode(
            id=f_worker_id,
            name=f"Exec({node_ir.name})",
            input_ports={
                "worker_input": PortDef("worker_input", PortRole.DATA, "Dict")
            },
            output_ports={
                "worker_result": PortDef("worker_result", PortRole.DATA, "Any")
            },
        )
~~~~~
~~~~~python.new
        # F_worker: The actual execution logic
        # It conceptually takes *args/**kwargs, but physically takes one 'worker_input' dict
        canonical_hash = node_ir.task.fingerprint["canonical_code_structure_hash"]
        f_worker = WorkerNode(
            id=f_worker_id,
            name=f"Exec({node_ir.name})",
            canonical_code_structure_hash=canonical_hash,
            input_ports={
                "worker_input": PortDef("worker_input", PortRole.DATA, "Dict")
            },
            output_ports={
                "worker_result": PortDef("worker_result", PortRole.DATA, "Any")
            },
        )
~~~~~

#### Acts 2: 更新 `Linker` 以使用 `standard_dispatcher`

接下来，我们重构 `linker.py`，移除旧的 `_make_worker_wrapper`，并将所有用户 `WorkerNode` 链接到 `standard_dispatcher`。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/linker.py
~~~~~
~~~~~python.old
import asyncio
from typing import Dict, Callable, Any, Optional

from cascade.spec.physical.assembly import Assembly
from cascade.spec.physical.nodes import Token, PhysicsFuncNode
from cascade.reflection import PhysicalIdGenerator

from .registry import CodeRegistry

# Standard Library Imports (Micro-Kernel)
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe


# Helper to wrap user functions
def _make_worker_wrapper(func: Callable) -> Callable:
    async def _wrapper(
        inputs: Dict[str, Token], node: Any, resources: Any
    ) -> Dict[str, Token]:
        # Unpack inputs. The Bleacher put them in 'worker_input'
        # payload is the dict of {arg_name: val}
        if "worker_input" not in inputs:
            # Fallback or error? For now assume it's there.
            return {}

        kwargs = inputs["worker_input"].payload

        # Execute
        if asyncio.iscoroutinefunction(func):
            result = await func(**kwargs)
        else:
            result = func(**kwargs)

        return {"worker_result": Token(payload=result)}

    return _wrapper


class Linker:
    def link(self, assembly: Assembly, registry: CodeRegistry) -> Dict[str, Callable]:
        function_map: Dict[str, Callable] = {}

        for node_id, node in assembly.graph.nodes.items():
            if not isinstance(node, PhysicsFuncNode):
                continue

            # 1. User Worker Nodes (via Symbol Table)
            if node_id in assembly.symbol_table:
                canonical_hash = assembly.symbol_table[node_id]
                try:
                    raw_func = registry.get(canonical_hash)
                    function_map[node_id] = _make_worker_wrapper(raw_func)
                except KeyError:
                    # TODO: In distributed mode, this might trigger a code fetch
                    raise ImportError(
                        f"Failed to link node '{node_id}': Code hash '{canonical_hash}' not found in registry."
                    )
                continue

            # 2. Standard Library Nodes (via ID Heuristics)
            stdlib_func = self._resolve_stdlib(node_id)
            if stdlib_func:
                function_map[node_id] = stdlib_func
                continue

            # If we reach here, we have an unlinked function node.
            # In strict mode, this should probably raise.
            # For now, we leave it unmapped (Reactor will raise if it tries to execute it).

        return function_map
~~~~~
~~~~~python.new
from typing import Dict, Callable, Optional

from cascade.spec.physical.assembly import Assembly
from cascade.spec.physical.nodes import PhysicsFuncNode
from cascade.reflection import PhysicalIdGenerator

from .registry import CodeRegistry

# Standard Library Imports (Micro-Kernel)
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe


class Linker:
    def link(self, assembly: Assembly, registry: CodeRegistry) -> Dict[str, Callable]:
        function_map: Dict[str, Callable] = {}

        for node_id, node in assembly.graph.nodes.items():
            if not isinstance(node, PhysicsFuncNode):
                continue

            # 1. User Worker Nodes (via Symbol Table)
            # All user workers are now implemented by the standard_dispatcher.
            if node_id in assembly.symbol_table:
                function_map[node_id] = standard_dispatcher
                continue

            # 2. Standard Library Nodes (via ID Heuristics)
            stdlib_func = self._resolve_stdlib(node_id)
            if stdlib_func:
                function_map[node_id] = stdlib_func
                continue

        return function_map
~~~~~

#### Acts 3: 重构 `EventDrivenRunner` 以支持 `LocalComputeService`

这是最重要的一步。我们将用一个能够管理后台服务和队列的新版本，完全替换 `harness.py` 的内容。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python
import asyncio
import logging
import uuid
from typing import Dict, Any, Callable, TypeVar, Optional, List, Tuple

from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.nodes import Token, PhysicsDataNode
from cascade.vm.reactor import Reactor
from cascade.vm.protocols import ReactorProtocol
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.resource_registry import ResourceRegistry
from cascade.runtime.services.observability.bus import EventBus
from cascade.runtime.services.observability.events import Event, TaskExecutionFinished
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.vm.registry import CodeRegistry

logger = logging.getLogger(__name__)

T = TypeVar("T")


class EventTimeoutError(TimeoutError):
    pass


class EventDrivenRunner:
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
        self.compute_queue: asyncio.Queue[ComputeRequest] = asyncio.Queue()
        self.ingress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()

        # 2. Setup Services
        # In a real system, store would be a separate entity.
        # Here we use a mock that is part of the test setup.
        # This runner doesn't have a store, but the compute service will need one.
        # Let's assume for now the compute service can be built without a real store
        # because the test functions it calls don't use it.
        # CORRECTION: LocalComputeService requires a store. Test functions will need one.
        # Let's create a mock store for the service.
        from cascade.runtime.storage import InMemoryObjectStore

        self.object_store = InMemoryObjectStore()
        self.compute_service = LocalComputeService(
            store=self.object_store,
            registry=code_registry,
            inbound_queue=self.compute_queue,
            outbound_queue=self.ingress_queue,
        )

        # 3. Setup Event Bus & Resource Registry
        self.event_bus = EventBus()
        self.event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._captured_events: List[Event] = []
        self.event_bus.subscribe(Event, self._on_event)

        self.resource_registry = ResourceRegistry()
        self.resource_registry.register("system.event_bus", self.event_bus)
        self.resource_registry.register("system.compute_queue", self.compute_queue)

        # 4. Setup Reactor
        factory = reactor_factory or Reactor
        self.reactor = factory(
            self.graph,
            self.memory,
            self.executor,
            function_map,
            self.resource_registry,
        )
        self._loop_task: Optional[asyncio.Task] = None
        self._service_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def _on_event(self, event: Event):
        self.event_queue.put_nowait(event)

    def prime(self):
        self.reactor.prime(genesis_trace={"rid": self.run_id})

    async def start_loop(self):
        if self._loop_task:
            return
        self._stop_event.clear()
        # Start both the reactor and the compute service as background tasks
        self._service_task = asyncio.create_task(self.compute_service.run())
        self._loop_task = asyncio.create_task(self._run_loop())

    async def _run_loop(self):
        logger.info("Reactor loop with ingress handling started.")
        try:
            while not self._stop_event.is_set():
                # This is the core of the v3.1 harness: it simulates the Reactor's
                # ability to handle both internal state changes and external events.
                await self._handle_ingress()
                fired = await self.reactor.step()
                if fired == 0 and self.ingress_queue.empty():
                    await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Reactor loop crashed")
            raise

    async def _handle_ingress(self):
        """Process all pending results from the compute service."""
        while not self.ingress_queue.empty():
            reply_to_nid, result_token = self.ingress_queue.get_nowait()
            node = self.graph.nodes.get(reply_to_nid)
            if isinstance(node, PhysicsDataNode):
                self.memory.put(node, result_token)
            else:
                logger.warning(
                    f"Invalid reply_to_nid '{reply_to_nid}': not a DataNode."
                )

    async def stop_loop(self):
        self._stop_event.set()
        if self._service_task:
            self.compute_service.stop()
            self._service_task.cancel()
            try:
                await self._service_task
            except asyncio.CancelledError:
                pass
            self._service_task = None
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None

    def inject_input(
        self, node_id: str, payload: Any, trace: Optional[Dict[str, Any]] = None
    ):
        node = self.graph.nodes[node_id]
        if not isinstance(node, PhysicsDataNode):
            raise ValueError(f"Node {node_id} is not a DataNode")
        final_trace = {"rid": self.run_id}
        if trace:
            final_trace.update(trace)
        self.memory.put(node, Token(payload=payload, trace=final_trace))

    async def wait_for_event(
        self,
        predicate: Callable[[Event], bool],
        timeout: float = 1.0,
    ) -> Event:
        start_time = asyncio.get_event_loop().time()
        while True:
            now = asyncio.get_event_loop().time()
            if now - start_time > timeout:
                raise EventTimeoutError(f"Timed out waiting for event after {timeout}s")
            try:
                remaining = timeout - (now - start_time)
                event = await asyncio.wait_for(
                    self.event_queue.get(), timeout=max(0.001, remaining)
                )
                self._captured_events.append(event)
                if predicate(event):
                    return event
            except asyncio.TimeoutError:
                raise EventTimeoutError(f"Timed out waiting for event after {timeout}s")

    async def run_until_complete(self, task_id: str, timeout: float = 2.0) -> Event:
        def is_completion(e: Event):
            if isinstance(e, TaskExecutionFinished):
                return e.task_id == task_id
            return False
        return await self.wait_for_event(is_completion, timeout=timeout)
~~~~~

### 下一步建议

我们已经完成了核心的集成工作，但还没有验证它是否能正常工作。`EventDrivenRunner` 的大规模改动很可能导致现有测试失败。

因此，下一步至关重要：**更新 `test_source_node_execution.py` 测试用例**。这个测试是验证端到端流程（从启动脉冲到任务完成）的理想选择。我们需要更新它，以适应 `EventDrivenRunner` 新的构造函数签名（需要传入 `CodeRegistry`），并验证整个“发射 -> 服务执行 -> 结果返回 -> `Stainer` 激活”的完整异步循环是否按预期工作。
