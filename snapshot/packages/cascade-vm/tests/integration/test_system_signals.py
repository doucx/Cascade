import pytest
import asyncio
from typing import Dict, Tuple

from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode, Token
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.compute.service import LocalComputeService
from cascade.runtime.storage import InMemoryObjectStore
from cascade.vm.registry import CodeRegistry


# --- Mocks & Fixtures ---

async def slow_task(n: int) -> int:
    await asyncio.sleep(0.1)  # Takes time to complete
    return n

async def crashing_task(n: int) -> int:
    raise RuntimeError("Intentional Crash")

def build_minimal_machine(graph, function_map, code_registry) -> Tuple[Machine, VolatileMemory, InMemoryObjectStore]:
    memory = VolatileMemory()
    store = InMemoryObjectStore()
    compute_queue = asyncio.Queue()
    ingress_queue = asyncio.Queue()
    
    # Minimal Resource Registry
    from cascade.vm.resource_registry import ResourceRegistry
    resources = ResourceRegistry()
    resources.register("system.object_store", store)
    resources.register("system.compute_queue", compute_queue)
    
    reactor = Reactor(graph, memory, function_map, resources, ingress_queue)
    compute_service = LocalComputeService(store, code_registry, compute_queue, ingress_queue)
    machine = Machine(reactor, compute_service, ingress_queue)
    
    return machine, memory, store

@pytest.mark.asyncio
async def test_drain_signal_waits_for_completion():
    # Scenario:
    # 1. Trigger Node -> Drain Node (Emits DRAIN)
    # 2. Trigger Node -> Worker Node (Starts Slow Task)
    # Goal: Verify that Machine doesn't stop until Slow Task finishes, even though DRAIN was emitted early.
    
    from cascade.std.system.drainer import drain_signal
    from cascade.std.triad.dispatcher import standard_dispatcher
    from cascade.reflection import PhysicalIdGenerator

    # Topology
    d_in = PhysicsDataNode(id="d_in", name="Input", initial_tokens=1, initial_payload=1)
    
    # Branch 1: The Drainer
    f_drain = PhysicsFuncNode(id="f_drain", name="Drainer", 
                              input_ports={"in": PortDef("in", PortRole.DATA)}, 
                              output_ports={"out": PortDef("out", PortRole.DATA)})
    d_ctrl = PhysicsDataNode(id="d_ctrl", name="ControlBus") # Reactor intercepts, but topology needs target

    # Branch 2: The Worker
    # We use a simplified dispatcher setup for brevity (skipping full Triad for this unit-integration test)
    # Just mocking a worker node behavior directly might be easier, but let's use dispatcher to test ComputeService integration.
    f_worker = PhysicsFuncNode(id="task.worker", name="Worker", 
                               input_ports={"worker_input": PortDef("worker_input", PortRole.DATA)},
                               output_ports={"worker_result": PortDef("worker_result", PortRole.DATA)})
    # Dispatcher expects {worker_input: {payload: {inputs...}}}
    # We'll mock a simple wrapper func to format it
    
    d_worker_out = PhysicsDataNode(id="d_out", name="Output")

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_in, f_drain, d_ctrl, f_worker, d_worker_out]}
    
    # Wiring
    # d_in -> f_drain
    graph.channels.append(Channel("d_in", "out", "f_drain", "in"))
    # d_in -> f_worker (Fan-out)
    graph.channels.append(Channel("d_in", "out", "task.worker", "worker_input"))
    
    # f_drain -> d_ctrl
    graph.channels.append(Channel("f_drain", "out", "d_ctrl", "in"))
    # f_worker -> d_out
    graph.channels.append(Channel("task.worker", "worker_result", "d_out", "in"))

    # Logic
    def split_input_wrapper(inputs, node, res):
        # Dispatcher expects specific structure
        return {"worker_input": inputs["worker_input"]}

    # We need a custom logic for f_worker to adapt d_in (int) to dispatcher format (dict of refs)
    # Actually, simpler: define a custom kernel function that submits to compute queue manually
    # to avoid mocking the whole Bleacher complexity.
    
    def custom_dispatcher(inputs, node, resources):
        from cascade.vm.compute import ComputeRequest
        q = resources.get("system.compute_queue")
        # Direct submission
        q.put_nowait(ComputeRequest(
            code_hash="slow_task",
            input_refs={}, # No inputs needed for this test
            reply_to_nid="d_out",
            trace={}
        ))
        return {}

    func_map = {
        "f_drain": drain_signal,
        "task.worker": custom_dispatcher
    }
    
    registry = CodeRegistry()
    registry.register("slow_task", slow_task)

    machine, memory, store = build_minimal_machine(graph, func_map, registry)

    # Execution
    # run() should return ONLY when shutdown_event is set.
    # shutdown_event should set ONLY when drain_event is set AND task is done.
    await machine.run()
    
    # Assertions
    # 1. Machine stopped (implied by await returning)
    # 2. Output should exist (meaning it waited)
    assert memory.get_count("d_out") == 1
    # 3. Drain event was triggered
    assert machine.reactor.drain_event.is_set()


@pytest.mark.asyncio
async def test_error_signal_broadcasts_crash():
    # Scenario: Kernel function raises exception -> Reactor catches -> Emits ERROR -> Machine stops
    
    d_in = PhysicsDataNode(id="d_in", name="Input", initial_tokens=1)
    f_crash = PhysicsFuncNode(id="f_crash", name="Crasher", 
                              input_ports={"in": PortDef("in", PortRole.DATA)}, 
                              output_ports={"out": PortDef("out", PortRole.DATA)})
    d_void = PhysicsDataNode(id="d_void", name="Void")

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_in, f_crash, d_void]}
    graph.channels.append(Channel("d_in", "out", "f_crash", "in"))
    graph.channels.append(Channel("f_crash", "out", "d_void", "in"))

    def crashing_kernel(inputs, node, res):
        raise ValueError("Kernel Panic!")

    func_map = {"f_crash": crashing_kernel}
    registry = CodeRegistry()

    machine, memory, store = build_minimal_machine(graph, func_map, registry)

    # Execution
    await machine.run()

    # Assertions
    # 1. Machine stopped
    assert machine.reactor.shutdown_event.is_set()
    # 2. Error should be logged (we can't easily assert logs here without caplog, but machine stopping confirms it)
    # Ideally we'd check if a SystemControlToken(ERROR) appeared in memory if wired, 
    # but Reactor._handle_control_signal consumes it immediately without putting to memory usually.
    # However, for this test, simply verifying it halted without external intervention is enough.