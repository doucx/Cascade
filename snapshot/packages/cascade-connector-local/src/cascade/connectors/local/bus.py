import asyncio
from collections import defaultdict
from typing import Dict, List, Any, Callable, Awaitable, Optional
from cascade.spec.protocols import Connector, SubscriptionHandle
from cascade.common.messaging import bus


class _LocalSubscriptionHandle(SubscriptionHandle):
    """Implementation of the subscription handle for the LocalBusConnector."""

    def __init__(
        self,
        parent: "LocalBusConnector",
        topic: str,
        queue: asyncio.Queue,
        listener_task: asyncio.Task,
    ):
        self._parent = parent
        self._topic = topic
        self._queue = queue
        self._listener_task = listener_task

    async def unsubscribe(self) -> None:
        # 1. Cancel the listener task
        self._listener_task.cancel()
        try:
            await self._listener_task
        except asyncio.CancelledError:
            pass

        # 2. Remove the queue from the broker's shared state
        async with self._parent._get_lock():
            is_wildcard = "+" in self._topic or "#" in self._topic
            target_dict = (
                self._parent._wildcard_subscriptions
                if is_wildcard
                else self._parent._exact_subscriptions
            )

            if self._topic in target_dict:
                try:
                    target_dict[self._topic].remove(self._queue)
                    if not target_dict[self._topic]:
                        del target_dict[self._topic]
                except ValueError:
                    # Queue already removed, which is fine
                    pass

        # 3. Remove task from parent's tracked listeners to prevent memory leak
        try:
            self._parent._listener_tasks.remove(self._listener_task)
        except ValueError:
            pass


class LocalBusConnector(Connector):
    """
    A robust, in-memory implementation of the Connector protocol.
    Acts as a local MQTT broker, supporting:
    - Shared state across instances (simulating a network broker)
    - Retained messages
    - Topic wildcards (+ and #)
    """

    # --- Broker State (Shared across all instances) ---
    _exact_subscriptions: Dict[str, List["asyncio.Queue"]] = defaultdict(list)
    _wildcard_subscriptions: Dict[str, List["asyncio.Queue"]] = defaultdict(list)
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
        try:
            # In modern Python, accessing or using a lock created in a different
            # loop will raise RuntimeError. We catch this to re-initialize.
            if cls._lock is None or cls._lock._get_loop() != loop:
                cls._lock = asyncio.Lock()
        except RuntimeError:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    def _reset_broker_state(cls):
        """Helper for tests to clear the 'broker'."""
        cls._exact_subscriptions.clear()
        cls._wildcard_subscriptions.clear()
        cls._retained_messages.clear()
        # Setting to None ensures _get_lock will create a fresh one for the current loop
        cls._lock = None

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
        print(f"DEBUG: Connector publish {topic} connected={self._is_connected}")
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

            # 1. Exact Matches (O(1))
            if topic in self._exact_subscriptions:
                for q in self._exact_subscriptions[topic]:
                    await q.put((topic, payload))

            # 2. Wildcard Matches (O(W))
            for sub_topic, queues in self._wildcard_subscriptions.items():
                match = self._topic_matches(sub_topic, topic)
                print(f"DEBUG: Checking match sub='{sub_topic}' topic='{topic}' -> {match}. Queues: {len(queues)}")
                if match:
                    for q in queues:
                        await q.put((topic, payload))

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> SubscriptionHandle:
        print(f"DEBUG: Connector subscribe {topic}")
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")

        queue = asyncio.Queue()
        is_wildcard = "+" in topic or "#" in topic

        async with self._get_lock():
            if is_wildcard:
                self._wildcard_subscriptions[topic].append(queue)
            else:
                self._exact_subscriptions[topic].append(queue)

            # Deliver Retained Messages Synchronously for the caller.
            # Note: Retained messages iteration is still O(R), which is acceptable
            # as it happens only once per subscription.
            for retained_topic, payload in self._retained_messages.items():
                # Check match logic:
                # If I subscribe to "a/+", I want retained "a/1", "a/2".
                # _topic_matches(sub=topic, topic=retained)
                if self._topic_matches(topic, retained_topic):
                    try:
                        await callback(retained_topic, payload)
                    except Exception as e:
                        bus.error(
                            "localbus.retained_callback_error",
                            topic=retained_topic,
                            error=e,
                        )

        # Start a background listener for NEW incoming messages
        task = asyncio.create_task(self._listener_loop(queue, callback))
        self._listener_tasks.append(task)

        return _LocalSubscriptionHandle(self, topic, queue, task)

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
                    bus.error("localbus.callback_error", topic=topic, error=e)
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
