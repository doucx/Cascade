import pytest
import asyncio
from unittest.mock import AsyncMock

from cascade.spec.physics import DataNode, FuncNode, Token, Port
from cascade.spec.topology import PhysicsTerminatorNode
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
    
    # 4. Mock executor completion to allow the task to 'finish'
    async def side_effect(node, inputs):
        reactor.push_event(ExecutionFinished(node=node, outputs={}))
    mock_executor.submit.side_effect = side_effect
    
    # 5. Wait and Expect Timeout
    # Even after the task finishes, the reactor should stay alive waiting for more.
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(run_task, timeout=0.5)
        
    # Cleanup
    reactor.stop()
    await run_task


@pytest.mark.asyncio
async def test_reactor_terminates_via_terminator_node():
    """
    Verifies the "Suicide Pact":
    When a PhysicsTerminatorNode is fired, the Reactor should call stop() on itself
    and the run() loop should return.
    
    NOTE: This test is expected to FAIL (Timeout) until Reactor implements Terminator handling.
    """
    rm = ResourceManager(capacity={"slots": 1})
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor, resource_manager=rm)
    
    # 1. Setup Topology: DataNode -> Terminator
    # We need to manually register the TerminatorNode because it's not a FuncNode
    # and might not be supported by register_node yet (depending on implementation).
    # Ideally, Reactor should treat TerminatorNode as a special FuncNode or similar.
    
    d_in = DataNode(name="trigger")
    
    # Note: PhysicsTerminatorNode is a Spec object (static). 
    # The Reactor needs a runtime representation (Physics object) for it.
    # For now, let's assume we reuse the Spec object as the runtime object identifier
    # or wrap it.
    # But wait, Reactor operates on `cascade.spec.physics.FuncNode`. 
    # PhysicsTerminatorNode is from `cascade.spec.topology` (Backend output).
    # We need a runtime equivalent in `cascade.spec.physics` or just use FuncNode 
    # with a special flag/type?
    
    # Architecture alignment:
    # `cascade.spec.topology` defines the Static Blueprint.
    # `cascade.spec.physics` defines the Runtime Objects.
    # We need a runtime representation for Terminator.
    
    # Strategy:
    # For this test, we can use a standard FuncNode but give it a special property 
    # or register it specially in the Reactor to mimic what the VM would do when 
    # loading a PhysicsTerminatorNode.
    
    # However, to properly test the Reactor's logic, we should probably add a 
    # TerminatorNode class to `cascade.spec.physics` as well?
    # Or, Reactor should recognize a specific type of node.
    
    # Let's define a runtime Terminator in the test for now, or use a duck-typed object.
    # The clean way is to add TerminatorNode to `cascade.spec.physics`.
    pass 
    # Deferring implementation details to the next step when we actually implement the logic.
    # For now, let's try to use a standard FuncNode but we expect the Reactor 
    # to treat it differently based on registration.
    
    # Wait, the user requirement is to use PhysicsTerminatorNode.
    # But PhysicsTerminatorNode is a dataclass for the static graph.
    # The VM (Machine.py) translates Static -> Dynamic.
    # The Reactor (Core.py) runs Dynamic nodes.
    
    # So we need a Dynamic Terminator Node.
    from cascade.spec.physics import FuncNode
    
    class RuntimeTerminator(FuncNode):
        """Runtime representation of a terminator."""
        pass

    terminator = RuntimeTerminator(name="term")
    terminator.add_input(Port(name="signal", source=d_in))
    
    reactor.register_node(d_in)
    reactor.register_node(terminator)
    
    # 2. Start Reactor
    run_task = asyncio.create_task(reactor.run())
    
    # 3. Trigger the terminator
    reactor.push_event(TokenGenerated(node=d_in, token=Token("DIE")))
    
    # 4. Expectation: The run loop should exit gracefully
    try:
        await asyncio.wait_for(run_task, timeout=1.0)
    except asyncio.TimeoutError:
        reactor.stop()
        await run_task
        pytest.fail("Reactor failed to terminate automatically upon triggering TerminatorNode")