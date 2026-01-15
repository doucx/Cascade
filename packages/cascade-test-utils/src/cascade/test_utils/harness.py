import asyncio
import logging
import uuid
from typing import Dict, Any, Callable, TypeVar, Optional, List, Tuple

from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.nodes import Token, PhysicsDataNode
from cascade.spec.physical.object import Ref
from cascade.vm.reactor import Reactor
from cascade.spec.vm.interfaces import ReactorProtocol
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.kernel import PhysicsKernel
from cascade.bus.core import EventBus
from cascade.bus.events import Event, TaskExecutionFinished
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.vm.services.chronos import ChronosService
from cascade.vm.services.contracts import DelayRequest
from cascade.vm.registry import CodeRegistry
from cascade.vm.linker import Linker
from cascade.spec.physical.assembly import Assembly

logger = logging.getLogger(__name__)

T = TypeVar("T")


class EventTimeoutError(TimeoutError):
    pass


class EventDrivenRunner:
    @classmethod
    def from_assembly(
        cls,
        assembly: Assembly,
        code_registry: CodeRegistry,
        reactor_factory: Optional[Callable[..., ReactorProtocol]] = None,
    ) -> "EventDrivenRunner":
        linker = Linker()
        # This will raise LinkerError if code_registry is missing required hashes
        function_map = linker.link(assembly, code_registry)
        return cls(assembly.graph, function_map, code_registry, reactor_factory)

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
        self.compute_queue: asyncio.Queue[ComputeRequest] = asyncio.Queue()
        self.chronos_queue: asyncio.Queue[DelayRequest] = asyncio.Queue()
        self.ingress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()
        self.egress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()

        # 2. Setup Services
        from cascade.runtime.storage import InMemoryObjectStore

        self.object_store = InMemoryObjectStore()
        self.wakeup_event = asyncio.Event()
        self.compute_service = LocalComputeService(
            store=self.object_store,
            registry=code_registry,
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
        self.event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._captured_events: List[Event] = []
        self.event_bus.subscribe(Event, self._on_event)

        self.resource_registry = ResourceRegistry()
        self.resource_registry.register("system.event_bus", self.event_bus)
        self.resource_registry.register("system.compute_queue", self.compute_queue)
        self.resource_registry.register("system.chronos_queue", self.chronos_queue)
        self.resource_registry.register("system.object_store", self.object_store)
        self.resource_registry.register("system.egress_queue", self.egress_queue)

        # 4. Setup Reactor
        self.kernel = PhysicsKernel(function_map, self.resource_registry)

        factory = reactor_factory or Reactor
        self.reactor = factory(
            self.graph,
            self.memory,
            self.kernel,
            ingress_queue=self.ingress_queue,
        )
        # The Machine is now a component managed by the harness
        from cascade.vm.machine import Machine

        self.machine = Machine(
            self.reactor, self.compute_service, self.chronos_service, self.wakeup_event
        )
        self._loop_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def _on_event(self, event: Event):
        self.event_queue.put_nowait(event)

    def prime(self):
        for node in self.graph.nodes.values():
            if (
                isinstance(node, PhysicsDataNode)
                and node.initial_tokens > 0
                and node.id.startswith("const.")
            ):
                payload = node.initial_payload
                if payload is not None and not isinstance(payload, Ref):
                    meta = {}
                    if (
                        isinstance(payload, (int, float, bool, str))
                        and len(str(payload)) < 256
                    ):
                        meta["scalar_value"] = payload

                    node.initial_payload = self.object_store.put(payload, metadata=meta)

        self.reactor.prime(genesis_trace={"rid": self.run_id})

    async def start_loop(self):
        if self._loop_task:
            return
        self._stop_event.clear()
        self._loop_task = asyncio.create_task(self.machine.run())

    async def stop_loop(self):
        self.reactor.shutdown_event.set()
        if self._loop_task:
            try:
                await asyncio.wait_for(self._loop_task, timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Machine did not shut down cleanly, cancelling task.")
                self._loop_task.cancel()
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

        ref = self.object_store.put(payload)
        self.memory.put(node, Token(payload=ref, trace=final_trace))

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
