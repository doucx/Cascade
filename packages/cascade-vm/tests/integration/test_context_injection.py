import pytest
from typing import Dict, Any

from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode, Token
from cascade.spec.triad import BleachNode, WorkerNode, StainNode, ObservabilityNode
from cascade.spec.ports import PortDef, PortRole
from cascade.runtime.events import TaskExecutionStarted, TaskExecutionFinished
from cascade.vm.harness import EventDrivenRunner
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer


# --- Helper: Build a Physical Triad manually ---
def build_test_triad() -> BipartiteGraph:
    graph = BipartiteGraph()

    # 1. Nodes
    # Input Data
    d_in = PhysicsDataNode(id="d_in", name="Input")

    # F_pre (Bleacher)
    f_pre = BleachNode(
        id="task.bleach",
        name="Bleacher",
        input_ports={"arg1": PortDef("arg1", PortRole.DATA)},
        output_ports={
            "worker_input": PortDef("worker_input", PortRole.DATA),
            "trace_output": PortDef("trace_output", PortRole.DATA),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY),
        },
    )

    # D_worker_in & D_trace
    d_worker_in = PhysicsDataNode(id="d_worker_in", name="WorkerIn")
    d_trace = PhysicsDataNode(id="d_trace", name="Trace")

    # F_exec (Worker)
    f_worker = WorkerNode(
        id="task.worker",
        name="Worker",
        input_ports={"worker_input": PortDef("worker_input", PortRole.DATA)},
        output_ports={"worker_result": PortDef("worker_result", PortRole.DATA)},
    )

    # D_worker_out
    d_worker_out = PhysicsDataNode(id="d_worker_out", name="WorkerOut")

    # F_post (Stainer)
    f_stain = StainNode(
        id="task.stain",
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
    d_life = PhysicsDataNode(
        id="global.observability.bus", name="EventBus", capacity=100
    )
    f_obs = ObservabilityNode(
        id="global.observability.observer",
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
        Channel("d_in", "out", "task.bleach", "arg1"),
        # Bleacher -> Worker
        Channel("task.bleach", "worker_input", "d_worker_in", "in"),
        Channel("d_worker_in", "out", "task.worker", "worker_input"),
        # Worker -> Stainer
        Channel("task.worker", "worker_result", "d_worker_out", "in"),
        Channel("d_worker_out", "out", "task.stain", "worker_result"),
        # Bleacher -> Trace -> Stainer (The Wormhole)
        Channel("task.bleach", "trace_output", "d_trace", "in"),
        Channel("d_trace", "out", "task.stain", "trace_input"),
        # Stainer -> Output
        Channel("task.stain", "output_default", "d_out", "in"),
        # Observability Wiring
        Channel("task.bleach", "obs_output", "global.observability.bus", "in"),
        Channel("task.stain", "obs_output", "global.observability.bus", "in"),
        Channel(
            "global.observability.bus",
            "out",
            "global.observability.observer",
            "event_token",
        ),
    ]

    graph.channels.extend(channels)
    return graph


async def simple_worker(
    inputs: Dict[str, Token], node: Any, resources: Any
) -> Dict[str, Token]:
    # A simple pass-through worker
    payload = inputs["worker_input"].payload
    val = payload["arg1"]
    return {"worker_result": Token(payload=f"processed_{val}")}


@pytest.mark.asyncio
async def test_genesis_injection_propagates_run_id():
    # 1. Setup
    graph = build_test_triad()
    function_map = {
        "task.bleach": standard_bleacher,
        "task.worker": simple_worker,
        "task.stain": standard_stainer,
        "global.observability.observer": standard_observer,
    }

    runner = EventDrivenRunner(graph, function_map)

    # Assert Runner has generated a Run ID
    assert runner.run_id is not None
    print(f"Test Run ID: {runner.run_id}")

    # 2. Prime and Start
    runner.prime()
    await runner.start_loop()

    try:
        # 3. Inject Input (This trigger Genesis Injection logic in inject_input)
        # We assume inject_input adds the run_id from runner to the token trace
        runner.inject_input("d_in", "test_data")

        # 4. Wait for completion (Stainer success event)
        # We look for the SUCCEEDED event from the stainer (which maps to TaskExecutionFinished)
        # Note: standard_stainer emits an IR with logic_id derived from node id.
        # "task.stain" -> logical_id "task"
        def is_success(e):
            return (
                isinstance(e, TaskExecutionFinished)
                and e.task_id == "task"
                and e.status == "Succeeded"
            )

        await runner.wait_for_event(is_success, timeout=2.0)

        # 5. Verify Events
        events = runner._captured_events

        # Filter relevant lifecycle events (Rich Objects)
        lifecycle_events = [
            e
            for e in events
            if isinstance(e, (TaskExecutionStarted, TaskExecutionFinished))
        ]
        assert len(lifecycle_events) >= 2  # At least Started and Finished

        for event in lifecycle_events:
            # THE CORE ASSERTION:
            # Every lifecycle event object must carry the correct run_id
            # The translation layer (Event.from_ir) extracts 'ctx.rid' -> 'event.run_id'
            assert event.run_id == runner.run_id, f"Run ID mismatch in event {event}"

        print("Context propagation verified successfully.")

    finally:
        await runner.stop_loop()
