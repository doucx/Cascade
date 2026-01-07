import asyncio
import pytest
from typing import List

from cascade import sdk as cs
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
from cascade.compiler.utils import GraphInspector
from cascade.runtime.services.observability.events import (
    Event,
    TaskExecutionStarted,
    TaskExecutionFinished,
)
from cascade.spec.physical.ports import PortName


@cs.task
async def resource_user(duration: float = 0.01) -> str:
    await asyncio.sleep(duration)
    return "done"


@pytest.mark.asyncio
async def test_gated_contention_and_wakeup():
    """
    Tests the full lifecycle of the "Topology Gating" model:
    1. Two tasks compete for one resource slot.
    2. The first task gets the resource.
    3. The second task's request is parked in D_parked.
    4. The first task finishes, releasing the resource and sending a signal.
    5. The gate fires, moving the second task's request back to the main buffer.
    6. The second task acquires the resource and runs to completion.
    """
    # 1. Define Logical Workflow
    task1 = resource_user(duration=0.02).with_constraints(gpu=1)
    task2 = resource_user(duration=0.02).with_constraints(gpu=1)

    # 2. Define Environment
    env = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1, type="discrete")])

    # 3. Compile
    ir_gen = IRGenerator()
    graph_ir = ir_gen.generate([task1, task2])

    builder = Builder()
    artifact = builder.build(graph_ir, env)
    assembly = artifact.assembly

    # 4. Static Validation (Assert Topology)
    inspector = GraphInspector(assembly.graph)

    # Assert new nodes exist
    d_parked_id = "parked.req.gpu"
    d_signal_id = "signal.wakeup.gpu"
    f_gate_id = "gate.wakeup.gpu"
    allocator_id = "canonical.resource.allocator.gpu"
    reclaimer_id = "canonical.resource.reclaimer.gpu"
    req_buffer_id = "buffer.req.gpu"

    inspector.assert_node_exists(d_parked_id)
    inspector.assert_node_exists(d_signal_id)
    inspector.assert_node_exists(f_gate_id)

    # Assert new connections are wired correctly
    inspector.assert_connection(allocator_id, d_parked_id, source_port=PortName.REQ_PARKED)
    inspector.assert_connection(reclaimer_id, d_signal_id, source_port=PortName.SIGNAL_OUT)
    inspector.assert_connection(d_parked_id, f_gate_id, target_port="req_in")
    inspector.assert_connection(d_signal_id, f_gate_id, target_port="signal_in")
    inspector.assert_connection(f_gate_id, req_buffer_id, source_port="req_out")

    # 5. Dynamic Validation (Assert Behavior)
    registry = CodeRegistry()
    registry.register(
        resource_user.func.task.fingerprint["canonical_code_structure_hash"],
        resource_user.func,
    )

    runner = EventDrivenRunner.from_assembly(assembly, registry)

    # Prime the system with initial energy
    runner.prime()
    await runner.start_loop()

    # We expect two tasks to start and finish.
    # The key is to verify their execution is serialized by the gate.
    started_events: List[TaskExecutionStarted] = []
    finished_events: List[TaskExecutionFinished] = []

    async def event_collector():
        while len(finished_events) < 2:
            event = await runner.event_queue.get()
            if isinstance(event, TaskExecutionStarted):
                started_events.append(event)
            elif isinstance(event, TaskExecutionFinished):
                finished_events.append(event)

    try:
        await asyncio.wait_for(event_collector(), timeout=2.0)
    finally:
        await runner.stop_loop()

    assert len(started_events) == 2
    assert len(finished_events) == 2
    assert all(e.status == "Succeeded" for e in finished_events)

    # CRITICAL ASSERTION: The start times prove serialization.
    # The second task must have started after the first one finished.
    first_finished = min(e.timestamp for e in finished_events)
    second_started = max(e.timestamp for e in started_events)

    assert second_started >= first_finished