import asyncio
import json
import logging
from typing import Callable, Awaitable, Dict, Any

try:
    import aiomqtt
except ImportError:
    aiomqtt = None

logger = logging.getLogger(__name__)


class MqttConnector:
    """
    Implements the Connector protocol for MQTT.

    This connector enables Cascade to publish telemetry data to an MQTT broker
    and subscribe to control commands.
    """

    def __init__(self, hostname: str, port: int = 1883, **kwargs):
        if aiomqtt is None:
            raise ImportError(
                "The 'aiomqtt' library is required to use the MqttConnector. "
                "Please install it with: pip install cascade-connector-mqtt"
            )
        self.hostname = hostname
        self.port = port
        self.client_kwargs = kwargs
        self._client: "aiomqtt.Client" | None = None
        self._subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}
        self._handler_task: asyncio.Task | None = None

    async def _message_handler_loop(self):
        if not self._client:
            return
        try:
            async for message in self._client.messages:
                topic = message.topic.value
                callback = self._subscriptions.get(topic)
                if callback:
                    try:
                        payload = json.loads(message.payload)
                        # Fire-and-forget the callback execution
                        asyncio.create_task(callback(topic, payload))
                    except json.JSONDecodeError:
                        logger.warning(f"Received non-JSON payload on topic '{topic}'")
                    except Exception as e:
                        logger.error(f"Error in message callback for topic '{topic}': {e}")
        except asyncio.CancelledError:
            logger.info("MQTT message handler task cancelled.")
        except Exception as e:
            logger.error(f"MQTT message handler loop crashed: {e}")

    async def connect(self) -> None:
        """Establishes a connection and starts the message handler."""
        if self._client:
            return

        client = aiomqtt.Client(
            hostname=self.hostname, port=self.port, **self.client_kwargs
        )
        self._client = await client.__aenter__()
        self._handler_task = asyncio.create_task(self._message_handler_loop())

    async def disconnect(self) -> None:
        """Cancels the message handler and disconnects from the broker."""
        if self._handler_task:
            self._handler_task.cancel()
            try:
                await self._handler_task
            except asyncio.CancelledError:
                pass  # Expected
            self._handler_task = None

        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None
        
        self._subscriptions.clear()


    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None:
        """Publishes a message in a non-blocking, fire-and-forget manner."""
        if not self._client:
            logger.warning("Attempted to publish without an active MQTT connection.")
            return

        async def _do_publish():
            try:
                json_payload = json.dumps(payload)
                await self._client.publish(topic, payload=json_payload, qos=qos)
            except Exception as e:
                logger.error(f"Failed to publish MQTT message to topic '{topic}': {e}")

        asyncio.create_task(_do_publish())

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        """Subscribes to a topic to receive messages."""
        if not self._client:
            raise ConnectionError("Cannot subscribe, not connected to MQTT broker.")

        await self._client.subscribe(topic)
        self._subscriptions[topic] = callback