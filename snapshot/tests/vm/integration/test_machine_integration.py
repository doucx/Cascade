import pytest
import asyncio
from typing import Dict, Callable

# Cascade DSL & Compiler
from cascade.spec.dsl.task import task
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.spec.physical.environment import EnvironmentDef

# Runtime Components
from cascade.vm.registry import CodeRegistry
from cascade.vm.resource_registry import ResourceRegistry
from cascade.runtime.storage import InMemoryObjectStore
from cascade.vm.compute.service import LocalComputeService
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.machine import Machine
from cascade.spec.physical.object import Ref

# Observability
from cascade.runtime.services.observability.bus import EventBus
from cascade.runtime.services.observability.events import TaskExecutionFinished

# Standard Library ICs
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.std.probe.const import const_probe
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor


# --- 1. Define User Task ---
@task
async def async_multiplier(a: int, b: int) -> int:
    # Simulate IO delay to ensure the Machine handles async suspension correctly
    await asyncio.sleep(0.01)
    return a * b


@pytest.mark.asyncio
async def test_machine_e2e_integration():
    """
    Verifies that the Machine can orchestrate a full end-to-end flow:
    Compiler -> Physical Graph -> Reactor -> Dispatcher -> ComputeService -> Worker -> Result
    """
    # --- 2. Compilation ---
    # Define a simple workflow: async_multiplier(10, 5)
    workflow = async_multiplier(10, 5)

    ir_gen = IRGenerator()
    builder = Builder()
    
    graph_ir = ir_gen.generate(workflow)
    assembly = builder.build(graph_ir, EnvironmentDef())
    graph = assembly.graph

    # --- 3. Infrastructure Setup ---
    
    # Storage & Registry
    store = InMemoryObjectStore()
    code_registry = CodeRegistry()

    # Register the worker function based on the compiler's symbol table
    worker_node_id = list(assembly.symbol_table.keys())[0]
    canonical_hash = assembly.symbol_table[worker_node_id]
    code_registry.register(canonical_hash, async_multiplier.func)

    # Communication Channels
    compute_queue = asyncio.Queue()
    ingress_queue = asyncio.Queue()
    event_bus = EventBus()

    # Resource Registry (The "Environment" for ICs)
    resources = ResourceRegistry()
    resources.register("system.object_store", store)
    resources.register("system.compute_queue", compute_queue)
    resources.register("system.event_bus", event_bus)

    # Compute Service (The Async Plane)
    compute_service = LocalComputeService(
        store=store,
        registry=code_registry,
        inbound_queue=compute_queue,
        outbound_queue=ingress_queue
    )

    # Reactor Function Map (The Physical Plane Logic)
    func_map: Dict[str, Callable] = {}
    for nid in graph.nodes:
        if nid.endswith(".bleach"):
            func_map[nid] = standard_bleacher
        elif nid.endswith(".stain"):
            func_map[node_id := nid] = standard_stainer
        elif nid.endswith(".worker"):
            # Crucial: Map workers to the dispatcher, NOT the user function
            func_map[nid] = standard_dispatcher
        elif nid.startswith("probe.const"):
            func_map[nid] = const_probe
        elif "observer" in nid:
            func_map[nid] = standard_observer
        elif "allocator" in nid:
            func_map[nid] = discrete_allocator
        elif "reclaimer" in nid:
            func_map[nid] = discrete_reclaimer
        elif nid.startswith("req."):
            func_map[nid] = resource_requestor

    # Reactor
    memory = VolatileMemory()
    reactor = Reactor(graph, memory, func_map, resources, ingress_queue)
    
    # Prime the reactor (loads constants into memory)
    reactor.prime()

    # --- 4. Execution ---
    
    # The Machine coordinates the Reactor and ComputeService
    machine = Machine(reactor, compute_service, ingress_queue)

    # Attach an observer to verify the result
    captured_events = []
    event_bus.subscribe(TaskExecutionFinished, captured_events.append)

    # Run! (Should exit automatically when idle)
    await machine.run()

    # --- 5. Verification ---
    
    assert len(captured_events) == 1
    event = captured_events[0]
    
    assert event.status == "Succeeded"
    assert event.task_name == "async_multiplier"
    
    # Verify the actual calculated result
    result_ref = event.result_preview
    assert isinstance(result_ref, Ref)
    
    final_value = store.get(result_ref)
    assert final_value == 50  # 10 * 5