import asyncio
import pytest
from typing import Dict, Callable, Tuple

from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode, Token
from cascade.spec.physical.dyad import LauncherNode, LanderNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.specs.dyad import LauncherSpec, LanderSpec
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.reflection import PhysicalIdGenerator
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.vm.services.chronos import ChronosService
from cascade.spec.runtime import DelayRequest
from cascade.bus.core import EventBus
from cascade.runtime.storage import InMemoryObjectStore

# Standard Library ICs
from cascade.std.dyad.launcher import standard_launcher
from cascade.std.dyad.lander import standard_lander


# --- Test Fixtures ---

async def user_square(n: int) -> int:
    await asyncio.sleep(0.01)
    return n * n


def transparent_halt(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    data_token = inputs["in"]
    return {
        "out": data_token,
        "ctrl": Token(payload=SystemControlToken(command=ControlCommand.HALT)),
    }


def build_test_graph() -> BipartiteGraph:
    graph = BipartiteGraph()
    base_id = "task_square"

    # Node IDs
    d_in_id = "d_in"
    f_launch_id = PhysicalIdGenerator.launcher_node(base_id)
    d_result_id = PhysicalIdGenerator.result_data(base_id)
    f_land_id = PhysicalIdGenerator.lander_node(base_id)
    d_out_id = "d_out"
    f_halt_id = "f_halt"
    d_final_id = "d_final"

    # Nodes
    d_in = PhysicsDataNode(id=d_in_id, name="Input")
    
    f_launch = LauncherNode(
        id=f_launch_id,
        name="Launch(square)",
        input_ports={"n": PortDef("n", PortRole.DATA)},
        output_ports={"obs_output": PortDef("obs_output", PortRole.OBSERVABILITY)},
        canonical_code_structure_hash="hash_for_user_square",
        reply_to_nid=d_result_id
    )

    d_result = PhysicsDataNode(id=d_result_id, name="Result(square)")

    f_land = LanderNode(
        id=f_land_id,
        name="Land(square)",
        input_ports={LanderSpec.result_token.name: PortDef(LanderSpec.result_token.name, PortRole.DATA)},
        output_ports={
            "output_default": PortDef("output_default", PortRole.DATA),
            "output_error": PortDef("output_error", PortRole.DATA),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY),
        },
    )

    d_out = PhysicsDataNode(id=d_out_id, name="IntermediateOutput")

    f_halt = PhysicsFuncNode(
        id=f_halt_id,
        name="TransparentHalt",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={
            "out": PortDef("out", PortRole.DATA),
            "ctrl": PortDef("ctrl", PortRole.SIGNAL),
        },
    )
    
    d_final = PhysicsDataNode(id=d_final_id, name="FinalOutput")

    for node in [d_in, f_launch, d_result, f_land, d_out, f_halt, d_final]:
        graph.nodes[node.id] = node

    # Channels
    graph.channels.extend([
        # Input -> Launcher
        Channel(d_in_id, "out", f_launch_id, "n"),
        
        # Note: Launcher -> Queue is NOT a physical channel.
        # Queue -> D_result is NOT a physical channel (handled by ComputeService).
        
        # D_result -> Lander
        Channel(d_result_id, "out", f_land_id, LanderSpec.result_token.name),
        
        # Lander -> Output
        Channel(f_land_id, "output_default", d_out_id, "in"),
        
        # Output -> Halt
        Channel(d_out_id, "out", f_halt_id, "in"),
        Channel(f_halt_id, "out", d_final_id, "in")
    ])

    return graph


@pytest.mark.asyncio
async def test_machine_self_terminating_flow():
    graph = build_test_graph()
    memory = VolatileMemory()

    function_map: Dict[str, Callable] = {
        PhysicalIdGenerator.launcher_node("task_square"): standard_launcher,
        PhysicalIdGenerator.lander_node("task_square"): standard_lander,
        "f_halt": transparent_halt,
    }

    code_registry = CodeRegistry()
    code_registry.register("hash_for_user_square", user_square)
    object_store = InMemoryObjectStore()
    
    compute_queue: asyncio.Queue[ComputeRequest] = asyncio.Queue()
    chronos_queue: asyncio.Queue[DelayRequest] = asyncio.Queue()
    ingress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()
    wakeup_event = asyncio.Event()
    event_bus = EventBus()

    resource_registry = ResourceRegistry()
    resource_registry.register("system.object_store", object_store)
    resource_registry.register("system.compute_queue", compute_queue)
    resource_registry.register("system.chronos_queue", chronos_queue)
    resource_registry.register("system.event_bus", event_bus)

    kernel = PhysicsKernel(function_map, resource_registry)
    reactor = Reactor(graph, memory, kernel, ingress_queue)
    
    compute_service = LocalComputeService(
        store=object_store,
        registry=code_registry,
        inbound_queue=compute_queue,
        outbound_queue=ingress_queue,
        wakeup_event=wakeup_event,
    )
    
    chronos_service = ChronosService(
        inbound_queue=chronos_queue,
        outbound_queue=ingress_queue,
        wakeup_event=wakeup_event,
    )
    
    machine = Machine(reactor, compute_service, chronos_service, wakeup_event)

    # Prime
    initial_value = 10
    initial_ref = object_store.put(initial_value)
    initial_token = Token(payload=initial_ref, trace={"rid": "self_term_run"})
    memory.put(graph.nodes["d_in"], initial_token)

    # Run
    try:
        await asyncio.wait_for(machine.run(), timeout=5.0)
    except asyncio.TimeoutError:
        pytest.fail("Machine execution timed out! Self-termination failed.")

    # Assert
    assert memory.get_count("d_final") == 1
    final_token = memory.take("d_final")
    final_ref = final_token.payload
    final_result = object_store.get(final_ref)
    assert final_result == 100