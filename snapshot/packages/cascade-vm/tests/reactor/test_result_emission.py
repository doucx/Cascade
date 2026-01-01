import pytest
import asyncio
from unittest.mock import AsyncMock

from cascade.spec.physics import DataNode, Token, Port, EmitterNode
from cascade.vm.reactor import Reactor, TokenGenerated

@pytest.mark.asyncio
async def test_reactor_emits_result_to_sink(event_loop):
    """
    Verifies that an EmitterNode correctly pushes data to an external sink,
    and that the Reactor can be gracefully stopped by an external controller
    after the emission occurs.
    
    This test validates the decoupled lifecycle model.
    """
    # 1. Setup simplified topology: D_in -> Emitter
    d_in = DataNode(name="result_slot")
    emitter = EmitterNode(name="emit", sink_id="main_output")
    emitter.add_input(Port(name="data", source=d_in))
    
    # 2. Setup Reactor and Mock Executor
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor)
    reactor.register_node(d_in)
    reactor.register_node(emitter)
    
    # 3. Register Sink with a Future for synchronization
    # The Future acts as the signal from the Reactor to the external world
    result_future = event_loop.create_future()
    reactor.register_sink("main_output", result_future.set_result)

    # 4. Start Reactor in a background task
    run_task = asyncio.create_task(reactor.run())
    
    # 5. Inject Initial Data to trigger the Emitter
    reactor.push_event(TokenGenerated(node=d_in, token=Token("Hello World")))
    
    # 6. Wait for the core work to be done (result emitted)
    # This is the key synchronization point.
    try:
        emitted_result = await asyncio.wait_for(result_future, timeout=1.0)
    except asyncio.TimeoutError:
        # If timeout, it means the Emitter never fired.
        reactor.stop()
        await run_task
        pytest.fail("Sink was never called. EmitterNode logic is likely broken.")
    
    # 7. Assert the emitted result
    assert emitted_result == "Hello World"

    # 8. Explicitly stop the reactor (External Lifecycle Control)
    reactor.stop()
    
    # 9. Await the run task to ensure it shut down cleanly
    await run_task