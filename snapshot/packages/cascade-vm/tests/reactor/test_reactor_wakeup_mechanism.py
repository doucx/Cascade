import pytest
import asyncio
from unittest.mock import AsyncMock

from cascade.spec.physics import DataNode, FuncNode, Token, Port
from cascade.vm.reactor import Reactor, TokenGenerated, ExecutionFinished
from cascade.runtime.resource_manager import ResourceManager

def create_topology(n_nodes: int):
    nodes, inputs = [], []
    for i in range(n_nodes):
        f_node = FuncNode(name=f"task_{i}", resource_requirements={"slots": 1})
        d_in = DataNode(name=f"in_{i}")
        f_node.add_input(Port(name="arg", source=d_in))
        nodes.append(f_node)
        inputs.append(d_in)
    return nodes, inputs

@pytest.mark.asyncio
async def test_run_loop_proactively_schedules_tasks():
    """
    Verifies that reactor.run() forms a continuous loop that:
    1. Waits for events when idle.
    2. Wakes up when events occur.
    3. Automatically schedules pending tasks when resources become available.
    """
    rm = ResourceManager(capacity={"slots": 1})
    mock_executor = AsyncMock()
    
    # We need a reactor that supports run() and stop()
    reactor = Reactor(executor=mock_executor, resource_manager=rm)
    
    # Synchronization: Wait for 2 tasks to complete
    completion_event = asyncio.Event()
    completed_count = 0

    # Side effect to simulate async execution flow
    async def executor_submit(node, inputs):
        # Simulate task finishing immediately by pushing event back to reactor
        # This tests if reactor.run() picks up the new event automatically
        reactor.push_event(ExecutionFinished(node=node, outputs={}))
        
        nonlocal completed_count
        completed_count += 1
        if completed_count == 2:
            completion_event.set()

    mock_executor.submit.side_effect = executor_submit

    # 1. Setup Topology
    func_nodes, data_nodes = create_topology(2)
    for n in func_nodes + data_nodes:
        reactor.register_node(n)

    # 2. Start Reactor in background
    # This expects reactor.run() to be implemented
    run_task = asyncio.create_task(reactor.run())

    # 3. Inject Initial State
    for d in data_nodes:
        reactor.push_event(TokenGenerated(node=d, token=Token(1)))

    # 4. Wait for completion
    # If run() is not implemented or doesn't loop, this will timeout.
    try:
        await asyncio.wait_for(completion_event.wait(), timeout=1.0)
    except asyncio.TimeoutError:
        reactor.stop()
        await run_task
        pytest.fail("Reactor run loop failed to process sequence within timeout.")

    # 5. Cleanup
    # Verify we can stop the reactor cleanly
    reactor.stop()
    await run_task
    
    assert mock_executor.submit.call_count == 2