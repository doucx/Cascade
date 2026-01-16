import pytest
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.dyad import LauncherNode, LanderNode
from cascade.spec.physical.system_nodes import ObservabilityNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.specs.dyad import LanderSpec
from cascade.spec.runtime.observability import EventState
from cascade.bus.events import TaskExecutionStarted, TaskExecutionFinished
from cascade.test_utils import EventDrivenRunner
from cascade.std.dyad.launcher import standard_launcher
from cascade.std.dyad.lander import standard_lander
from cascade.std.system.observer import standard_observer
from cascade.vm.registry import CodeRegistry
from cascade.reflection import PhysicalIdGenerator


async def actual_user_logic(arg1: str) -> str:
    return f"processed_{arg1}"


def build_test_dyad_for_injection() -> BipartiteGraph:
    graph = BipartiteGraph()
    base_id = "task"
    f_launch_id = PhysicalIdGenerator.launcher_node(base_id)
    d_result_id = PhysicalIdGenerator.result_data(base_id)
    f_land_id = PhysicalIdGenerator.lander_node(base_id)
    d_life_id = PhysicalIdGenerator.observability_bus()
    f_obs_id = PhysicalIdGenerator.observability_observer()

    d_in = PhysicsDataNode(id="d_in", name="Input")
    
    f_launch = LauncherNode(
        id=f_launch_id,
        name="Launch",
        input_ports={"arg1": PortDef("arg1", PortRole.DATA)},
        output_ports={"obs_output": PortDef("obs_output", PortRole.OBSERVABILITY)},
        canonical_code_structure_hash="hash_user_logic_001",
        reply_to_nid=d_result_id
    )
    
    d_result = PhysicsDataNode(id=d_result_id, name="Result")
    
    f_land = LanderNode(
        id=f_land_id,
        name="Land",
        input_ports={LanderSpec.result_token.name: PortDef(LanderSpec.result_token.name, PortRole.DATA)},
        output_ports={
            "output_default": PortDef("output_default", PortRole.DATA),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY),
        }
    )
    
    d_out = PhysicsDataNode(id="d_out", name="Output")
    
    d_life = PhysicsDataNode(id=d_life_id, name="EventBus", capacity=100)
    f_obs = ObservabilityNode(
        id=f_obs_id,
        name="Observer",
        input_ports={"event_token": PortDef("event_token", PortRole.OBSERVABILITY)},
    )

    for n in [d_in, f_launch, d_result, f_land, d_out, d_life, f_obs]:
        graph.nodes[n.id] = n

    graph.channels.extend([
        Channel("d_in", "out", f_launch_id, "arg1"),
        Channel(d_result_id, "out", f_land_id, LanderSpec.result_token.name),
        Channel(f_land_id, "output_default", "d_out", "in"),
        
        Channel(f_launch_id, "obs_output", d_life_id, "in"),
        Channel(f_land_id, "obs_output", d_life_id, "in"),
        Channel(d_life_id, "out", f_obs_id, "event_token"),
    ])
    return graph


@pytest.mark.asyncio
async def test_genesis_injection_propagates_run_id():
    registry = CodeRegistry()
    registry.register("hash_user_logic_001", actual_user_logic)

    graph = build_test_dyad_for_injection()
    base_id = "task"
    
    function_map = {
        PhysicalIdGenerator.launcher_node(base_id): standard_launcher,
        PhysicalIdGenerator.lander_node(base_id): standard_lander,
        PhysicalIdGenerator.observability_observer(): standard_observer,
    }

    runner = EventDrivenRunner(graph, function_map, registry)
    runner.prime()
    
    # Manually configure compute service to bridge queue -> d_result
    # The EventDrivenRunner sets up a LocalComputeService, but we need to ensure 
    # it knows about our object store and queues.
    # EventDrivenRunner internal setup handles this.

    await runner.start_loop()

    try:
        runner.inject_input("d_in", "test_data")

        def is_success(e):
            return (
                isinstance(e, TaskExecutionFinished)
                and e.task_id == "task"
                and e.status is EventState.SUCCEEDED
            )

        await runner.wait_for_event(is_success, timeout=2.0)

        events = runner._captured_events
        lifecycle_events = [
            e for e in events if isinstance(e, (TaskExecutionStarted, TaskExecutionFinished))
        ]
        
        assert len(lifecycle_events) >= 2
        for event in lifecycle_events:
            assert event.run_id == runner.run_id

    finally:
        await runner.stop_loop()