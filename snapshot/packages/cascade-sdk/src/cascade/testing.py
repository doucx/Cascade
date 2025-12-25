from contextlib import contextmanager
from typing import Callable, Any, List, Dict, Awaitable
from unittest.mock import MagicMock
import asyncio

from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.spec.protocols import Solver, Executor, ExecutionPlan, Connector
from cascade.graph.model import Node, Graph


@contextmanager
def override_resource(
    engine: "Engine", name: str, new_resource_func: Callable[[], Any]
):
    """
    A context manager to temporarily override a resource for testing purposes.

    Usage:
        engine = Engine()
        engine.register(production_db)

        with override_resource(engine, "production_db", mock_db):
            engine.run(my_task) # my_task will receive mock_db
    """
    if not hasattr(engine, "override_resource_provider"):
        raise TypeError("The provided engine does not support resource overriding.")

    original = engine.get_resource_provider(name)
    try:
        engine.override_resource_provider(name, new_resource_func)
        yield
    finally:
        engine.override_resource_provider(name, original)


class SpySubscriber:
    """A test utility to collect events from a MessageBus."""

    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        """Returns a list of all events of a specific type."""
        return [e for e in self.events if isinstance(e, event_type)]


class SpySolver(Solver):
    """
    A test double for the Solver protocol that spies on calls to `resolve`
    while delegating to a real underlying solver.
    """

    def __init__(self, underlying_solver: Solver):
        self.underlying_solver = underlying_solver
        self.resolve = MagicMock(wraps=self.underlying_solver.resolve)

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # This method's body is effectively replaced by the MagicMock wrapper,
        # but is required to satisfy the Solver protocol's type signature.
        # The actual call is handled by the `wraps` argument in __init__.
        pass


class MockSolver(Solver):
    """
    A test double for the Solver protocol that returns a pre-programmed plan,
    bypassing any real resolution logic.
    """

    def __init__(self, plan: ExecutionPlan):
        self._plan = plan

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # Return the pre-programmed plan regardless of the input graph
        return self._plan


class SpyExecutor(Executor):
    """A test double for the Executor protocol that logs all calls to `execute`."""

    def __init__(self):
        self.call_log: List[Node] = []

    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        self.call_log.append(node)
        return f"executed_{node.name}"


class MockExecutor(Executor):
    """
    A generic mock for the Executor protocol that can simulate various
    behaviors like delays or returning specific values.
    """



    def __init__(self, delay: float = 0, return_value: Any = "result"):
        self.delay = delay
        self.return_value = return_value

    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        if self.delay > 0:
            await asyncio.sleep(self.delay)

        # A simple logic to return something from inputs if available
        if args:
            return args[0]
        if kwargs:
            return next(iter(kwargs.values()))

        return self.return_value


class MockConnector(Connector):
    """
    A mock connector for testing that simulates MQTT behavior,
    including retained messages and topic matching.
    """

    def __init__(self):
        self.subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}
        # Simulate broker storage for retained messages: topic -> payload
        self.retained_messages: Dict[str, Dict[str, Any]] = {}
        self.connected: bool = False
        self.disconnected: bool = False
        self.publish_log: List[Dict[str, Any]] = []

    async def connect(self) -> None:
        self.connected = True
        self.disconnected = False

    async def disconnect(self) -> None:
        self.disconnected = True
        self.connected = False

    async def publish(
        self, topic: str, payload: Dict[str, Any], retain: bool = False, qos: int = 0
    ) -> None:
        """Simulates publishing a message, triggering subscribers and handling retention."""
        self.publish_log.append(
            {"topic": topic, "payload": payload, "retain": retain, "qos": qos}
        )

        if retain:
            if payload:
                self.retained_messages[topic] = payload
            elif topic in self.retained_messages:
                # An empty payload on a retained topic clears it
                del self.retained_messages[topic]

        await self._trigger_message(topic, payload)

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        self.subscriptions[topic] = callback

        # Immediate delivery of matching retained messages upon subscription
        for retained_topic, payload in self.retained_messages.items():
            if self._topic_matches(subscription=topic, topic=retained_topic):
                # Run in a task to avoid blocking the subscribe call itself
                asyncio.create_task(callback(retained_topic, payload))

    def seed_retained_message(self, topic: str, payload: Dict[str, Any]):
        """Helper to pre-seed a retained message on the 'broker' for test setup."""
        self.retained_messages[topic] = payload

    async def _trigger_message(self, topic: str, payload: Dict[str, Any]):
        """Helper to simulate receiving a message, used by tests and publish()."""
        for sub_topic, callback in self.subscriptions.items():
            if self._topic_matches(subscription=sub_topic, topic=topic):
                await callback(topic, payload)

    def _topic_matches(self, subscription: str, topic: str) -> bool:
        # Simple topic matching for direct match and wildcard at the end
        if subscription == topic:
            return True
        if subscription.endswith("/#"):
            prefix = subscription[:-2]
            if topic.startswith(prefix):
                return True
        return False