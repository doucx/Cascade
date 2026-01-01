import pytest
import asyncio
from unittest.mock import AsyncMock

from cascade.spec.physics import DataNode, Token, Port, EmitterNode, TerminatorNode
from cascade.vm.reactor import Reactor, TokenGenerated
from cascade.runtime.resource_manager import ResourceManager

@pytest.mark.asyncio
async def test_reactor_emits_result_to_sink_sequentially():
    """
    Verifies that an EmitterNode correctly pushes data to a sink, and THEN
    a chained TerminatorNode successfully stops the reactor.
    
    Topology: D_in -> Emitter -> D_signal -> Terminator
    """
    rm = ResourceManager(capacity={"slots": 1})
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor, resource_manager=rm)
    
    # 1. Setup Sequential Topology
    d_in = DataNode(name="result_slot")
    d_signal = DataNode(name="signal_slot") # Connects Emitter and Terminator
    
    # Emitter: Reads from d_in, sends to "main_output", signals to d_signal
    emitter = EmitterNode(name="emit", sink_id="main_output")
    emitter.add_input(Port(name="data", source=d_in))
    emitter.add_output(Port(name="result", target=d_signal)) # Output for signaling
    
    # Terminator: Reads from d_signal, stops the reactor
    terminator = TerminatorNode(name="term")
    terminator.add_input(Port(name="signal", source=d_signal))
    
    reactor.register_node(d_in)
    reactor.register_node(d_signal)
    reactor.register_node(emitter)
    reactor.register_node(terminator)
    
    # 2. Register Sink
    result_future = asyncio.Future()
    reactor.register_sink("main_output", result_future.set_result)

    # 3. Start Reactor
    run_task = asyncio.create_task(reactor.run())
    
    # 4. Inject Initial Data
    reactor.push_event(TokenGenerated(node=d_in, token=Token("Hello World")))
    
    # 5. Wait for Reactor to terminate on its own
    try:
        await asyncio.wait_for(run_task, timeout=1.0)
    except asyncio.TimeoutError:
        # If timeout, it means the terminator was never reached.
        reactor.stop()
        try:
            await run_task
        except asyncio.CancelledError:
            pass
        pytest.fail("Reactor did not terminate. The Emitter->Terminator signal chain is broken.")
    
    # 6. Verify Result from Sink
    try:
        result = result_future.result()
        assert result == "Hello World"
    except asyncio.InvalidStateError:
        pytest.fail("Sink was never called with the result, even though Reactor terminated.")