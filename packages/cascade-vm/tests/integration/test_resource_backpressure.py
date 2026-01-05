import pytest
from typing import Dict

from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef, ArgumentDef
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.physics import Token
from cascade.spec.environment import EnvironmentDef, ResourceDef
from cascade.compiler.backend.builder import Builder
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor

# Import new ICs
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe


# --- Mocks ---


def mock_worker(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    worker_input_token = inputs["worker_input"]
    worker_payload = worker_input_token.payload
    val = worker_payload["x"]
    return {"worker_result": Token(payload=val + 1)}


def noop_observer(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    return {}


# --- Test ---


@pytest.mark.asyncio
async def test_concurrency_limit():
    # 1. Define a graph with 2 nodes, both needing the same resource 'GPU'.
    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(
        name="task", args=[ArgumentDef("x", "POSITIONAL")], fingerprint=fp
    )

    node_1 = NodeIR(
        current_node_instance_hash="node_1",
        name="Task1",
        task=task_def,
        inputs={"x": 10},
        constraints={"gpu": 1},
    )
    node_2 = NodeIR(
        current_node_instance_hash="node_2",
        name="Task2",
        task=task_def,
        inputs={"x": 20},
        constraints={"gpu": 1},
    )

    graph_ir = GraphIR(nodes=[node_1, node_2])

    # 2. Define Environment and Build Physical Graph
    env = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1)])
    builder = Builder()
    assembly = builder.build(graph_ir, environment=env)
    physical_graph = assembly.graph

    # 3. Setup VM
    memory = VolatileMemory()
    executor = PhysicsExecutor()

    # Map functions
    func_map = {}
    for node_id in physical_graph.nodes:
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"):
            func_map[node_id] = mock_worker
        elif "allocator" in node_id:
            func_map[node_id] = discrete_allocator
        elif "reclaimer" in node_id:
            func_map[node_id] = discrete_reclaimer
        elif node_id.startswith("req."):
            func_map[node_id] = resource_requestor
        elif node_id.startswith("probe.const."):
            func_map[node_id] = const_probe
        elif "observability" in node_id:
            func_map[node_id] = noop_observer

    # 5. Initialize Reactor
    reactor = Reactor(physical_graph, memory, executor, func_map)

    # 6. Prime the reactor.
    reactor.prime()

    # Assert initial state of Ledger
    ledger_node_id = "canonical.resource.ledger.gpu"
    assert memory.get_count(ledger_node_id) == 1
    ledger = memory.take(ledger_node_id).payload
    assert ledger.available == 1
    memory.put(physical_graph.nodes[ledger_node_id], Token(payload=ledger))

    # 7. Step Execution Logic
    async def wait_idle():
        import asyncio

        while reactor.active_task_count > 0:
            await asyncio.sleep(0.001)

    # --- SIMULATION ---
    # The new graph has many more steps due to Probe -> Req -> Broker -> Bleacher

    # Round 1: Probes fire (providing Amount and X)
    await reactor.step()
    await wait_idle()

    # Round 2: Requestors fire (sending Req Tokens to Buffer)
    await reactor.step()
    await wait_idle()

    # Check Buffer state
    req_buffer_id = "buffer.req.gpu"
    assert memory.get_count(req_buffer_id) == 2  # Both requests are in buffer

    # Round 3: Allocator fires.
    # It consumes Ledger + ONE request from Buffer.
    # Since capacity is 1, it Grants.
    await reactor.step()
    await wait_idle()

    # Ledger should now have 0 available
    ledger = memory.take(ledger_node_id).payload
    assert ledger.available == 0
    memory.put(physical_graph.nodes[ledger_node_id], Token(payload=ledger))

    # Buffer should have 1 request remaining
    assert memory.get_count(req_buffer_id) == 1

    # Round 4:
    # - The lucky Bleacher (who got GNT) fires.
    # - The Allocator attempts to fire again for the second request?
    #   Yes, it reads Ledger(0) and Request(1).
    #   Logic: 0 < 1. Reject & Recirculate.

    await reactor.step()
    await wait_idle()

    # If Allocator fired, it recirculated the request back to Buffer.
    # If Bleacher fired, it started the triad.

    # Let's run until one Task completes (Stainer fires)
    # This involves: Worker -> Stainer -> RelBuffer -> Reclaimer -> Ledger

    # We loop until resource is released (Ledger becomes 1)
    max_steps = 30
    for _ in range(max_steps):
        await reactor.step()
        await wait_idle()

        # Check if resource returned
        ledger = memory.take(ledger_node_id).payload
        memory.put(physical_graph.nodes[ledger_node_id], Token(payload=ledger))
        if ledger.available == 1:
            break

    assert ledger.available == 1

    # Now the second task can proceed.
    # Allocator fires -> Grants -> Bleacher -> Worker -> Stainer -> Reclaimer
    for _ in range(20):
        if (
            memory.get_count(req_buffer_id) == 0
            and memory.get_count("buffer.rel.gpu") == 0
        ):
            # If buffers are empty and tasks done, we are good.
            pass
        await reactor.step()
        await wait_idle()

    # Final check: Ledger full, Buffers empty
    ledger = memory.take(ledger_node_id).payload
    assert ledger.available == 1
    assert memory.get_count(req_buffer_id) == 0
