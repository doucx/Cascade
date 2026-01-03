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
            self.function_map[obs_id] = partial(
                standard_observer, queue=self.event_queue
            )

        self.reactor = Reactor(
            self.graph, self.memory, self.executor, self.function_map
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
