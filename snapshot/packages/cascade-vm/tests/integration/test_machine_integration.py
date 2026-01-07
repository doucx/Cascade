import asyncio
import pytest
from typing import Dict, Callable

from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.triad import BleachNode, WorkerNode, StainNode, ObservabilityNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.reflection import PhysicalIdGenerator
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
from cascade.runtime.services.observability.events import TaskExecutionFinished

# Standard Library ICs
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.system.terminator import halt_signal


# --- Test Fixtures ---


# 1. A simple async user function to be executed by the ComputeService
async def user_square(n: int) -> int:
    await asyncio.sleep(0.01)  # Simulate real async work
    return n * n


# 2. A helper to build the self-terminating physical graph for the test
def build_test_graph() -> BipartiteGraph:
    graph = BipartiteGraph()
    base_id = "task_square"

    # Node IDs
    d_in_id = "d_in"
    d_out_id = "d_out"
    f_halt_id = "f_halt"
    f_bleach_id = PhysicalIdGenerator.bleach_node(base_id)
    d_worker_in_id = PhysicalIdGenerator.worker_in_data(base_id)
    f_worker_id = PhysicalIdGenerator.worker_node(base_id)
    d_worker_out_id = PhysicalIdGenerator.worker_out_data(base_id)
    d_trace_id = PhysicalIdGenerator.trace_data(base_id)
    f_stain_id = PhysicalIdGenerator.stain_node(base_id)

    d_life_id = PhysicalIdGenerator.observability_bus()
    f_obs_id = PhysicalIdGenerator.observability_observer()

    # Node Definitions
    nodes = [
        PhysicsDataNode(id=d_in_id, name="Input"),
        BleachNode(
            id=f_bleach_id,
            name="Bleach(square)",
            input_ports={"n": PortDef("n", PortRole.DATA)},
            output_ports={
                "worker_input": PortDef("worker_input", PortRole.DATA),
                "trace_output": PortDef("trace_output", PortRole.DATA),
                "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY),
            },
        ),
        PhysicsDataNode(id=d_worker_in_id, name="In(square)"),
        WorkerNode(
            id=f_worker_id,
            name="Exec(square)",
            canonical_code_structure_hash="hash_for_user_square",
            input_ports={"worker_input": PortDef("worker_input", PortRole.DATA)},
            output_ports={"worker_result": PortDef("worker_result", PortRole.DATA)},
        ),
        PhysicsDataNode(id=d_worker_out_id, name="Out(square)"),
        PhysicsDataNode(id=d_trace_id, name="Trace(square)"),
        StainNode(
            id=f_stain_id,
            name="Stain(square)",
            input_ports={
                "worker_result": PortDef("worker_result", PortRole.DATA),
                "trace_input": PortDef("trace_input", PortRole.DATA),
            },
            output_ports={
                "output_default": PortDef("output_default", PortRole.DATA),
                "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY),
            },
        ),
        PhysicsDataNode(id=d_out_id, name="FinalOutput"),
        PhysicsFuncNode(
            id=f_halt_id,
            name="Halt",
            input_ports={"in": PortDef("in", PortRole.DATA)},
            output_ports={"out": PortDef("out", PortRole.DATA)},
        ),
        # Observability Infrastructure
        PhysicsDataNode(id=d_life_id, name="EventBus", capacity=100),
        ObservabilityNode(
            id=f_obs_id,
            name="Observer",
            input_ports={"event_token": PortDef("event_token", PortRole.OBSERVABILITY)},
        ),
    ]
    for node in nodes:
        graph.nodes[node.id] = node

    # Channels
    graph.channels.extend(
        [
            Channel(d_in_id, "out", f_bleach_id, "n"),
            Channel(f_bleach_id, "worker_input", d_worker_in_id, "in"),
            Channel(d_worker_in_id, "out", f_worker_id, "worker_input"),
            Channel(f_worker_id, "worker_result", d_worker_out_id, "in"),
            Channel(d_worker_out_id, "out", f_stain_id, "worker_result"),
            Channel(f_bleach_id, "trace_output", d_trace_id, "in"),
            Channel(d_trace_id, "out", f_stain_id, "trace_input"),
            Channel(f_stain_id, "output_default", d_out_id, "in"),
            # Add the self-termination channel
            Channel(d_out_id, "out", f_halt_id, "in"),
            # Observability Wiring
            Channel(f_bleach_id, "obs_output", d_life_id, "in"),
            Channel(f_stain_id, "obs_output", d_life_id, "in"),
            Channel(d_life_id, "out", f_obs_id, "event_token"),
        ]
    )
    return graph


# --- The Test ---


@pytest.mark.asyncio
async def test_machine_runs_self_terminating_flow():
    # 1. Setup
    graph = build_test_graph()

    # Kernel Function Map (Standard Library ICs)
    function_map: Dict[str, Callable] = {
        PhysicalIdGenerator.bleach_node("task_square"): standard_bleacher,
        PhysicalIdGenerator.worker_node("task_square"): standard_dispatcher,
        PhysicalIdGenerator.stain_node("task_square"): standard_stainer,
        PhysicalIdGenerator.observability_observer(): standard_observer,
        "f_halt": halt_signal,
    }

    # Code Registry (User Functions)
    code_registry = CodeRegistry()
    code_registry.register("hash_for_user_square", user_square)

    # Use the test harness for setup
    runner = EventDrivenRunner(graph, function_map, code_registry)

    # 2. Prime and Execute
    runner.inject_input("d_in", 10)
    await runner.start_loop()

    try:
        # 3. Wait for the machine to terminate on its own
        await asyncio.wait_for(runner._loop_task, timeout=5.0)

        # 4. Assert: Verify the final state by inspecting captured events
        # Find the completion event for our task
        completion_event = next(
            (
                e
                for e in runner._captured_events
                if isinstance(e, TaskExecutionFinished) and e.task_id == "task_square"
            ),
            None,
        )

        assert completion_event is not None, "Task completion event was not captured"
        assert (
            completion_event.status == "Succeeded"
        ), "Task did not succeed"

        final_ref = completion_event.result_preview
        final_result = runner.object_store.get(final_ref)

        assert final_result == 100, "The final result should be 10*10"
        print("Machine self-termination test passed: Final result is 100.")

    finally:
        # stop_loop is now just for cleanup, ensuring tasks are cancelled
        # if the test fails before self-termination.
        await runner.stop_loop()