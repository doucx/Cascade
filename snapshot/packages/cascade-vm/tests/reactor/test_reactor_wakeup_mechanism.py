import pytest
import asyncio
from unittest.mock import AsyncMock

from cascade.spec.physics import DataNode, FuncNode, Token, Port
from cascade.vm.reactor import Reactor, TokenGenerated, ExecutionFinished
from cascade.runtime.resource_manager import ResourceManager


def create_topology(n_nodes: int):
    """Creates a simple fan-out topology."""
    nodes, inputs = [], []
    for i in range(n_nodes):
        f_node = FuncNode(name=f"task_{i}", resource_requirements={"slots": 1})
        d_in = DataNode(name=f"in_{i}")
        f_node.add_input(Port(name="arg", source=d_in))
        nodes.append(f_node)
        inputs.append(d_in)
    return nodes, inputs


@pytest.mark.asyncio
async def test_reactor_proactively_wakes_up_on_resource_release():
    """
    Phase 4.2 TDD (Strict): Reactor must wake up internally, not via polling.

    This test calls `step()` only ONCE. It simulates a fast task that
    finishes and emits an ExecutionFinished event *during* the initial step.
    A truly event-driven reactor should process this new event and schedule
    the next pending task without needing another external `step()` call.
    """
    rm = ResourceManager(capacity={"slots": 1})
    mock_executor = AsyncMock()

    # Synchronization primitive: this event is set when the SECOND task is submitted
    second_task_submitted = asyncio.Event()

    # --- Mock Executor Side Effect ---
    # This is the core of the test's strictness.
    # When the first task is submitted, it immediately pushes its own "Finished" event back.
    # When the second task is submitted, it signals the test to finish.
    async def executor_side_effect(node, inputs):
        if mock_executor.submit.call_count == 1:
            # First task: immediately signal completion
            # This pushes an event into the queue WHILE a step() is active.
            reactor.push_event(ExecutionFinished(node=node, outputs={}))
        elif mock_executor.submit.call_count == 2:
            # Second task: signal success to the test harness
            second_task_submitted.set()

    mock_executor.submit.side_effect = executor_side_effect
    # ---

    reactor = Reactor(executor=mock_executor, resource_manager=rm)

    # 1. Setup A and B
    func_nodes, data_nodes = create_topology(2)
    for n in func_nodes + data_nodes:
        reactor.register_node(n)

    # 2. Trigger both tasks to be ready
    for d in data_nodes:
        reactor.push_event(TokenGenerated(node=d, token=Token(1)))

    # 3. Action: Call step() only ONCE.
    # Expected internal flow:
    # - step() starts.
    # - Processes TokenGenerated events. Both A and B are now data-ready.
    # - Fires task A. B becomes pending.
    # - `executor.submit(A)` is called.
    # - Side effect triggers, pushing `ExecutionFinished(A)` into the event queue.
    # - A truly event-driven reactor would re-loop, process this event, release
    #   resources, and re-evaluate pending tasks, thus firing B.
    # - `executor.submit(B)` is called.
    # - Side effect triggers, setting `second_task_submitted`.
    await reactor.step()

    # 4. Assertion: Wait for the event signaling the second task was submitted.
    # The current implementation will fail here (timeout) because it finishes the
    # `step()` after submitting task A and does not re-process the new event.
    try:
        await asyncio.wait_for(second_task_submitted.wait(), timeout=0.5)
    except asyncio.TimeoutError:
        pytest.fail(
            "Reactor did not proactively wake up and schedule the second task. "
            f"Only {mock_executor.submit.call_count} task(s) were submitted."
        )

    assert mock_executor.submit.call_count == 2