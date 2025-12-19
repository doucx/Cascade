import asyncio
from collections import defaultdict
from typing import Dict, List, Any, Callable, Awaitable
from cascade.interfaces.protocols import Connector


class LocalBusConnector(Connector):
    """
    A robust, in-memory implementation of the Connector protocol.
    Acts as a local MQTT broker, supporting:
    - Shared state across instances (simulating a network broker)
    - Retained messages
    - Topic wildcards (+ and #)
    """

    # --- Broker State (Shared across all instances) ---
    _subscriptions: Dict[str, List["asyncio.Queue"]] = defaultdict(list)
    _retained_messages: Dict[str, Any] = {}
    _lock: Optional[asyncio.Lock] = None

    def __init__(self):
        # Default to True to support pre-run configuration in E2E tests
        self._is_connected = True
        self._listener_tasks = []

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        """
        Ensures the lock is bound to the current running event loop.
        This is critical for pytest where each test has its own loop.
        """
        loop = asyncio.get_running_loop()
        if cls._lock is None or cls._lock._get_loop() != loop:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    def _reset_broker_state(cls):
        """Helper for tests to clear the 'broker'."""
        cls._subscriptions.clear()
        cls._retained_messages.clear()
        cls._lock = None  # Force re-creation on next access

    async def connect(self) -> None:
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False
        # Cancel all listener tasks for this connector
        for task in self._listener_tasks:
            task.cancel()
        if self._listener_tasks:
            await asyncio.gather(*self._listener_tasks, return_exceptions=True)
        self._listener_tasks.clear()

    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
        if not self._is_connected:
            return

        async with self._get_lock():
            # Handle Retention
            if retain:
                if payload == {} or payload == "":
                    # Clear retained message
                    self._retained_messages.pop(topic, None)
                else:
                    # Save retained message
                    self._retained_messages[topic] = payload

            # Route to all matching queues
            # We iterate over all subscription topics in the broker
            for sub_topic, queues in self._subscriptions.items():
                if self._topic_matches(sub_topic, topic):
                    for q in queues:
                        await q.put((topic, payload))

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        if not self._is_connected:
            return

        queue = asyncio.Queue()
        
        async with self._get_lock():
            self._subscriptions[topic].append(queue)

            # Deliver Retained Messages
            for retained_topic, payload in self._retained_messages.items():
                if self._topic_matches(topic, retained_topic):
                    # For immediate delivery, we can push to queue or call callback directly?
                    # Pushing to queue preserves order and simplifies locking.
                    await queue.put((retained_topic, payload))

        # Start a background listener for this specific subscription queue
        task = asyncio.create_task(self._listener_loop(queue, callback))
        self._listener_tasks.append(task)

    async def _listener_loop(self, queue: asyncio.Queue, callback):
        """Consumes messages from the subscription queue and invokes callback."""
        try:
            while self._is_connected:
                # Use a small timeout or just wait. wait_for allows easier cancellation?
                # A simple await get() is fine as long as we cancel task on disconnect.
                topic, payload = await queue.get()
                try:
                    await callback(topic, payload)
                except Exception as e:
                    # Fail-silent: don't crash the bus because a callback failed
                    print(f"[LocalBus] Callback error on {topic}: {e}")
                finally:
                    queue.task_done()
        except asyncio.CancelledError:
            pass

    @staticmethod
    def _topic_matches(subscription: str, topic: str) -> bool:
        """
        Checks if a concrete topic matches a subscription pattern (supporting + and #).
        """
        if subscription == "#":
            return True
        if subscription == topic:
            return True

        sub_parts = subscription.split("/")
        topic_parts = topic.split("/")

        for i, sub_part in enumerate(sub_parts):
            if sub_part == "#":
                return True

            if i >= len(topic_parts):
                return False

            topic_part = topic_parts[i]

            if sub_part == "+":
                continue

            if sub_part != topic_part:
                return False

        return len(sub_parts) == len(topic_parts)