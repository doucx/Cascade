import pytest
import asyncio
from typing import Dict

from cascade.spec.physical.nodes import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor


def switch_logic(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    in_token = inputs["in"]
    direction = in_token.payload

    # Sovereign routing: explicitly choose output port
    if direction == "path_a":
        return {"out_a": Token(payload="Data A")}
    else:
        return {"out_b": Token(payload="Data B")}


@pytest.fixture
def branching_topology():
    # D_in -> Switch -> (D_A, D_B)
    d_in = PhysicsDataNode(id="D_in", name="Input")
    f_sw = PhysicsFuncNode(
        id="Switch",
        name="SwitchNode",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        # Define multiple sovereign output ports
        output_ports={
            "out_a": PortDef("out_a", PortRole.DATA),
            "out_b": PortDef("out_b", PortRole.DATA),
        },
    )
    d_a = PhysicsDataNode(id="D_A", name="Branch A")
    d_b = PhysicsDataNode(id="D_B", name="Branch B")

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_in, f_sw, d_a, d_b]}

    # Wiring
    # D_in -> Switch
    graph.channels.append(Channel(d_in.id, "out", f_sw.id, target_port="in"))

    # Switch -> D_A (Connect to out_a)
    graph.channels.append(Channel(f_sw.id, "out_a", d_a.id, target_port="in"))

    # Switch -> D_B (Connect to out_b)
    graph.channels.append(Channel(f_sw.id, "out_b", d_b.id, target_port="in"))

    func_map = {f_sw.id: switch_logic}

    return graph, d_in, d_a, d_b, func_map


async def wait_for_idle(reactor: Reactor):
    while reactor.active_task_count > 0:
        await asyncio.sleep(0.001)


@pytest.mark.asyncio
async def test_branching_path_a(branching_topology):
    graph, d_in, d_a, d_b, func_map = branching_topology

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, PhysicsExecutor(), func_map)

    # 1. Inject signal for Path A
    memory.put(d_in, Token(payload="path_a"))

    # 2. Run
    await reactor.step()
    await wait_for_idle(reactor)

    # 3. Assert
    # D_A should receive token
    assert memory.get_count(d_a.id) == 1
    assert memory.take(d_a.id).payload == "Data A"

    # D_B should be empty (physically blocked)
    assert memory.get_count(d_b.id) == 0


@pytest.mark.asyncio
async def test_branching_path_b(branching_topology):
    graph, d_in, d_a, d_b, func_map = branching_topology

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, PhysicsExecutor(), func_map)

    # 1. Inject signal for Path B
    memory.put(d_in, Token(payload="path_b"))

    # 2. Run
    await reactor.step()
    await wait_for_idle(reactor)

    # 3. Assert
    # D_B should receive token
    assert memory.get_count(d_b.id) == 1
    assert memory.take(d_b.id).payload == "Data B"

    # D_A should be empty
    assert memory.get_count(d_a.id) == 0
