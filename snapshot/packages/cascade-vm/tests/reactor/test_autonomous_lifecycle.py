import pytest
import asyncio
from unittest.mock import AsyncMock

from cascade.spec.physics import DataNode, FuncNode, Token, Port, TerminatorNode
from cascade.vm.reactor import Reactor, TokenGenerated, ExecutionFinished
from cascade.runtime.resource_manager import ResourceManager

# --- Helpers ---

def create_simple_chain():
    """Creates a simple D -> F -> D chain."""
    d_in = DataNode(name="in")
    d_out = DataNode(name="out")
    f_node = FuncNode(name="process", resource_requirements={"slots": 1})
    
    f_node.add_input(Port(name="arg", source=d_in))
    f_node.add_output(Port(name="res", target=d_out))
    
    return [f_node], [d_in, d_out]

# --- Tests ---

@pytest.mark.asyncio
async def test_reactor_runs_forever_without_terminator():
    """
    Verifies the default behavior: The Reactor run loop does NOT exit automatically
    when the graph becomes idle. It waits indefinitely for new events.
    """
    rm = ResourceManager(capacity={"slots": 1})
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor, resource_manager=rm)
    
    # 1. Setup minimal topology
    func_nodes, data_nodes = create_simple_chain()
    for n in func_nodes + data_nodes:
        reactor.register_node(n)
        
    # 2. Start Reactor
    run_task = asyncio.create_task(reactor.run())
    
    # 3. Inject work
    reactor.push_event(TokenGenerated(node=data_nodes[0], token=Token(1)))
    
    # 4. Mock executor completion
    async def side_effect(node, inputs):
        reactor.push_event(ExecutionFinished(node=node, outputs={}))
    mock_executor.submit.side_effect = side_effect
    
    # 5. Wait and Expect Timeout
    # wait_for will cancel run_task on timeout
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(run_task, timeout=0.2)
        
    # Cleanup: Ensure task is cancelled/stopped properly
    reactor.stop()
    try:
        await run_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_reactor_terminates_via_terminator_node():
    """
    Verifies the "Suicide Pact":
    When a TerminatorNode is fired, the Reactor should call stop() on itself
    and the run() loop should return.
    """
    rm = ResourceManager(capacity={"slots": 1})
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor, resource_manager=rm)
    
    # 1. Setup Topology: DataNode -> Terminator
    d_in = DataNode(name="trigger")
    terminator = TerminatorNode(name="term", resource_requirements={"slots": 1})
    terminator.add_input(Port(name="signal", source=d_in))
    
    reactor.register_node(d_in)
    reactor.register_node(terminator)
    
    # 2. Start Reactor
    run_task = asyncio.create_task(reactor.run())
    
    # 3. Trigger the terminator
    reactor.push_event(TokenGenerated(node=d_in, token=Token("DIE")))
    
    # 4. Expectation: The run loop should exit gracefully WITHOUT timeout
    # If it times out, the logic is broken.
    try:
        await asyncio.wait_for(run_task, timeout=1.0)
    except asyncio.TimeoutError:
        reactor.stop()
        try:
            await run_task
        except asyncio.CancelledError:
            pass
        pytest.fail("Reactor failed to terminate automatically upon triggering TerminatorNode")
    
    # Assert stop was called (run loop exited)
    assert run_task.done()
    assert not run_task.cancelled()