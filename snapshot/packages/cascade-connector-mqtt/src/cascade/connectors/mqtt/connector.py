import asyncio
import json
import logging
import platform
import os
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
        self._loop_task: asyncio.Task | None = None
        self._subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}
        self._source_id = f"{platform.node()}-{os.getpid()}"

    async def connect(self) -> None:
        """Establishes a connection to the MQTT Broker."""
        if self._client:
            return

        # Define the Last Will and Testament message
        lwt_topic = f"cascade/status/{self._source_id}"
        lwt_payload = json.dumps({"status": "offline"})
        will_message = aiomqtt.Will(topic=lwt_topic, payload=lwt_payload)

        # aiomqtt.Client now acts as an async context manager
        client = aiomqtt.Client(
            hostname=self.hostname,
            port=self.port,
            will=will_message,
            **self.client_kwargs,
        )
        self._client = await client.__aenter__()

        # Start the message processing loop
        self._loop_task = asyncio.create_task(self._message_loop())

    async def disconnect(self) -> None:
        """Disconnects from the MQTT Broker and cleans up resources."""
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None

        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
        """
        Publishes a message in a non-blocking, fire-and-forget manner.
        """
        if not self._client:
            logger.warning("Attempted to publish without an active MQTT connection.")
            return

        async def _do_publish():
            try:
                # Support both dicts (for JSON) and empty strings (for clearing retained)
                if isinstance(payload, dict):
                    final_payload = json.dumps(payload)
                else:
                    final_payload = payload

                await self._client.publish(
                    topic, payload=final_payload, qos=qos, retain=retain
                )
            except Exception as e:
                # Per Fail-Silent Telemetry principle, we log errors but don't propagate them.
                logger.error(f"Failed to publish MQTT message to topic '{topic}': {e}")

        asyncio.create_task(_do_publish())

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        """Subscribes to a topic to receive messages."""
        if not self._client:
            logger.warning("Attempted to subscribe without an active MQTT connection.")
            return

        # 1. Register callback locally
        self._subscriptions[topic] = callback

        # 2. Send subscribe command to broker
        try:
            await self._client.subscribe(topic)
        except Exception as e:
            logger.error(f"Failed to subscribe to topic '{topic}': {e}")

    @staticmethod
    def _topic_matches(subscription: str, topic: str) -> bool:
        """
        Checks if a concrete topic matches a subscription pattern (supporting + and #).
        """
        if subscription == topic:
            return True
        
        sub_parts = subscription.split("/")
        topic_parts = topic.split("/")

        for i, sub_part in enumerate(sub_parts):
            if sub_part == "#":
                # '#' matches the rest of the topic
                return True
            
            if i >= len(topic_parts):
                # Topic is shorter than subscription (and not matched by #)
                return False
            
            topic_part = topic_parts[i]
            
            if sub_part == "+":
                # '+' matches any single level
                continue
            
            if sub_part != topic_part:
                return False
        
        # Ensure lengths match (unless ended with #, handled above)
        return len(sub_parts) == len(topic_parts)

    async def _message_loop(self):
        """Background task to process incoming MQTT messages."""
        if not self._client:
            return

        try:
            # Iterate over the messages asynchronous generator provided by aiomqtt
            async for message in self._client.messages:
                topic = str(message.topic)
                payload_bytes = message.payload

                # Dispatch to all matching subscriptions
                # We iterate over all subscriptions because a single message 
                # might match multiple patterns (e.g. "a/b" matches "a/+" and "#")
                matched_callbacks = []
                for sub_pattern, cb in self._subscriptions.items():
                    if self._topic_matches(sub_pattern, topic):
                        matched_callbacks.append(cb)
                
                if not matched_callbacks:
                    continue

                # Decode payload once
                try:
                    # aiomqtt payload can be bytes, bytearray, etc.
                    if isinstance(payload_bytes, (bytes, bytearray)):
                        payload_str = payload_bytes.decode("utf-8")
                    else:
                        payload_str = str(payload_bytes)

                    # If the payload is empty (resume command), pass an empty dict
                    if not payload_str:
                        data = {}
                    else:
                        data = json.loads(payload_str)

                    # Execute all matched callbacks
                    for cb in matched_callbacks:
                        await cb(topic, data)

                except json.JSONDecodeError:
                    logger.error(f"Received non-JSON payload on topic '{topic}'")
                except Exception as e:
                    logger.error(f"Error processing message on topic '{topic}': {e}")

        except asyncio.CancelledError:
            # Normal shutdown
            pass
        except Exception as e:
            # Unexpected error in loop, log it.
            # In a robust system we might want to restart the loop.
            logger.error(f"MQTT message loop crashed: {e}")
