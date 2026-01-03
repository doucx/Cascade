import pytest
from typing import Dict
import sys

from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef, ArgumentDef
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.physics import Token
from cascade.spec.environment import EnvironmentDef, ResourceDef
from cascade.compiler.backend.builder import Builder
from cascade.vm.harness import EventDrivenRunner

# Import new ICs
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe


# --- Mocks ---


def mock_worker(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    worker_input_token = inputs["worker_input"]
    worker_payload = worker_input_token.payload
    val = worker_payload["x"]
    return {"worker_result": Token(payload=val + 1)}


# --- Test ---


@pytest.mark.asyncio
async def test_concurrency_limit_event_driven():
    # 1. Define a graph with 2 nodes, both needing the same resource 'GPU'.
    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(
        name="task", args=[ArgumentDef("x", "POSITIONAL")], fingerprint=fp
    )

    node_1 = NodeIR(
        id="node_1",
        name="Task1",
        task=task_def,
        inputs={"x": 10},
        constraints={"gpu": 1},
    )
    node_2 = NodeIR(
        id="node_2",
        name="Task2",
        task=task_def,
        inputs={"x": 20},
        constraints={"gpu": 1},
    )

    graph_ir = GraphIR(nodes=[node_1, node_2])

    # 2. Define Environment and Build Physical Graph
    env = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1)])
    builder = Builder()
    physical_graph = builder.build(graph_ir, environment=env)

    # 3. Construct Function Map
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
        elif "global.observability.observer" in node_id:
            func_map[node_id] = standard_observer

    # 4. Initialize EventDrivenRunner
    runner = EventDrivenRunner(physical_graph, func_map)
    runner.prime()

    # Assert initial state of Ledger
    ledger_node_id = "canonical.resource.ledger.gpu"
    assert runner.memory.get_count(ledger_node_id) == 1
    ledger = runner.memory.take(ledger_node_id).payload
    assert ledger.available == 1
    # Put it back
    runner.inject_input(ledger_node_id, ledger)

    # 5. Start the Reactor Loop
    await runner.start_loop()

    try:
        # 6. Wait for tasks to complete
        # Since resource capacity is 1, they must run sequentially.
        # But we don't strictly enforce order here, just that BOTH finish.
        
        # Note: In a real EventDrivenRunner, we might want a 'wait_for_all' helper.
        # For now, we wait for them individually. The order doesn't matter for correctness,
        # but logically one will finish before the other.
        
        # We collect completion events
        completed_tasks = set()
        
        def completion_predicate(event):
            if event.event_type == "end" and event.trace_data.get("id") in ["node_1", "node_2"]:
                completed_tasks.add(event.trace_data.get("id"))
            return len(completed_tasks) == 2

        # Wait until both are done (timeout generous because of backoff/recirculation latency)
        await runner.wait_for_event(completion_predicate, timeout=5.0)
        
        assert "node_1" in completed_tasks
        assert "node_2" in completed_tasks

        # 7. Final State Verification
        # Ledger should be full again
        ledger = runner.memory.take(ledger_node_id).payload
        assert ledger.available == 1
        
        # Buffers should be empty
        assert runner.memory.get_count("buffer.req.gpu") == 0
        
    finally:
        await runner.stop_loop()