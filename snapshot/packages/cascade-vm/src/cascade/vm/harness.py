import asyncio
import logging
import uuid
from typing import Dict, Any, Callable, TypeVar, Optional, List, Tuple

from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.nodes import Token, PhysicsDataNode
from cascade.vm.reactor import Reactor
from cascade.vm.protocols import ReactorProtocol
from cascade.vm.memory import VolatileMemory
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
        self.resource_registry.register("system.object_store", self.object_store)

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
                # In v3.1 Phase 4, the Reactor handles ingress internally during step().
                fired = await self.reactor.step()
                if fired == 0 and self.ingress_queue.empty():
                    await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Reactor loop crashed")
            raise

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

        # v3.1: All data in the physical layer is a Ref.
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
