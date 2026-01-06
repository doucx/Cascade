import pytest
from cascade.spec.physical.nodes import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.ports import PortDef, PortRole, PortName
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.std.resource.discrete import (
    discrete_allocator,
    discrete_reclaimer,
    DiscreteLedger,
)


def create_starvation_topology(allocator_first: bool):
    # Setup:
    # Ledger: Total=1, Available=0 (Starved)
    # Req: 1 (Blocked)
    # Rel: 1 (Pending)

    ledger_id = "D_ledger"
    ledger = DiscreteLedger(total=1, available=0)
    d_ledger = PhysicsDataNode(
        id=ledger_id,
        name="Ledger",
        capacity=1,
        initial_tokens=1,
        initial_payload=ledger,
    )

    # Allocator
    alloc_id = "F_alloc"
    f_alloc = PhysicsFuncNode(
        id=alloc_id,
        name="Allocator",
        input_ports={
            PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
            PortName.REQ: PortDef(PortName.REQ, PortRole.DATA),
        },
        output_ports={
            PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
            PortName.GNT: PortDef(PortName.GNT, PortRole.RESOURCE),
            PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA),
        },
    )

    # Reclaimer
    reclaim_id = "F_reclaim"
    f_reclaim = PhysicsFuncNode(
        id=reclaim_id,
        name="Reclaimer",
        input_ports={
            PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
            PortName.REL: PortDef(PortName.REL, PortRole.DATA),
        },
        output_ports={
            PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
        },
    )

    # Buffers
    d_req = PhysicsDataNode(
        id="D_req", name="ReqBuf", capacity=10, initial_tokens=1, initial_payload=1
    )
    d_rel = PhysicsDataNode(
        id="D_rel", name="RelBuf", capacity=10, initial_tokens=1, initial_payload=1
    )

    graph = BipartiteGraph()

    # CONTROL THE ORDER HERE
    # Reactor iterates over graph.nodes values or internally constructed list.
    # Currently Reactor iterates over self._func_nodes which is built from graph.nodes.values()
    # Python 3.7+ dicts preserve insertion order.

    nodes_list = [d_ledger, d_req, d_rel]
    if allocator_first:
        nodes_list.extend([f_alloc, f_reclaim])
    else:
        nodes_list.extend([f_reclaim, f_alloc])

    for n in nodes_list:
        graph.nodes[n.id] = n

    # Wiring
    # Ledger Loop Allocator
    graph.channels.append(Channel(ledger_id, "out", alloc_id, PortName.LEDGER_IN))
    graph.channels.append(Channel(alloc_id, PortName.LEDGER_OUT, ledger_id, "in"))

    # Ledger Loop Reclaimer
    graph.channels.append(Channel(ledger_id, "out", reclaim_id, PortName.LEDGER_IN))
    graph.channels.append(Channel(reclaim_id, PortName.LEDGER_OUT, ledger_id, "in"))

    # Inputs
    graph.channels.append(Channel(d_req.id, "out", alloc_id, PortName.REQ))
    graph.channels.append(Channel(d_rel.id, "out", reclaim_id, PortName.REL))

    # Recirculation
    graph.channels.append(Channel(alloc_id, PortName.REQ_OUT, d_req.id, "in"))

    func_map = {alloc_id: discrete_allocator, reclaim_id: discrete_reclaimer}

    return graph, d_ledger, d_req, d_rel, func_map


@pytest.mark.asyncio
async def test_allocator_starves_reclaimer():
    graph, d_ledger, d_req, d_rel, func_map = create_starvation_topology(
        allocator_first=True
    )

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, func_map)
    reactor.prime()

    # Step 1
    # Allocator should fire (it sees Ledger and Req).
    # Reclaimer sees Ledger and Rel, BUT Ledger is consumed by Allocator first.
    fired = reactor.step()

    assert fired == 1

    # Check Ledger State: Should still be 0 available (Allocator failed and returned it)
    ledger = memory.take(d_ledger.id).payload
    memory.put(d_ledger, Token(payload=ledger))
    assert ledger.available == 0

    # Check D_rel: Should still be 1 (Reclaimer didn't run)
    assert memory.get_count(d_rel.id) == 1

    # Step 2
    # Allocator fires AGAIN.
    fired = reactor.step()

    assert fired == 1
    assert memory.get_count(d_rel.id) == 1  # Reclaimer STILL hasn't ran


@pytest.mark.asyncio
async def test_reclaimer_priority_fixes_starvation():
    graph, d_ledger, d_req, d_rel, func_map = create_starvation_topology(
        allocator_first=False
    )

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, func_map)
    reactor.prime()

    # Step 1
    # Reclaimer should fire first.
    fired = reactor.step()

    assert fired >= 1  # Could be 1 (Reclaim) or 2 (Reclaim then Alloc in same step?)
    # Wait, in one step, if Reclaim consumes Ledger, Allocator CANNOT fire in that same step.
    # So fired should be 1.

    # Check Ledger State: Should be 1 available (Reclaimed)
    ledger = memory.take(d_ledger.id).payload
    memory.put(d_ledger, Token(payload=ledger))
    assert ledger.available == 1

    # Check D_rel: Should be 0 (Consumed)
    assert memory.get_count(d_rel.id) == 0

    # Step 2
    # Now Allocator should fire and SUCCEED
    fired = reactor.step()

    # Ledger should be 0 again (Granted)
    ledger = memory.take(d_ledger.id).payload
    memory.put(d_ledger, Token(payload=ledger))
    assert ledger.available == 0

    # Request consumed (or recirculated if we count that, but here it succeeds so GNT emitted)
    # Check GNT output? We didn't wire GNT to a buffer in this test helper, but we can infer from Ledger.
