import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Component imports
from cascade.spec.physics import DataNode, FuncNode, Token, Port
from cascade.vm.reactor import Reactor, TokenGenerated, ExecutionFinished
from cascade.runtime.resource_manager import ResourceManager

# --- Helpers ---

def create_topology(n_nodes: int):
    """
    Creates a simple fan-out topology: 
    n independent FuncNodes, each fed by a dedicated DataNode.
    """
    nodes = []
    inputs = []
    
    for i in range(n_nodes):
        f_node = FuncNode(name=f"task_{i}")
        # Dynamically attach resource requirements (Phase 4 requirement)
        # We assume the task needs 1 "slot"
        f_node.resource_requirements = {"slots": 1}
        
        d_in = DataNode(name=f"in_{i}")
        f_node.add_input(Port(name="arg", source=d_in))
        
        nodes.append(f_node)
        inputs.append(d_in)
        
    return nodes, inputs

# --- Tests ---

@pytest.mark.asyncio
async def test_reactor_respects_resource_concurrency_limit():
    """
    Phase 4.1 TDD: Ensure Reactor respects global resource constraints.
    
    Scenario:
    - System has 'slots': 1.
    - 4 tasks are ready to run, each requiring 'slots': 1.
    - Current Reactor (Greedy) would submit all 4.
    - Expected Reactor (Physics-Aware) should submit only 1.
    """
    # 1. Setup Resource Manager
    # We use a real ResourceManager to integration test the interaction
    rm = ResourceManager(capacity={"slots": 1})
    
    # 2. Setup Reactor with Resource Manager
    mock_executor = AsyncMock()
    # NOTE: This API (resource_manager arg) does not exist yet. 
    # This will cause a TypeError, marking the start of TDD.
    reactor = Reactor(executor=mock_executor, resource_manager=rm)
    
    # 3. Setup Topology
    func_nodes, data_nodes = create_topology(4)
    for f in func_nodes:
        reactor.register_node(f)
    for d in data_nodes:
        reactor.register_node(d)
        
    # 4. Trigger: All inputs become excited simultaneously
    for d in data_nodes:
        reactor.push_event(TokenGenerated(node=d, token=Token(1)))
        
    # 5. Action: Step the reactor
    await reactor.step()
    
    # 6. Assertion
    # If greedy (current), call_count will be 4.
    # If resource-aware (target), call_count should be 1.
    assert mock_executor.submit.call_count == 1, (
        f"Reactor violated resource limits! Expected 1 submission, "
        f"got {mock_executor.submit.call_count}."
    )


@pytest.mark.asyncio
async def test_reactor_waits_for_resources_and_wakes_up():
    """
    Phase 4.2 TDD: Ensure Reactor wakes up pending tasks when resources are released.
    
    Scenario:
    - System has 'slots': 1.
    - Task A runs (consuming 1 slot). Task B is pending.
    - Task A finishes -> releases slot.
    - Reactor should detect this and schedule Task B.
    """
    rm = ResourceManager(capacity={"slots": 1})
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor, resource_manager=rm)
    
    # 1. Setup A and B
    func_nodes, data_nodes = create_topology(2)
    node_a, node_b = func_nodes
    in_a, in_b = data_nodes
    
    for n in func_nodes + data_nodes:
        reactor.register_node(n)
        
    # 2. Trigger both
    reactor.push_event(TokenGenerated(node=in_a, token=Token(1)))
    reactor.push_event(TokenGenerated(node=in_b, token=Token(1)))
    
    # 3. Step 1: Should fire Node A (arbitrary order, but only 1)
    await reactor.step()
    assert mock_executor.submit.call_count == 1
    
    # Identify which one ran
    submitted_node = mock_executor.submit.call_args[0][0]
    remaining_node = node_b if submitted_node == node_a else node_a
    
    # 4. Simulate Completion of the running task
    # This logic assumes Reactor will hook into ExecutionFinished to release resources
    # OR that we need to manually release resources in this test if Reactor isn't doing it yet.
    # The 'ExecutionFinished' event is the standard signal.
    # However, ResourceManager release usually happens via `await rm.release()` inside the reactor loop 
    # or callback.
    
    # We push the completion event.
    # IMPORTANT: For this test to pass in the future, Reactor._handle_execution_finished
    # must trigger resource release.
    reactor.push_event(ExecutionFinished(node=submitted_node, outputs={}))
    
    # 5. Step 2: Should process completion, release resource, and fire Node B
    await reactor.step()
    
    # 6. Assertion
    assert mock_executor.submit.call_count == 2, "Reactor failed to schedule pending task after resource release."
    
    # Verify the second call was for the remaining node
    last_submitted = mock_executor.submit.call_args[0][0]
    assert last_submitted == remaining_node