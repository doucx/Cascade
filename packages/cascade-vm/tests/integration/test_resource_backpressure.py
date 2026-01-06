import pytest
from typing import Dict

from cascade.spec.ir.graph import GraphIR, NodeIR, TaskDef, ArgumentDef
from cascade.spec.ir.fingerprint import Fingerprint
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.compiler.backend.builder import Builder
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.resource_registry import ResourceRegistry
from cascade.runtime.storage import InMemoryObjectStore

# Import new ICs
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.spec.physical.object import Ref


# --- Mocks ---


def mock_worker(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    worker_input_token = inputs["worker_input"]
    worker_payload = worker_input_token.payload

    # Handle Ref-based payload (v3.1)
    val = worker_payload["x"]
    if isinstance(val, Ref):
        # In this specific test, we know const_probe hoists scalar values.
        # So we can peek at meta. In a real worker, we'd use store.get().
        if "scalar_value" in val.meta:
            val = val.meta["scalar_value"]
        else:
            # Fallback for completeness, though test setup should ensure hoisting
            store = resources.get("system.object_store")
            val = store.get(val)

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
        elif "observability" in node_id:
            func_map[node_id] = noop_observer

    # 5. Initialize Reactor
    # Probe needs an object store to materialize scalar values into Refs
    registry = ResourceRegistry()
    store = InMemoryObjectStore()
    registry.register("system.object_store", store)

    reactor = Reactor(physical_graph, memory, func_map, resource_registry=registry)

    # 6. Prime the reactor.
    reactor.prime()

    # Assert initial state of Ledger
    ledger_node_id = "canonical.resource.ledger.gpu"
    assert memory.get_count(ledger_node_id) == 1
    ledger = memory.take(ledger_node_id).payload
    assert ledger.available == 1
    memory.put(physical_graph.nodes[ledger_node_id], Token(payload=ledger))

    # --- SIMULATION ---
    # With direct D_const -> F_req wiring, requestors fire on the first step.

    # Step 1: Requestors for both tasks fire, populating the request buffer.
    reactor.step()

    # Check Buffer state
    req_buffer_id = "buffer.req.gpu"
    assert memory.get_count(req_buffer_id) == 2  # Both requests are in buffer

    # Round 3: Allocator fires.
    # It consumes Ledger + ONE request from Buffer.
    # Since capacity is 1, it Grants.
    reactor.step()

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

    reactor.step()

    # If Allocator fired, it recirculated the request back to Buffer.
    # If Bleacher fired, it started the triad.

    # Let's run until one Task completes (Stainer fires)
    # This involves: Worker -> Stainer -> RelBuffer -> Reclaimer -> Ledger

    # We loop until resource is released (Ledger becomes 1)
    max_steps = 30
    for _ in range(max_steps):
        reactor.step()

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
        reactor.step()

    # Final check: Ledger full, Buffers empty
    ledger = memory.take(ledger_node_id).payload
    assert ledger.available == 1
    assert memory.get_count(req_buffer_id) == 0
