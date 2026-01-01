import pytest
from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.executor import PhysicsExecutor


# Dummy function for testing
def noop(inputs):
    # Echos back a generic result token on 'out' port
    return {"out": Token(payload="result")}


@pytest.fixture
def simple_topology():
    d1 = PhysicsDataNode(id="D1", name="Input")
    f1 = PhysicsFuncNode(id="F1", name="Processor")

    # Define ports (optional for logic, but good for completeness)
    f1.input_ports["in"] = "D1"

    graph = BipartiteGraph()
    graph.nodes[d1.id] = d1
    graph.nodes[f1.id] = f1

    # Connect D1 -> F1
    channel = Channel(source_node_id=d1.id, source_port="out", target_node_id=f1.id, target_port="in")
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
    f1 = PhysicsFuncNode(id="F1", name="Processor")

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
    f1 = PhysicsFuncNode(id="F1", name="Proc1")

    d2 = PhysicsDataNode(id="D2", name="In2")
    f2 = PhysicsFuncNode(id="F2", name="Proc2")

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
