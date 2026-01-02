import pytest
from typing import Dict
from functools import partial

from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef, ArgumentDef
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.physics import Token
from cascade.spec.environment import EnvironmentDef, ResourceDef
from cascade.compiler.backend.builder import Builder
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor
from cascade.vm.instructions.bleacher import standard_bleacher
from cascade.vm.instructions.stainer import standard_stainer


# --- Mocks ---


def mock_worker(inputs: Dict[str, Token]) -> Dict[str, Token]:
    # The WorkerNode receives a single token on its 'worker_input' port.
    # The payload of this token is the dictionary of actual arguments.
    worker_input_token = inputs["worker_input"]
    worker_payload = worker_input_token.payload

    # Simulate work based on the unpacked payload
    val = worker_payload["x"]  # The payload is the raw value, not another Token
    return {"worker_result": Token(payload=val + 1)}


# --- Test ---


@pytest.mark.asyncio
async def test_concurrency_limit():
    # 1. Define a graph with 2 nodes, both needing the same resource 'GPU'.
    # We will set the global GPU resource to have initial_tokens = 1.
    # This should force them to run sequentially.

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

    # Verify D_res exists and was configured by the environment
    assert "canonical.resource.gpu" in physical_graph.nodes
    d_res = physical_graph.nodes["canonical.resource.gpu"]
    assert d_res.initial_tokens == 1

    # 3. Setup VM
    memory = VolatileMemory()
    executor = PhysicsExecutor()

    # Map functions
    # Note: We must bind expected_args for bleacher so it knows 'x' is data, 'res_gpu' is resource
    bleacher_fn = partial(standard_bleacher, expected_args=["x"])

    func_map = {}
    for node_id in physical_graph.nodes:
        if node_id.endswith(".bleach"):
            func_map[node_id] = bleacher_fn
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"):
            func_map[node_id] = mock_worker
        # We don't map observers here to keep it simple,
        # but in real code we would need to or Reactor will fail if it tries to fire them.
        # Actually, Reactor only fires nodes that are ready.
        # Observers need D_life input. We haven't wired D_life inputs in this test setup manually,
        # but Builder did. D_life starts empty. So Observers won't fire unless D_life gets tokens.
        # Wait, D_life gets tokens from Bleacher/Stainer. So Observers WILL become ready.
        # We must map them to a no-op or mock.
        elif "observability" in node_id:  # Not a func node
            pass

    # We need to handle the global D_life observability sidecar if we want full correctness.
    # Builder created 'global_d_life'.

    # 4. (Deleted) Manual DataNode creation is no longer needed.
    # The Builder now automatically creates 'const_node_1_x' and 'const_node_2_x'
    # based on the literals in NodeIR.inputs.

    # 5. Initialize Reactor
    reactor = Reactor(physical_graph, memory, executor, func_map)

    # 6. Prime the reactor.
    # This should fill:
    # - global_res_gpu (1 token, payload=None)
    # - const_node_1_x (1 token, payload=10)
    # - const_node_2_x (1 token, payload=20)
    reactor.prime()

    assert memory.get_count("canonical.resource.gpu") == 1
    assert memory.get_count("const.node_1.x") == 1
    assert memory.get_count("const.node_2.x") == 1

    # Verify payloads
    t1 = memory.take("const.node_1.x")
    assert t1.payload == 10
    memory.put(physical_graph.nodes["const.node_1.x"], t1)  # Put it back for execution

    t2 = memory.take("const.node_2.x")
    assert t2.payload == 20
    memory.put(physical_graph.nodes["const.node_2.x"], t2)  # Put it back

    # 7. Step Execution
    # Step 1: Both Bleachers are ready on 'x', but contend for 'res_gpu'.
    # With the new atomic Reactor, only ONE should fire.
    fired = await reactor.step()
    # What fires?
    # 1. Bleacher (consumes 1 GPU, 1 X) -> fires.
    # The other Bleacher cannot fire because D_res is empty.

    assert fired == 1
    assert memory.get_count("canonical.resource.gpu") == 0  # Resource taken

    # Step 2: The fired Triad proceeds.
    # Worker fires.
    await reactor.step()

    # Step 3: Stainer fires.
    # This should return the resource.
    await reactor.step()

    assert memory.get_count("canonical.resource.gpu") == 1  # Resource returned!

    # Step 4: Now the second Bleacher can fire.
    fired_2 = await reactor.step()
    assert fired_2 == 1
    assert memory.get_count("canonical.resource.gpu") == 0

    # Step 5 & 6: Finish second task
    await reactor.step()  # Worker
    await reactor.step()  # Stainer

    assert memory.get_count("canonical.resource.gpu") == 1
