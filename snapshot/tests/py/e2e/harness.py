import asyncio
from typing import Callable, Awaitable, Dict, Any, List
from collections import defaultdict
import uuid
from dataclasses import asdict

from typing import List
from cascade.interfaces.protocols import Connector, Executor
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node
from cascade.connectors.local import LocalBusConnector


class MockWorkExecutor(Executor):
    """Executor that simulates short, time-consuming work."""

    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        # Yield control to event loop to simulate async boundary
        await asyncio.sleep(0)
        if kwargs:
            return next(iter(kwargs.values()))
        return "done"


class InProcessConnector(LocalBusConnector):
    """
    A shim that makes LocalBusConnector backwards compatible with the old test harness.
    InProcessConnector formerly managed state per-instance, but LocalBusConnector
    uses class-level state for true multi-instance simulation. We reset it on init
    to preserve the original isolation expectations of old E2E tests.
    """

    def __init__(self):
        super().__init__()
        # Ensure each test run starts with a clean bus when using the old harness
        # Note: This is synchronous-ish but fine for harness init.
        # Ideally, tests should use LocalBusConnector.reset_bus() in a fixture.
        LocalBusConnector._shared_queues.clear()
        LocalBusConnector._retained_messages.clear()


class ControllerTestApp:
    """A lightweight simulator for the cs-controller CLI tool."""

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
        await self.connector.publish(topic, {}, retain=True)

    async def _publish(self, scope: str, constraint: GlobalConstraint):
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await self.connector.publish(topic, payload, retain=True)
