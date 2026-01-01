import pytest
import asyncio
from unittest.mock import AsyncMock

from cascade.spec.physics import DataNode, Token, Port, EmitterNode, TerminatorNode
from cascade.vm.reactor import Reactor, TokenGenerated
from cascade.runtime.resource_manager import ResourceManager

@pytest.mark.asyncio
async def test_reactor_emits_result_to_sink():
    """
    Verifies that an EmitterNode correctly pushes data to a registered external sink.
    
    Topology: DataNode -> EmitterNode -> TerminatorNode
    
    Flow:
    1. Inject token "Hello World" into DataNode.
    2. EmitterNode picks it up and (should) push to sink.
    3. TerminatorNode picks it up (via shared input or sequence) and stops reactor.
    
    For simplicity in this unit test, we wire:
    DataNode -> EmitterNode
             -> TerminatorNode (Parallel consumption or just separate trigger)
             
    Actually, to ensure we capture the emission BEFORE termination, 
    we should probably chain them if possible, or just rely on the Reactor processing 
    events in order. 
    
    Let's use a shared DataNode for simplicity. Both Emitter and Terminator listen to it.
    """
    rm = ResourceManager(capacity={"slots": 1})
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor, resource_manager=rm)
    
    # 1. Setup Topology
    d_in = DataNode(name="result_slot")
    
    # Emitter: Sends data to "main_output"
    emitter = EmitterNode(name="emit", sink_id="main_output", resource_requirements={"slots": 1})
    emitter.add_input(Port(name="data", source=d_in))
    
    # Terminator: Stops the reactor
    terminator = TerminatorNode(name="term", resource_requirements={"slots": 1})
    terminator.add_input(Port(name="signal", source=d_in))
    
    reactor.register_node(d_in)
    reactor.register_node(emitter)
    reactor.register_node(terminator)
    
    # 2. Register Sink
    # API Requirement: Reactor must support sink registration
    result_future = asyncio.Future()
    
    # NOTE: This method does not exist yet (RED)
    if hasattr(reactor, "register_sink"):
        reactor.register_sink("main_output", result_future.set_result)
    else:
        # If API is missing, we fail fast, but for TDD strictness we might want to 
        # allow the code to run and fail on the result not being set.
        # But we need to call the API to define it.
        # Let's assume we implement it in the next step.
        # For now, we simulate the API call failure or just skip if we want "RuntimeError".
        # But to be clean, let's call it and expect AttributeError if not implemented.
        try:
            reactor.register_sink("main_output", result_future.set_result)
        except AttributeError:
            pytest.fail("Reactor.register_sink API is missing")

    # 3. Start Reactor
    run_task = asyncio.create_task(reactor.run())
    
    # 4. Inject Result
    reactor.push_event(TokenGenerated(node=d_in, token=Token("Hello World")))
    
    # 5. Wait for completion
    try:
        # Wait for reactor to stop (triggered by Terminator)
        await asyncio.wait_for(run_task, timeout=1.0)
    except asyncio.TimeoutError:
        # The test failed because the reactor didn't stop in time.
        # The run_task is already cancelled by wait_for.
        reactor.stop()
        try:
            # Awaiting a cancelled task raises CancelledError, we absorb it.
            await run_task
        except asyncio.CancelledError:
            pass
        pytest.fail("Reactor failed to terminate automatically")
    
    # 6. Verify Result
    # This logic now correctly executes for both success and failure paths,
    # but the fail path is handled by pytest.fail above.
    assert result_future.done(), "Future was not resolved"
    assert result_future.result() == "Hello World"