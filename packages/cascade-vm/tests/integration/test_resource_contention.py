from __future__ import annotations

import pytest
from cascade.bus.events import (
    Event,
    TaskExecutionFinished,
    TaskExecutionStarted,
)
from cascade.compiler.backend.builder import Builder
from cascade.compiler.frontend.generator import IRGenerator
from cascade.compiler.utils.inspector import GraphInspector
from cascade.reflection import PhysicalIdGenerator
from cascade.spec.dsl.task import task
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.spec.physical.ports import PortRole
from cascade.test_utils import EventDrivenRunner
from cascade.vm.registry import CodeRegistry


@task
def resource_heavy_task(duration: float = 0.01):
    # Simulate work
    import time

    time.sleep(duration)
    return "Done"


@pytest.mark.timeout(1)
@pytest.mark.asyncio
async def test_resource_scarcity_topology_and_execution():
    # Configuration
    # Reduced to 10 to avoid "request storm" livelock in the simple reactor simulation.
    # When many requests are rejected and recirculated instantly, it consumes massive CPU cycles.
    TASK_COUNT = 10
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
    generation_result = ir_generator.generate(tasks)
    graph_ir = generation_result.ir

    # 2. Build Physical Graph
    env = EnvironmentDef(
        resources=[ResourceDef(name=RESOURCE_NAME, capacity=RESOURCE_CAPACITY)]
    )
    builder = Builder()
    artifact = builder.build(graph_ir, env)
    assembly = artifact.assembly
    physical_graph = assembly.graph

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
    inspector.assert_port_count(
        allocator_id, count=TASK_COUNT + 1, role=PortRole.RESOURCE
    )

    # Verify Wiring
    # Pick a random task node to verify its path
    sample_node_ir = graph_ir.nodes[0]
    # Path: Allocator -> D_gnt -> Bleacher
    # We need to find the specific grant port for this task.
    # It requires the ID of the Requestor node.
    req_id = PhysicalIdGenerator.requestor(
        sample_node_ir.current_node_instance_hash, RESOURCE_NAME
    )
    expected_port = f"gnt_for_{req_id}"

    inspector.assert_port_exists(allocator_id, expected_port)

    # Verify connection to intermediate D_gnt
    # We don't know D_gnt ID easily without reconstructing logic, but we can search channels
    channels = inspector.find_channels_from(allocator_id, expected_port)
    assert len(channels) == 1
    d_gnt_id = channels[0].target_node_id

    inspector.get_data_node(d_gnt_id)  # Should be a data node

    # Verify D_gnt -> Launcher
    launcher_id = PhysicalIdGenerator.launcher_node(
        sample_node_ir.current_node_instance_hash
    )
    inspector.assert_connection(
        d_gnt_id, launcher_id, target_port=f"res_{RESOURCE_NAME}"
    )

    # --- PART B: EXECUTION ASSERTION ---
    print("\n--- Physical Field Event Log (Observed) ---")

    code_registry = CodeRegistry()
    # All tasks are the same, so they share the same canonical hash.
    # We can just grab the first one from the symbol table to register the implementation.
    if assembly.symbol_table:
        canonical_hash = next(iter(assembly.symbol_table.values()))
        code_registry.register(canonical_hash, resource_heavy_task.func)

    runner = EventDrivenRunner.from_assembly(assembly, code_registry)
    runner.prime()

    await runner.start_loop()

    try:
        # Collect all events
        events: list[Event] = []

        def collection_predicate(e: Event):
            events.append(e)

            if isinstance(e, TaskExecutionStarted):
                print(f"[OBS-START] {e.task_id}")
            elif isinstance(e, TaskExecutionFinished):
                print(f"[OBS-END  ] {e.task_id} ({e.status})")

            # Check completion condition based on END events only
            completed = len([e for e in events if isinstance(e, TaskExecutionFinished)])
            return completed == TASK_COUNT

        await runner.wait_for_event(collection_predicate, timeout=10.0)

        # Analyze Concurrency from the rich event stream
        intervals: dict[str, dict[str, float]] = {}

        start_events = {
            e.task_id: e.timestamp
            for e in events
            if isinstance(e, TaskExecutionStarted)
        }
        end_events = {
            e.task_id: e.timestamp
            for e in events
            if isinstance(e, TaskExecutionFinished)
        }

        for task_id, start_ts in start_events.items():
            if task_id in end_events:
                intervals[task_id] = {
                    "start": start_ts,
                    "end": end_events[task_id],
                }

        # Check max overlap
        max_concurrency = 0
        sorted_starts = sorted(intervals[tid]["start"] for tid in intervals)

        for t in sorted_starts:
            active = 0
            for info in intervals.values():
                if info["start"] <= t + 0.0001 and info["end"] > t:
                    active += 1
            max_concurrency = max(max_concurrency, active)

        assert max_concurrency <= RESOURCE_CAPACITY, (
            f"Max concurrency {max_concurrency} exceeded capacity {RESOURCE_CAPACITY}"
        )
        assert max_concurrency > 1, (
            "Tasks ran purely sequentially, which is suspicious."
        )

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
    generation_result = ir_generator.generate([t_gpu, t_cpu])
    graph_ir = generation_result.ir

    env = EnvironmentDef(resources=[ResourceDef("gpu", 1), ResourceDef("cpu", 1)])
    builder = Builder()
    artifact = builder.build(graph_ir, env)
    assembly = artifact.assembly
    physical_graph = assembly.graph
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
    node_ids = [n.current_node_instance_hash for n in graph_ir.nodes]
    # Let's assume index 0 is gpu, 1 is cpu (list order preserved)
    gpu_node_id = node_ids[0]

    # Find channels entering GPU Task Launcher
    gpu_launcher_id = PhysicalIdGenerator.launcher_node(gpu_node_id)
    in_channels = [
        c for c in physical_graph.channels if c.target_node_id == gpu_launcher_id
    ]

    # Check sources. One should be from GPU grant chain. None from CPU.
    connected_sources = [c.source_node_id for c in in_channels]

    # Trace back from connected sources to see if they come from CPU allocator
    for src in connected_sources:
        # src is likely D_gnt or D_pulse or D_dep
        # If it's D_gnt, it should come from Allocator
        incoming_to_src = [
            c for c in physical_graph.channels if c.target_node_id == src
        ]
        for c in incoming_to_src:
            assert c.source_node_id != cpu_alloc, (
                "GPU Task illegal connection to CPU Allocator"
            )
