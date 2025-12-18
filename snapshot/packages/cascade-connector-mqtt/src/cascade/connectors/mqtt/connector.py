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

    async def connect(self) -> None:
        """Establishes a connection to the MQTT Broker."""
        if self._client:
            return

        # aiomqtt.Client now acts as an async context manager
        client = aiomqtt.Client(
            hostname=self.hostname, port=self.port, **self.client_kwargs
        )
        # TODO: Implement LWT message logic.
        self._client = await client.__aenter__()

    async def disconnect(self) -> None:
        """Disconnects from the MQTT Broker and cleans up resources."""
        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None:
        """
        Publishes a message in a non-blocking, fire-and-forget manner.
        """
        if not self._client:
            logger.warning("Attempted to publish without an active MQTT connection.")
            return

        async def _do_publish():
            try:
                json_payload = json.dumps(payload)
                await self._client.publish(topic, payload=json_payload, qos=qos)
            except Exception as e:
                # Per Fail-Silent Telemetry principle, we log errors but don't propagate them.
                logger.error(f"Failed to publish MQTT message to topic '{topic}': {e}")

        asyncio.create_task(_do_publish())


    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        """Subscribes to a topic to receive messages."""
        # TODO: Implement subscription logic.
        # - The client needs a message handling loop.
        # - This method should register the topic and callback.
        # - The loop will decode JSON and invoke the callback.
        pass