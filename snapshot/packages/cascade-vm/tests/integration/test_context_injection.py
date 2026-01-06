import pytest
import asyncio
from typing import Dict, Any

from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.triad import (
    BleachNode,
    WorkerNode,
    StainNode,
    ObservabilityNode,
)
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.runtime.services.observability.events import (
    TaskExecutionStarted,
    TaskExecutionFinished,
)
from cascade.vm.harness import EventDrivenRunner
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.vm.registry import CodeRegistry
from cascade.reflection import PhysicalIdGenerator


# --- User Logic ---
async def actual_user_logic(arg1: str) -> str:
    """
    The actual user code that runs in the Compute Plane.
    It doesn't deal with Tokens or Nodes, just data.
    """
    return f"processed_{arg1}"


# --- Helper: Build a Physical Triad manually ---
def build_test_triad_for_injection() -> BipartiteGraph:
    graph = BipartiteGraph()

    # Base logical ID for the task
    base_id = "task"

    # Generate IDs using the standard protocol
    f_pre_id = PhysicalIdGenerator.bleach_node(base_id)       # e.g., task.bleach
    f_worker_id = PhysicalIdGenerator.worker_node(base_id)    # e.g., task.worker
    f_stain_id = PhysicalIdGenerator.stain_node(base_id)      # e.g., task.stain
    
    # Data nodes must also follow convention where Dispatcher relies on it
    d_worker_in_id = PhysicalIdGenerator.worker_in_data(base_id)
    d_worker_out_id = PhysicalIdGenerator.worker_out_data(base_id)
    d_trace_id = PhysicalIdGenerator.trace_data(base_id)

    # 1. Nodes
    # Input Data (External)
    d_in = PhysicsDataNode(id="d_in", name="Input")

    # F_pre (Bleacher)
    f_pre = BleachNode(
        id=f_pre_id,
        name="Bleacher",
        input_ports={"arg1": PortDef("arg1", PortRole.DATA)},
        output_ports={
            "worker_input": PortDef("worker_input", PortRole.DATA),
            "trace_output": PortDef("trace_output", PortRole.DATA),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY),
        },
    )

    # D_worker_in & D_trace
    d_worker_in = PhysicsDataNode(id=d_worker_in_id, name="WorkerIn")
    d_trace = PhysicsDataNode(id=d_trace_id, name="Trace")

    # F_exec (Worker)
    # NOTE: In v3.3, WorkerNode holds the hash of the code it should dispatch.
    f_worker = WorkerNode(
        id=f_worker_id,
        name="Worker",
        canonical_code_structure_hash="hash_user_logic_001",
        input_ports={"worker_input": PortDef("worker_input", PortRole.DATA)},
        output_ports={"worker_result": PortDef("worker_result", PortRole.DATA)},
    )

    # D_worker_out
    d_worker_out = PhysicsDataNode(id=d_worker_out_id, name="WorkerOut")

    # F_post (Stainer)
    f_stain = StainNode(
        id=f_stain_id,
        name="Stainer",
        input_ports={
            "worker_result": PortDef("worker_result", PortRole.DATA),
            "trace_input": PortDef("trace_input", PortRole.DATA),
        },
        output_ports={
            "output_default": PortDef("output_default", PortRole.DATA),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY),
        },
    )

    # D_out (Final Result)
    d_out = PhysicsDataNode(id="d_out", name="Output")

    # Observability Infrastructure
    d_life_id = PhysicalIdGenerator.observability_bus()
    f_obs_id = PhysicalIdGenerator.observability_observer()
    
    d_life = PhysicsDataNode(
        id=d_life_id, name="EventBus", capacity=100
    )
    f_obs = ObservabilityNode(
        id=f_obs_id,
        name="Observer",
        input_ports={"event_token": PortDef("event_token", PortRole.OBSERVABILITY)},
    )

    # Register Nodes
    for n in [
        d_in,
        f_pre,
        d_worker_in,
        d_trace,
        f_worker,
        d_worker_out,
        f_stain,
        d_out,
        d_life,
        f_obs,
    ]:
        graph.nodes[n.id] = n

    # 2. Channels (Wiring)
    channels = [
        # Input -> Bleacher
        Channel("d_in", "out", f_pre_id, "arg1"),
        # Bleacher -> Worker
        Channel(f_pre_id, "worker_input", d_worker_in_id, "in"),
        Channel(d_worker_in_id, "out", f_worker_id, "worker_input"),
        # Worker -> Stainer
        Channel(f_worker_id, "worker_result", d_worker_out_id, "in"),
        Channel(d_worker_out_id, "out", f_stain_id, "worker_result"),
        # Bleacher -> Trace -> Stainer (The Wormhole)
        Channel(f_pre_id, "trace_output", d_trace_id, "in"),
        Channel(d_trace_id, "out", f_stain_id, "trace_input"),
        # Stainer -> Output
        Channel(f_stain_id, "output_default", "d_out", "in"),
        # Observability Wiring
        Channel(f_pre_id, "obs_output", d_life_id, "in"),
        Channel(f_stain_id, "obs_output", d_life_id, "in"),
        Channel(
            d_life_id,
            "out",
            f_obs_id,
            "event_token",
        ),
    ]

    graph.channels.extend(channels)
    return graph


@pytest.mark.asyncio
async def test_genesis_injection_propagates_run_id():
    # 1. Setup Code Registry
    registry = CodeRegistry()
    registry.register("hash_user_logic_001", actual_user_logic)

    # 2. Setup Graph
    graph = build_test_triad_for_injection()

    # 3. Setup Physics Kernel Function Map
    # NOTE: The worker now maps to the standard_dispatcher!
    # We must use the exact IDs generated by PhysicalIdGenerator
    base_id = "task"
    function_map = {
        PhysicalIdGenerator.bleach_node(base_id): standard_bleacher,
        PhysicalIdGenerator.worker_node(base_id): standard_dispatcher,
        PhysicalIdGenerator.stain_node(base_id): standard_stainer,
        PhysicalIdGenerator.observability_observer(): standard_observer,
    }

    runner = EventDrivenRunner(graph, function_map, registry)

    # Assert Runner has generated a Run ID
    assert runner.run_id is not None
    print(f"Test Run ID: {runner.run_id}")

    # 4. Prime and Start
    runner.prime()
    await runner.start_loop()

    try:
        # 5. Inject Input (Trigger Genesis Injection)
        # Runner.inject_input will embed the runner.run_id into the Token trace.
        runner.inject_input("d_in", "test_data")

        # 6. Wait for completion
        # We look for the SUCCEEDED event from the stainer.
        def is_success(e):
            return (
                isinstance(e, TaskExecutionFinished)
                and e.task_id == "task"
                and e.status == "Succeeded"
            )

        await runner.wait_for_event(is_success, timeout=2.0)

        # 7. Verify Events
        events = runner._captured_events

        lifecycle_events = [
            e
            for e in events
            if isinstance(e, (TaskExecutionStarted, TaskExecutionFinished))
        ]
        assert len(lifecycle_events) >= 2

        for event in lifecycle_events:
            # The Critical Assertion:
            # Did the run_id survive the trip through:
            # Bleacher -> Dispatcher -> ComputeService -> Worker -> Stainer -> EventBus?
            assert event.run_id == runner.run_id, f"Run ID mismatch in event {event}"

        print("Context propagation verified successfully.")

    finally:
        await runner.stop_loop()