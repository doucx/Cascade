import pytest
from unittest.mock import AsyncMock

from cascade.spec.physics import DataNode, FuncNode, Token, Port
from cascade.vm.reactor import Reactor, TokenGenerated, ExecutionFinished
from cascade.runtime.resource_manager import ResourceManager

# --- Helpers ---


def create_topology(n_nodes: int):
    nodes = []
    inputs = []
    for i in range(n_nodes):
        f_node = FuncNode(
            name=f"task_{i}",
            canonical_code_structure_hash=f"hash_task_{i}",
            resource_requirements={"slots": 1},
        )
        d_in = DataNode(name=f"in_{i}")
        f_node.add_input(Port(name="arg", source=d_in))
        nodes.append(f_node)
        inputs.append(d_in)
    return nodes, inputs


# --- Tests ---


@pytest.mark.asyncio
async def test_step_respects_resource_limits():
    """
    Verifies that a single call to step() does not over-commit resources.
    """
    rm = ResourceManager(capacity={"slots": 1})
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor, resource_manager=rm)

    func_nodes, data_nodes = create_topology(4)
    for n in func_nodes + data_nodes:
        reactor.register_node(n)

    for d in data_nodes:
        reactor.push_event(TokenGenerated(node=d, token=Token(1)))

    # Action: Single Step
    await reactor.step()

    # Assertion: Only 1 task submitted despite 4 being ready
    assert mock_executor.submit.call_count == 1


@pytest.mark.asyncio
async def test_manual_stepping_processes_pending_queue():
    """
    Verifies the state machine logic:
    If we manually release resources and call step() again,
    the reactor should pick up the pending task.

    This tests the 'step' logic in isolation, without relying on 'run' loop magic.
    """
    rm = ResourceManager(capacity={"slots": 1})
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor, resource_manager=rm)

    func_nodes, data_nodes = create_topology(2)
    node_a, node_b = func_nodes

    for n in func_nodes + data_nodes:
        reactor.register_node(n)

    # Trigger both
    for d in data_nodes:
        reactor.push_event(TokenGenerated(node=d, token=Token(1)))

    # Step 1: Fire first task
    await reactor.step()
    assert mock_executor.submit.call_count == 1

    # Identify running node
    submitted_node = mock_executor.submit.call_args[0][0]

    # Simulate completion event (which should release resources in the next step)
    reactor.push_event(ExecutionFinished(node=submitted_node, outputs={}))

    # Step 2: Process completion & fire second task
    # The reactor should process the ExecutionFinished event, release the resource,
    # re-evaluate the pending queue, and fire the next node.
    await reactor.step()

    assert mock_executor.submit.call_count == 2
