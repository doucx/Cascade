import asyncio
import pytest
from typing import Dict, Tuple

from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode, Token
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.runtime.storage import InMemoryObjectStore

# --- DRAIN Test Helpers ---

async def slow_worker_func(n: int) -> int:
    # Sleeps to ensure DRAIN signal arrives while task is active
    await asyncio.sleep(0.1)
    return n * n

def drain_trigger_kernel(inputs, node, resources):
    # Emits a DRAIN signal immediately
    return {"out": Token(payload=SystemControlToken(ControlCommand.DRAIN))}

def mock_dispatcher_kernel(inputs, node, resources):
    # Dispatches the slow task
    compute_queue = resources.get("system.compute_queue")
    input_val = inputs["in"].payload # Assumed Ref for simplicity in full stack, but here we can cheat for micro-test
    # We construct a fake request just to trigger the service
    req = ComputeRequest(
        code_hash="slow_task",
        input_refs={}, # Ignored by our registry mock wrapper below
        reply_to_nid="D_out",
        trace={}
    )
    compute_queue.put_nowait(req)
    return {}

# --- ERROR Test Helpers ---

def crashing_kernel(inputs, node, resources):
    raise ValueError("Intentional Kernel Panic")

# --- Fixtures ---

@pytest.fixture
def machine_components():
    memory = VolatileMemory()
    object_store = InMemoryObjectStore()
    compute_queue = asyncio.Queue()
    ingress_queue = asyncio.Queue()
    
    code_registry = CodeRegistry()
    # Mocking execution to skip Ref resolution complexity for this specific test
    # We intercept the _process_request in a real integration, or just ensure 
    # the service's registry call works.
    # Let's use the real service but trick the registry.
    code_registry.register("slow_task", slow_worker_func)

    resource_registry = ResourceRegistry()
    resource_registry.register("system.object_store", object_store)
    resource_registry.register("system.compute_queue", compute_queue)

    compute_service = LocalComputeService(
        store=object_store,
        registry=code_registry,
        inbound_queue=compute_queue,
        outbound_queue=ingress_queue
    )

    return memory, resource_registry, ingress_queue, compute_service

# --- Tests ---

@pytest.mark.asyncio
async def test_drain_waits_for_active_task(machine_components):
    memory, resource_registry, ingress_queue, compute_service = machine_components
    
    # Topology: 
    # 1. D_start -> F_launch (starts slow task) -> D_out
    # 2. D_drain -> F_drain (sends DRAIN)
    
    d_start = PhysicsDataNode(id="D_start", name="Start")
    d_out = PhysicsDataNode(id="D_out", name="Out")
    f_launch = PhysicsFuncNode(id="F_launch", name="Launch", input_ports={"in": PortDef("in", PortRole.DATA)})
    
    d_drain = PhysicsDataNode(id="D_drain", name="DrainTrigger")
    f_drain = PhysicsFuncNode(id="F_drain", name="Drainer", input_ports={"in": PortDef("in", PortRole.DATA)})
    # F_drain output is intercepted by Reactor, no target D needed
    
    graph = BipartiteGraph()
    for n in [d_start, d_out, f_launch, d_drain, f_drain]:
        graph.nodes[n.id] = n
        
    graph.channels.append(Channel("D_start", "out", "F_launch", "in"))
    graph.channels.append(Channel("D_drain", "out", "F_drain", "in"))
    
    func_map = {
        "F_launch": mock_dispatcher_kernel,
        "F_drain": drain_trigger_kernel
    }
    
    reactor = Reactor(graph, memory, func_map, resource_registry, ingress_queue)
    machine = Machine(reactor, compute_service, ingress_queue)
    
    # Inject inputs
    memory.put(d_start, Token(payload="go"))
    memory.put(d_drain, Token(payload="stop"))
    
    # Run
    # The machine should:
    # 1. Fire F_launch (starts slow task in background)
    # 2. Fire F_drain (sets DRAIN flag)
    # 3. Wait approx 0.1s for slow task to finish
    # 4. Process result in D_out
    # 5. Detect Quiescence -> Shutdown
    
    await asyncio.wait_for(machine.run(), timeout=1.0)
    
    # Assertions
    assert memory.get_count("D_out") == 1
    assert reactor.shutdown_event.is_set()
    assert reactor.drain_event.is_set()


@pytest.mark.asyncio
async def test_error_signal_shuts_down_machine(machine_components):
    memory, resource_registry, ingress_queue, compute_service = machine_components
    
    d_err = PhysicsDataNode(id="D_err", name="ErrTrigger")
    f_crash = PhysicsFuncNode(id="F_crash", name="Crasher", input_ports={"in": PortDef("in", PortRole.DATA)})
    
    graph = BipartiteGraph()
    graph.nodes[d_err.id] = d_err
    graph.nodes[f_crash.id] = f_crash
    graph.channels.append(Channel("D_err", "out", "F_crash", "in"))
    
    func_map = { "F_crash": crashing_kernel }
    
    reactor = Reactor(graph, memory, func_map, resource_registry, ingress_queue)
    machine = Machine(reactor, compute_service, ingress_queue)
    
    memory.put(d_err, Token("die"))
    
    await asyncio.wait_for(machine.run(), timeout=1.0)
    
    assert reactor.shutdown_event.is_set()
    # The system should have stopped cleanly despite the exception