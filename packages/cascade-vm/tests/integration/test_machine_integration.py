import asyncio
import pytest
from typing import Dict, Callable, Tuple

from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode, Token
from cascade.spec.physical.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.reflection import PhysicalIdGenerator
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.runtime.storage import InMemoryObjectStore

# Standard Library ICs
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.std.triad.stainer import standard_stainer


# --- Test Fixtures ---


# 1. A simple async user function to be executed by the ComputeService
async def user_square(n: int) -> int:
    await asyncio.sleep(0.01)  # Simulate real async work
    return n * n


# 2. A helper to build the physical graph for the test
def build_test_graph() -> BipartiteGraph:
    graph = BipartiteGraph()
    base_id = "task_square"

    # Node IDs
    d_in_id = "d_in"
    d_out_id = "d_out"
    f_bleach_id = PhysicalIdGenerator.bleach_node(base_id)
    d_worker_in_id = PhysicalIdGenerator.worker_in_data(base_id)
    f_worker_id = PhysicalIdGenerator.worker_node(base_id)
    d_worker_out_id = PhysicalIdGenerator.worker_out_data(base_id)
    d_trace_id = PhysicalIdGenerator.trace_data(base_id)
    f_stain_id = PhysicalIdGenerator.stain_node(base_id)

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
            output_ports={"output_default": PortDef("output_default", PortRole.DATA)},
        ),
        PhysicsDataNode(id=d_out_id, name="FinalOutput"),
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
        ]
    )
    return graph


# --- The Test ---


@pytest.mark.asyncio
async def test_machine_runs_cross_jurisdiction_flow():
    # 1. Setup: Build all components of the Machine
    graph = build_test_graph()
    memory = VolatileMemory()

    # Kernel Function Map (Standard Library ICs)
    function_map: Dict[str, Callable] = {
        PhysicalIdGenerator.bleach_node("task_square"): standard_bleacher,
        PhysicalIdGenerator.worker_node("task_square"): standard_dispatcher,
        PhysicalIdGenerator.stain_node("task_square"): standard_stainer,
    }

    # Code Registry (User Functions)
    code_registry = CodeRegistry()
    code_registry.register("hash_for_user_square", user_square)

    # Object Store (Data Plane)
    object_store = InMemoryObjectStore()

    # Communication Queues
    compute_queue: asyncio.Queue[ComputeRequest] = asyncio.Queue()
    ingress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()

    # Resource Registry (Environment)
    resource_registry = ResourceRegistry()
    resource_registry.register("system.object_store", object_store)
    resource_registry.register("system.compute_queue", compute_queue)

    # Instantiate Core Components
    reactor = Reactor(graph, memory, function_map, resource_registry, ingress_queue)
    compute_service = LocalComputeService(
        store=object_store,
        registry=code_registry,
        inbound_queue=compute_queue,
        outbound_queue=ingress_queue,
    )
    machine = Machine(reactor, compute_service, ingress_queue)

    # 2. Prime the System: Inject the initial input data
    initial_value = 10
    initial_ref = object_store.put(initial_value)
    initial_token = Token(payload=initial_ref, trace={"rid": "test_run_01"})
    memory.put(graph.nodes["d_in"], initial_token)

    # 3. Execute: Run the machine until it becomes idle
    await machine.run()

    # 4. Assert: Verify the final state
    # The machine should stop when idle. We can now inspect the final memory state.
    assert memory.get_count("d_out") == 1, "Final output node should have one token"

    final_token = memory.take("d_out")
    final_ref = final_token.payload
    final_result = object_store.get(final_ref)

    assert final_result == 100, "The final result should be 10*10"
    print("Machine integration test passed: Final result is 100.")
