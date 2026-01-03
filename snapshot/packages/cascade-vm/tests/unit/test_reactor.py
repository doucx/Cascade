import pytest
from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.ports import PortDef, PortRole
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.executor import PhysicsExecutor


# Dummy function for testing
def noop(inputs, node, resources):
    # Echos back a generic result token on 'out' port
    return {"out": Token(payload="result")}


@pytest.fixture
def simple_topology():
    d1 = PhysicsDataNode(id="D1", name="Input")
    f1 = PhysicsFuncNode(
        id="F1",
        name="Processor",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )

    graph = BipartiteGraph()
    graph.nodes[d1.id] = d1
    graph.nodes[f1.id] = f1

    # Connect D1 -> F1
    channel = Channel(
        source_node_id=d1.id, source_port="out", target_node_id=f1.id, target_port="in"
    )
    graph.channels.append(channel)

    return graph, d1, f1


@pytest.mark.asyncio
async def test_reactor_step_idle(simple_topology):
    graph, d1, f1 = simple_topology
    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f1.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)

    fired_count = await reactor.step()

    assert fired_count == 0


@pytest.mark.asyncio
async def test_reactor_step_fire(simple_topology):
    graph, d1, f1 = simple_topology
    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f1.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)

    # 1. Put token
    memory.put(d1, Token(payload="energy"))
    assert memory.get_count(d1.id) == 1

    # 2. Step
    fired_count = await reactor.step()

    # 3. Assertions
    assert fired_count == 1
    # Token must be consumed (Atomic Consumption)
    assert memory.get_count(d1.id) == 0


@pytest.mark.asyncio
async def test_reactor_partial_inputs():
    d1 = PhysicsDataNode(id="D1", name="Input1")
    d2 = PhysicsDataNode(id="D2", name="Input2")
    f1 = PhysicsFuncNode(
        id="F1",
        name="Processor",
        input_ports={
            "in1": PortDef("in1", PortRole.DATA),
            "in2": PortDef("in2", PortRole.DATA),
        },
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, d2, f1]}

    # D1 -> F1
    graph.channels.append(Channel(d1.id, "out", f1.id, target_port="in1"))
    # D2 -> F1
    graph.channels.append(Channel(d2.id, "out", f1.id, target_port="in2"))

    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f1.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)

    # Only fill D1
    memory.put(d1, Token(payload="A"))

    fired_count = await reactor.step()

    assert fired_count == 0
    # Token in D1 should remain untouched
    assert memory.get_count(d1.id) == 1


@pytest.mark.asyncio
async def test_reactor_independent_nodes():
    d1 = PhysicsDataNode(id="D1", name="In1")
    f1 = PhysicsFuncNode(
        id="F1",
        name="Proc1",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )

    d2 = PhysicsDataNode(id="D2", name="In2")
    f2 = PhysicsFuncNode(
        id="F2",
        name="Proc2",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, f1, d2, f2]}
    graph.channels.append(Channel(d1.id, "out", f1.id, target_port="in"))
    graph.channels.append(Channel(d2.id, "out", f2.id, target_port="in"))

    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f1.id: noop, f2.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)

    memory.put(d1, Token("A"))
    memory.put(d2, Token("B"))

    fired_count = await reactor.step()

    assert fired_count == 2
    assert memory.get_count(d1.id) == 0
    assert memory.get_count(d2.id) == 0


# --- New Test demonstrating EventDrivenRunner ---

from cascade.vm.test_harness import EventDrivenRunner
from cascade.spec.triad import ObservabilityNode
from cascade.std.triad.observer import standard_observer
import sys

@pytest.mark.asyncio
async def test_event_driven_ping_pong():
    # 1. Topology with Observability
    d1 = PhysicsDataNode(id="D1", name="Input")
    f1 = PhysicsFuncNode(
        id="F1",
        name="Increment",
        input_ports={"value": PortDef("value", PortRole.DATA)},
        output_ports={
            "result": PortDef("result", PortRole.DATA),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY) # Added Obs port
        },
    )
    d2 = PhysicsDataNode(id="D2", name="Output")
    
    # Obs Infra
    d_life = PhysicsDataNode(id="global.observability.bus", name="Bus", capacity=sys.maxsize)
    f_obs = ObservabilityNode(
        id="global.observability.observer",
        name="Observer",
        input_ports={"event_token": PortDef("event_token", PortRole.OBSERVABILITY)}
    )

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, f1, d2, d_life, f_obs]}
    
    # Logic Wiring
    graph.channels.append(Channel(d1.id, "out", f1.id, "value"))
    graph.channels.append(Channel(f1.id, "result", d2.id, "in"))
    
    # Obs Wiring
    # F1 emits directly to Bus (Simulating a Bleacher/Stainer behavior roughly)
    graph.channels.append(Channel(f1.id, "obs_output", d_life.id, "in"))
    graph.channels.append(Channel(d_life.id, "out", f_obs.id, "event_token"))

    # Function Map
    def obs_enabled_logic(inputs, node, resources):
        val = inputs["value"].payload
        # Emit Result AND Observation
        return {
            "result": Token(payload=val + 1),
            "obs_output": Token(payload=None, trace={"id": "F1", "status": "done"})
        }

    func_map = {
        "F1": obs_enabled_logic,
        "global.observability.observer": standard_observer # Runner will auto-inject queue
    }

    # 2. Use Runner
    runner = EventDrivenRunner(graph, func_map)
    runner.inject_input("D1", 10)

    # 3. Start & Wait
    await runner.start_loop()
    
    try:
        # We wait for the specific event proving F1 finished
        event = await runner.wait_for_event(
            lambda e: e.trace_data.get("id") == "F1" and e.trace_data.get("status") == "done"
        )
        assert event is not None
        
        # Verify physical side effect (Memory)
        assert runner.memory.get_count("D2") == 1
        assert runner.memory.take("D2").payload == 11
        
    finally:
        await runner.stop_loop()
