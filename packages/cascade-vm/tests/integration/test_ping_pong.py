import pytest
from typing import Dict, Callable

from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor


def simple_increment(val: int) -> int:
    return val + 1


@pytest.fixture
def ping_pong_topology():
    d1 = PhysicsDataNode(id="D1", name="Input")
    f1 = PhysicsFuncNode(id="F1", name="Increment")
    d2 = PhysicsDataNode(id="D2", name="Output")

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, f1, d2]}

    # D1 -> F1
    graph.channels.append(
        Channel(source_node_id=d1.id, source_port="value", target_node_id=f1.id)
    )
    # F1 -> D2
    graph.channels.append(
        Channel(source_node_id=f1.id, source_port="result", target_node_id=d2.id)
    )

    # The runtime binding between the abstract physics node and the concrete function
    function_map: Dict[str, Callable] = {f1.id: simple_increment}

    return graph, d1, f1, d2, function_map


@pytest.mark.asyncio
async def test_ping_pong_flow(ping_pong_topology):
    graph, d1, f1, d2, function_map = ping_pong_topology

    memory = VolatileMemory()
    executor = PhysicsExecutor()
    reactor = Reactor(graph, memory, executor, function_map)

    # 1. Start state
    initial_token = Token(payload=10)
    memory.put(d1, initial_token)

    # 2. Run the physics simulation for one step
    fired_count = await reactor.step()

    # 3. Assertions
    assert fired_count == 1

    # Input token should be consumed
    assert memory.get_count(d1.id) == 0

    # Output node should receive the result
    assert memory.get_count(d2.id) == 1

    result_token = memory.take(d2.id)
    assert result_token.payload == 11  # 10 + 1
