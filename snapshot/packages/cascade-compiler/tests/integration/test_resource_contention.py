import pytest
import asyncio
from typing import Dict, List, Tuple

from cascade.spec.task import task
from cascade.compiler.frontend.generator import IRGenerator
from cascade.compiler.backend.builder import Builder
from cascade.spec.environment import EnvironmentDef, ResourceDef
from cascade.spec.physics import Token
from cascade.spec.ports import PortRole
from cascade.vm.harness import EventDrivenRunner, ObservedEvent
from cascade.compiler.utils.inspector import GraphInspector
from cascade.compiler.utils.naming import PhysicalIdGenerator

# Standard IC imports
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe


@task
def resource_heavy_task(duration: float = 0.01):
    # Simulate work
    import time
    time.sleep(duration)
    return "Done"

# Mock Worker
def mock_worker(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    worker_input_token = inputs["worker_input"]
    trace = worker_input_token.trace
    
    # Simulate execution duration
    payload = worker_input_token.payload
    duration = payload.get("duration", 0.0)
    
    # We cheat a bit and sleep async here to allow reactor to switch contexts
    # In a real ThreadPool executor, this would be time.sleep
    # But since we use PhysicsExecutor in tests which is threaded, time.sleep is fine.
    # However, to keep tests fast, we assume the duration is small.
    import time
    time.sleep(duration)
    
    return {"worker_result": Token(payload="Done", trace=trace)}


@pytest.mark.asyncio
async def test_resource_scarcity_topology_and_execution():
    # Configuration
    TASK_COUNT = 50
    RESOURCE_CAPACITY = 3
    RESOURCE_NAME = "gpu"
    
    # 1. Generate Logical Graph
    tasks = []
    for _ in range(TASK_COUNT):
        # Each task needs 1 GPU
        t = resource_heavy_task(duration=0.005).with_constraints(gpu=1)
        tasks.append(t)
        
    # We group them in a list to generate graph
    ir_generator = IRGenerator()
    # IRGenerator can handle a list of LazyResults (it treats them as independent roots)
    graph_ir = ir_generator.generate(tasks)
    
    # 2. Build Physical Graph
    env = EnvironmentDef(resources=[ResourceDef(name=RESOURCE_NAME, capacity=RESOURCE_CAPACITY)])
    builder = Builder()
    physical_graph = builder.build(graph_ir, env)
    
    # --- PART A: TOPOLOGY ASSERTION ---
    inspector = GraphInspector(physical_graph)
    
    # Verify Allocator Ports
    allocator_id = PhysicalIdGenerator.global_allocator(RESOURCE_NAME)
    inspector.assert_node_exists(allocator_id)
    
    # Allocator should have:
    # - 1 'ledger_out'
    # - 1 'gnt' (legacy/fallback, defined in builder but maybe unused)
    # - 1 'req_out'
    # - 50 dynamic 'gnt_for_...' ports
    
    # Let's count RESOURCE role ports.
    # Legacy 'gnt_out' is RESOURCE. Dynamic ones are RESOURCE.
    # Total should be 50 + 1 = 51.
    inspector.assert_port_count(allocator_id, count=TASK_COUNT + 1, role=PortRole.RESOURCE)
    
    # Verify Wiring
    # Pick a random task node to verify its path
    sample_node_ir = graph_ir.nodes[0]
    # Path: Allocator -> D_gnt -> Bleacher
    # We need to find the specific grant port for this task.
    # It requires the ID of the Requestor node.
    req_id = PhysicalIdGenerator.requestor(sample_node_ir.id, RESOURCE_NAME)
    expected_port = f"gnt_for_{req_id}"
    
    inspector.assert_port_exists(allocator_id, expected_port)
    
    # Verify connection to intermediate D_gnt
    # We don't know D_gnt ID easily without reconstructing logic, but we can search channels
    channels = inspector.find_channels_from(allocator_id, expected_port)
    assert len(channels) == 1
    d_gnt_id = channels[0].target_node_id
    
    inspector.get_data_node(d_gnt_id) # Should be a data node
    
    # Verify D_gnt -> Bleacher
    bleacher_id = PhysicalIdGenerator.bleach_node(sample_node_ir.id)
    inspector.assert_connection(d_gnt_id, bleacher_id, target_port=f"res_{RESOURCE_NAME}")

    # --- PART B: EXECUTION ASSERTION ---
    
    # Function Map
    func_map = {}
    for node_id in physical_graph.nodes:
        if node_id.endswith(".bleach"): func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"): func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"): func_map[node_id] = mock_worker
        elif "allocator" in node_id: func_map[node_id] = discrete_allocator
        elif "reclaimer" in node_id: func_map[node_id] = discrete_reclaimer
        elif node_id.startswith("req."): func_map[node_id] = resource_requestor
        elif node_id.startswith("probe.const."): func_map[node_id] = const_probe
        elif "observability" in node_id: func_map[node_id] = standard_observer
            
    runner = EventDrivenRunner(physical_graph, func_map)
    runner.prime()
    
    await runner.start_loop()
    
    try:
        # Collect all 'start' and 'end' events
        events: List[ObservedEvent] = []
        
        # We wait until we have 2 * TASK_COUNT events (start + end for each)
        # We need a robust condition.
        def collection_predicate(e: ObservedEvent):
            if e.event_type in ("start", "end") and e.trace_data.get("id", "").startswith("node_"):
                events.append(e)
            # Stop when we have all completion events
            completed = sum(1 for x in events if x.event_type == "end")
            return completed == TASK_COUNT

        # Timeout needs to be generous for 50 tasks with concurrency 3
        # 50 tasks / 3 concurrent * 0.005s per task ~= 0.08s (theoretical minimum)
        # But overhead is high. Let's give it 5 seconds.
        await runner.wait_for_event(collection_predicate, timeout=5.0)
        
        # Analyze Concurrency
        # Convert events to intervals [start, end]
        intervals: Dict[str, Dict[str, float]] = {}
        for e in events:
            tid = e.trace_data["id"]
            if tid not in intervals: intervals[tid] = {}
            
            if e.event_type == "start":
                intervals[tid]["start"] = e.trace_data["start_ts"]
            elif e.event_type == "end":
                intervals[tid]["end"] = e.trace_data["end_ts"]
                
        # Check max overlap
        # We sample at the start time of each task
        max_concurrency = 0
        
        sorted_starts = sorted([info["start"] for info in intervals.values() if "start" in info])
        
        for t in sorted_starts:
            # Count how many tasks are active at time t (start <= t < end)
            # We use a small epsilon for float comparison safety
            active = 0
            for info in intervals.values():
                if "start" in info and "end" in info:
                    if info["start"] <= t + 0.0001 and info["end"] > t:
                        active += 1
            max_concurrency = max(max_concurrency, active)
            
        # Assertion: Concurrency should never exceed capacity
        # Note: Due to async/thread timing granularity, 'start_ts' from bleacher 
        # and 'end_ts' from stainer might show slight overlaps that didn't physically exist 
        # in the Allocator's ledger. But it should be close.
        # Ideally it should be exactly 3. 
        assert max_concurrency <= RESOURCE_CAPACITY, f"Max concurrency {max_concurrency} exceeded capacity {RESOURCE_CAPACITY}"
        
        # Sanity check: verify we actually ran stuff in parallel (at least > 1)
        # With 50 tasks and cap 3, we definitely should hit 2 or 3.
        assert max_concurrency > 1, "Tasks ran purely sequentially, which is suspicious."
        
    finally:
        await runner.stop_loop()


@pytest.mark.asyncio
async def test_mixed_resource_wiring():
    # Scenario: 
    # Task A needs GPU. Task B needs CPU.
    # Verify their wiring is distinct.
    
    t_gpu = resource_heavy_task().with_constraints(gpu=1)
    t_cpu = resource_heavy_task().with_constraints(cpu=1)
    
    ir_generator = IRGenerator()
    graph_ir = ir_generator.generate([t_gpu, t_cpu])
    
    env = EnvironmentDef(resources=[
        ResourceDef("gpu", 1),
        ResourceDef("cpu", 1)
    ])
    builder = Builder()
    physical_graph = builder.build(graph_ir, env)
    inspector = GraphInspector(physical_graph)
    
    gpu_alloc = PhysicalIdGenerator.global_allocator("gpu")
    cpu_alloc = PhysicalIdGenerator.global_allocator("cpu")
    
    # GPU Allocator should have 2 resource ports (1 legacy + 1 dynamic for t_gpu)
    inspector.assert_port_count(gpu_alloc, 2, role=PortRole.RESOURCE)
    
    # CPU Allocator should have 2 resource ports (1 legacy + 1 dynamic for t_cpu)
    inspector.assert_port_count(cpu_alloc, 2, role=PortRole.RESOURCE)
    
    # Verify no cross-wiring
    # t_gpu's bleacher should NOT be connected to CPU allocator
    # We need to find t_gpu's node ID. Since it's list input, IDs are generated.
    # IR generator uses hashing.
    node_ids = [n.id for n in graph_ir.nodes]
    # Let's assume index 0 is gpu, 1 is cpu (list order preserved)
    gpu_node_id = node_ids[0]
    
    # Find channels entering GPU Task Bleacher
    gpu_bleacher_id = PhysicalIdGenerator.bleach_node(gpu_node_id)
    in_channels = [c for c in physical_graph.channels if c.target_node_id == gpu_bleacher_id]
    
    # Check sources. One should be from GPU grant chain. None from CPU.
    connected_sources = [c.source_node_id for c in in_channels]
    
    # Trace back from connected sources to see if they come from CPU allocator
    for src in connected_sources:
        # src is likely D_gnt or D_pulse or D_dep
        # If it's D_gnt, it should come from Allocator
        incoming_to_src = [c for c in physical_graph.channels if c.target_node_id == src]
        for c in incoming_to_src:
            assert c.source_node_id != cpu_alloc, "GPU Task illegal connection to CPU Allocator"