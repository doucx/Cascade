import pytest
import asyncio
from typing import Dict, List
from functools import partial

from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.physics import Token, PhysicsDataNode
from cascade.compiler.backend.builder import Builder
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor
from cascade.vm.instructions.bleacher import standard_bleacher
from cascade.vm.instructions.stainer import standard_stainer
from cascade.vm.instructions.observer import standard_observer
from cascade.spec.topology import BipartiteGraph, Channel


# --- Mocks ---

def mock_worker(inputs: Dict[str, Token]) -> Dict[str, Token]:
    # Simulate work
    val = inputs["x"].payload
    return {"worker_result": Token(payload=val + 1)}

# --- Test ---

@pytest.mark.asyncio
async def test_concurrency_limit():
    # 1. Define a graph with 2 nodes, both needing the same resource 'GPU'.
    # We will set the global GPU resource to have initial_tokens = 1.
    # This should force them to run sequentially.
    
    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(name="task", args=[ArgumentDef("x", "POSITIONAL")], fingerprint=fp)
    
    node_1 = NodeIR(
        id="node_1", 
        name="Task1", 
        task=task_def, 
        inputs={"x": 10}, 
        constraints={"gpu": 1}
    )
    node_2 = NodeIR(
        id="node_2", 
        name="Task2", 
        task=task_def, 
        inputs={"x": 20}, 
        constraints={"gpu": 1}
    )
    
    graph_ir = GraphIR(nodes=[node_1, node_2])
    
    # 2. Build Physical Graph
    builder = Builder()
    physical_graph = builder.build(graph_ir)
    
    # Verify D_res exists
    assert "global_res_gpu" in physical_graph.nodes
    d_res = physical_graph.nodes["global_res_gpu"]
    # Force capacity to 1 for this test (Builder currently defaults to 1)
    d_res.initial_tokens = 1 
    
    # 3. Setup VM
    memory = VolatileMemory()
    executor = PhysicsExecutor()
    
    # Map functions
    # Note: We must bind expected_args for bleacher so it knows 'x' is data, 'res_gpu' is resource
    bleacher_fn = partial(standard_bleacher, expected_args=["x"])
    
    func_map = {}
    for node_id in physical_graph.nodes:
        if node_id.endswith("_bleach"):
            func_map[node_id] = bleacher_fn
        elif node_id.endswith("_stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith("_worker"):
            func_map[node_id] = mock_worker
        # We don't map observers here to keep it simple, 
        # but in real code we would need to or Reactor will fail if it tries to fire them.
        # Actually, Reactor only fires nodes that are ready. 
        # Observers need D_life input. We haven't wired D_life inputs in this test setup manually,
        # but Builder did. D_life starts empty. So Observers won't fire unless D_life gets tokens.
        # Wait, D_life gets tokens from Bleacher/Stainer. So Observers WILL become ready.
        # We must map them to a no-op or mock.
        elif "d_life" in node_id: # Not a func node
            pass
    
    # We need to handle the global D_life observability sidecar if we want full correctness.
    # Builder created 'global_d_life'.
    # But Builder did NOT create an F_obs node attached to it in the current implementation?
    # Let's check builder.py...
    # Builder creates 'd_life' DataNode. But it does NOT seem to create the F_obs node consuming it.
    # It just wires output ports TO d_life.
    # This means d_life will fill up with events. This is fine for this test.
    
    reactor = Reactor(physical_graph, memory, executor, func_map)
    
    # 4. Prime the reactor (Fill D_res)
    reactor.prime()
    assert memory.get_count("global_res_gpu") == 1
    
    # 5. Inject Inputs
    # We need to manually inject inputs for the tasks because Builder doesn't handle Literals yet
    # (Comment in Builder: "We only handle inter-node references here. Literals are handled later.")
    # So we manually put tokens in D_worker_in? No, D_worker_in is internal.
    # Bleacher needs inputs.
    # Bleacher inputs are usually wired from upstream. Here we have literals.
    # In a full system, literals are handled by Constant Nodes or injected at start.
    # For this test, we manually identify the input slots for Bleacher and fill them.
    
    # Builder doesn't create DataNodes for inputs unless they come from upstream.
    # Wait, Expander creates input ports for Bleacher.
    # But who connects to them?
    # If it's a literal, currently NO ONE connects to them in the physical graph.
    # This is a gap in the current Builder implementation for Literals.
    # For this test, we will assume we need to manually put tokens into the Bleacher's input memory.
    # But Reactor consumes from DataNodes. The Bleacher's input ports need to be connected to SOMETHING.
    # If Builder didn't create a DataNode for the literal 'x', Reactor won't find an input source 
    # and thus won't fire.
    
    # FIX for Test: We need to patch the graph to add input DataNodes for 'x'.
    for node_prefix, val in [("node_1", 10), ("node_2", 20)]:
        d_literal = PhysicsDataNode(id=f"{node_prefix}_in_x", name="Literal X")
        physical_graph.nodes[d_literal.id] = d_literal
        physical_graph.channels.append(
            Channel(d_literal.id, "out", f"{node_prefix}_bleach", target_port="x")
        )
        memory.put(d_literal, Token(payload=val))
        
        # We also need to re-initialize Reactor because we modified the graph
    
    reactor = Reactor(physical_graph, memory, executor, func_map)
    reactor.prime()

    # 6. Step Execution
    # Step 1: Both Bleachers are ready on 'x', but contend for 'res_gpu'.
    # Only ONE should fire.
    fired = await reactor.step()
    # What fires?
    # 1. Bleacher (consumes 1 GPU, 1 X) -> fires.
    # The other Bleacher cannot fire because D_res is empty.
    
    assert fired == 1
    assert memory.get_count("global_res_gpu") == 0 # Resource taken
    
    # Step 2: The fired Triad proceeds. 
    # Worker fires.
    await reactor.step() 
    
    # Step 3: Stainer fires. 
    # This should return the resource.
    await reactor.step()
    
    assert memory.get_count("global_res_gpu") == 1 # Resource returned!
    
    # Step 4: Now the second Bleacher can fire.
    fired_2 = await reactor.step()
    assert fired_2 == 1
    assert memory.get_count("global_res_gpu") == 0
    
    # Step 5 & 6: Finish second task
    await reactor.step() # Worker
    await reactor.step() # Stainer
    
    assert memory.get_count("global_res_gpu") == 1
