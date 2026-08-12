from __future__ import annotations

import asyncio
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from typing import Any, Awaitable, Callable
from unittest.mock import MagicMock

from cascade.bus.events import Event
from cascade.execution.graph.model.model import Graph, Node
from cascade.runtime import EventBus
from cascade.runtime.host.instance import Engine
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.spec.dsl.constraint import GlobalConstraint
from cascade.spec.runtime.interfaces import (
    Connector,
    ExecutionPlan,
    Executor,
    Solver,
    SubscriptionHandle,
)


@contextmanager
def override_resource(engine: Engine, name: str, new_resource_func: Callable[[], Any]):
    if not hasattr(engine, "override_resource_provider"):
        raise TypeError("The provided engine does not support resource overriding.")

    original = engine.get_resource_provider(name)
    try:
        engine.override_resource_provider(name, new_resource_func)
        yield
    finally:
        engine.override_resource_provider(name, original)


class SpySubscriber:
    def __init__(self, bus: EventBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        return [e for e in self.events if isinstance(e, event_type)]


class SpySolver(Solver):
    def __init__(self, underlying_solver: Solver):
        self.underlying_solver = underlying_solver
        self.resolve = MagicMock(wraps=self.underlying_solver.resolve)

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # This method's body is effectively replaced by the MagicMock wrapper,
        # but is required to satisfy the Solver protocol's type signature.
        # The actual call is handled by the `wraps` argument in __init__.
        return self.underlying_solver.resolve(graph)


class MockSolver(Solver):
    def __init__(self, plan: ExecutionPlan):
        self._plan = plan

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # Return the pre-programmed plan regardless of the input graph
        return self._plan


class SpyExecutor(Executor):
    def __init__(self):
        self.call_log: list[Node] = []

    async def execute(
        self,
        node: Node,
        callable_obj: Callable,
        args: list[Any],
        kwargs: dict[str, Any],
    ) -> Any:
        self.call_log.append(node)
        return f"executed_{node.name}"


class MockExecutor(Executor):
    def __init__(self, delay: float = 0, return_value: Any = "result"):
        self.delay = delay
        self.return_value = return_value

    async def execute(
        self,
        node: Node,
        callable_obj: Callable,
        args: list[Any],
        kwargs: dict[str, Any],
    ):
        if self.delay > 0:
            await asyncio.sleep(self.delay)

        # A simple logic to return something from inputs if available
        if args:
            return args[0]
        if kwargs:
            return next(iter(kwargs.values()))

        return self.return_value


class MockSubscriptionHandle(SubscriptionHandle):
    def __init__(self, parent: MockConnector, topic: str):
        self._parent = parent
        self._topic = topic

    async def unsubscribe(self) -> None:
        if self._topic in self._parent.subscriptions:
            del self._parent.subscriptions[self._topic]


class TimedMockExecutor(LocalExecutor):
    def __init__(self, delay: float = 0.0):
        super().__init__()
        self.delay = delay

    async def execute(self, node, callable_obj, args, kwargs):
        await asyncio.sleep(self.delay)
        return await super().execute(node, callable_obj, args, kwargs)


class MockConnector(Connector):
    def __init__(self):
        self.subscriptions: dict[str, Callable[[str, dict], Awaitable[None]]] = {}
        # Simulate broker storage for retained messages: topic -> payload
        self.retained_messages: dict[str, dict[str, Any]] = {}
        self.connected: bool = False
        self.disconnected: bool = False
        self.publish_log: list[dict[str, Any]] = []

    async def connect(self) -> None:
        self.connected = True
        self.disconnected = False

    async def disconnect(self) -> None:
        self.disconnected = True
        self.connected = False

    async def publish(
        self, topic: str, payload: dict[str, Any], qos: int = 0, retain: bool = False
    ) -> None:
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
        self, topic: str, callback: Callable[[str, dict], Awaitable[None]]
    ) -> SubscriptionHandle:
        self.subscriptions[topic] = callback

        # Immediate delivery of matching retained messages upon subscription
        for retained_topic, payload in self.retained_messages.items():
            if self._topic_matches(subscription=topic, topic=retained_topic):
                # Run in a task to avoid blocking the subscribe call itself
                coro = callback(retained_topic, payload)
                # Cast to avoid Pyright complaining about Awaitable vs Coroutine
                asyncio.create_task(coro)  # type: ignore

        return MockSubscriptionHandle(self, topic)

    def seed_retained_message(self, topic: str, payload: dict[str, Any]):
        self.retained_messages[topic] = payload

    async def _trigger_message(self, topic: str, payload: dict[str, Any]):
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


class ControllerTestApp:
    def __init__(self, connector: Connector):
        self.connector = connector

    async def pause(self, scope: str = "global"):
        constraint = GlobalConstraint(
            id=f"pause-{scope}-{uuid.uuid4().hex[:8]}",
            scope=scope,
            type="pause",
            params={},
        )
        await self._publish(scope, constraint)

    async def resume(self, scope: str = "global"):
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        # Sending an empty dict simulates the connector's behavior for an empty payload
        # (clearing the retained message)
        await self.connector.publish(topic, {}, retain=True)

    async def _publish(self, scope: str, constraint: GlobalConstraint):
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await self.connector.publish(topic, payload, retain=True)


__all__ = [
    "ControllerTestApp",
    "MockConnector",
    "MockExecutor",
    "MockSolver",
    "MockSubscriptionHandle",
    "SpyExecutor",
    "SpySolver",
    "SpySubscriber",
    "TimedMockExecutor",
    "override_resource",
]
