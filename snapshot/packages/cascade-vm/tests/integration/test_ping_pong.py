import pytest
from typing import Dict, Callable

from cascade.spec.physical.nodes import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.resource_registry import ResourceRegistry


def simple_increment(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    # Extract
    in_token = inputs["value"]
    val = in_token.payload

    # Process
    res = val + 1

    # Wrap
    return {"result": Token(payload=res)}


@pytest.fixture
def ping_pong_topology():
    d1 = PhysicsDataNode(id="D1", name="Input")
    f1 = PhysicsFuncNode(
        id="F1",
        name="Increment",
        input_ports={"value": PortDef("value", PortRole.DATA)},
        output_ports={"result": PortDef("result", PortRole.DATA)},
    )
    d2 = PhysicsDataNode(id="D2", name="Output")

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, f1, d2]}

    # D1 -> F1 (Explicit target port 'value')
    graph.channels.append(
        Channel(
            source_node_id=d1.id,
            source_port="out",
            target_node_id=f1.id,
            target_port="value",
        )
    )
    # F1 -> D2
    graph.channels.append(
        Channel(
            source_node_id=f1.id,
            source_port="result",
            target_node_id=d2.id,
            target_port="in",
        )
    )

    # The runtime binding between the abstract physics node and the concrete function
    function_map: Dict[str, Callable] = {f1.id: simple_increment}

    return graph, d1, f1, d2, function_map


@pytest.mark.asyncio
async def test_ping_pong_flow(ping_pong_topology):
    graph, d1, f1, d2, function_map = ping_pong_topology

    memory = VolatileMemory()
    resources = ResourceRegistry()
    kernel = PhysicsKernel(function_map, resources)
    reactor = Reactor(graph, memory, kernel)

    # 1. Start state
    initial_token = Token(payload=10)
    memory.put(d1, initial_token)

    # 2. Run the physics simulation for one step
    fired_count = reactor.step()

    # 3. Assertions
    assert fired_count == 1

    # Input token should be consumed
    assert memory.get_count(d1.id) == 0

    # Output node should receive the result
    assert memory.get_count(d2.id) == 1

    result_token = memory.take(d2.id)
    assert result_token.payload == 11  # 10 + 1
