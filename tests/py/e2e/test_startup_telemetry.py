import pytest
import asyncio
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus
from cascade.runtime.subscribers import TelemetrySubscriber
from .harness import InProcessConnector

@pytest.mark.asyncio
async def test_startup_telemetry_no_race_condition():
    """
    Verifies that the initial 'RunStarted' telemetry event is correctly published
    to the connector.
    
    This guards against a race condition where the engine emits 'RunStarted'
    internally *before* establishing the connection to the external connector,
    causing the first telemetry message to be lost (and a warning logged).
    """
    # 1. Setup Harness
    connector = InProcessConnector()
    bus = MessageBus()
    
    # CRITICAL: Manually assemble the TelemetrySubscriber, which bridges
    # the internal event bus to the external connector. This is what cs.run()
    # does automatically.
    telemetry_subscriber = TelemetrySubscriber(bus, connector)
    
    # We will act as an external observer subscribing to the telemetry topic.
    # Since InProcessConnector routes messages internally, we can subscribe 
    # on the same instance that the Engine uses.
    received_messages = []
    
    async def telemetry_observer(topic, payload):
        received_messages.append(payload)
    
    # Subscribe to all telemetry events
    # Note: We must ensure the connector considers itself "connected" enough 
    # to register this subscription, or at least that the subscription persists.
    # InProcessConnector.subscribe doesn't check _is_connected strictness for 
    # registration, but Engine will call connect() shortly.
    await connector.subscribe("cascade/telemetry/+/+/+/events", telemetry_observer)
    
    # 2. Define Workflow
    @cs.task
    def noop():
        pass
        
    # 3. Run Engine
    # The Engine is expected to:
    #   a. Connect to the connector
    #   b. Publish 'RunStarted' (which triggers telemetry via the subscriber)
    #   c. Run the task
    # If (b) happens before (a), the message is dropped.
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=connector,
    )
    # CRITICAL: Register the subscriber with the engine for lifecycle management
    engine.add_subscriber(telemetry_subscriber)
    
    await engine.run(noop())
    
    # 4. Assert
    # Verify we caught the ENGINE_STARTED event
    has_start_event = False
    for msg in received_messages:
        body = msg.get("body", {})
        if body.get("type") == "LifecycleEvent" and body.get("event") == "ENGINE_STARTED":
            has_start_event = True
            break
            
    assert has_start_event, (
        "Failed to receive ENGINE_STARTED telemetry event. "
        "It was likely published before the connector was active."
    )