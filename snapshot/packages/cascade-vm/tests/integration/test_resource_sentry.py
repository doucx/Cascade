import asyncio
import pytest

from cascade.compiler.backend import Builder
from cascade.compiler.frontend import IRGenerator
from cascade.reflection import ReflectionAnalyzer
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.spec.dsl.task import task
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
from cascade.compiler.utils.inspector import GraphInspector
from cascade.runtime.services.observability.events import (
    Event,
    TaskExecutionStarted,
    TaskExecutionFinished,
)


@task
async def gpu_task(val: int) -> int:
    await asyncio.sleep(0.01)
    return val * 2


@pytest.mark.asyncio
async def test_sentry_parks_and_releases_correctly():
    # 1. Define a resource-constrained environment
    env = EnvironmentDef(
        resources=[ResourceDef(name="gpu", capacity=1, type="discrete")]
    )
    registry = CodeRegistry()

    # Dynamically compute the hash at test time to avoid fragility.
    analyzer = ReflectionAnalyzer()
    task_def = analyzer.analyze(gpu_task)
    gpu_task_hash = task_def.fingerprint["canonical_code_structure_hash"]
    registry.register(gpu_task_hash, gpu_task)

    # 2. Define two concurrent tasks competing for the same resource
    task_a = gpu_task(10).with_constraints(gpu=1)
    task_b = gpu_task(20).with_constraints(gpu=1)

    # 3. Compile the graph
    ir_generator = IRGenerator()
    graph_ir = ir_generator.generate([task_a, task_b])

    builder = Builder()
    artifact = builder.build(graph_ir, env)
    assembly = artifact.assembly

    # 4. Setup Runner and Inspector
    runner = EventDrivenRunner.from_assembly(assembly, registry)
    inspector = GraphInspector(assembly.graph)

    # Deterministically get key node IDs
    d_parked_id = "parked.req.gpu"
    d_signal_id = "signal.wakeup.gpu"
    f_gate_id = "gate.wakeup.gpu"
    inspector.assert_node_exists(d_parked_id)
    inspector.assert_node_exists(d_signal_id)
    inspector.assert_node_exists(f_gate_id)

    # 5. Execute and Assert
    runner.prime()
    await runner.start_loop()

    try:
        # --- Phase 1: Parking ---
        # One task should start, the other should be parked.
        started_events = []

        def is_started(e: Event):
            if isinstance(e, TaskExecutionStarted):
                started_events.append(e)
                return True
            return False

        first_started_event = await runner.wait_for_event(is_started, timeout=1.0)
        assert len(started_events) == 1
        # Directly assert that one request token is now in the parking lot
        assert runner.memory.get_count(d_parked_id) == 1, (
            "A task should have been parked"
        )

        # --- Phase 2 & 3: Signaling & Gating ---
        # Wait for the first task to finish, which triggers the signal and gate
        def is_finished(e: Event):
            return (
                isinstance(e, TaskExecutionFinished)
                and e.task_id == first_started_event.task_id
            )

        await runner.wait_for_event(is_finished, timeout=1.0)

        # The most reliable proof of signaling and gating is that the second task starts.
        # After the first finishes, the gate should fire almost instantly,
        # moving the token from D_parked to D_req, which then starts the second task.
        second_started_event = await runner.wait_for_event(is_started, timeout=1.0)
        assert len(started_events) == 2
        assert runner.memory.get_count(d_parked_id) == 0, "Parking lot should be empty"

        # --- Phase 4: Final Completion ---
        # Wait for the second task to complete
        def is_second_finished(e: Event):
            return (
                isinstance(e, TaskExecutionFinished)
                and e.task_id == second_started_event.task_id
            )

        await runner.wait_for_event(is_second_finished, timeout=1.0)

        # Verify final state
        finished_events = [
            e for e in runner._captured_events if isinstance(e, TaskExecutionFinished)
        ]
        assert len(finished_events) == 2
        assert all(e.status == "Succeeded" for e in finished_events)

    finally:
        await runner.stop_loop()
