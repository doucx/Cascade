from __future__ import annotations

import asyncio
import time
from typing import Callable

from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode, Token
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor


# --- Kernel ICs ---
def tco_func(inputs, node, resources):
    in_token = inputs["in"]
    return {"out": Token(payload=in_token.payload, trace=in_token.trace)}


# --- Test Setups ---
def setup_physical_tco() -> BipartiteGraph:
    d1 = PhysicsDataNode(id="D1", name="Slot1")
    f1 = PhysicsFuncNode(
        id="F1",
        name="Func1",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )
    graph = BipartiteGraph()
    graph.nodes = {d1.id: d1, f1.id: f1}
    graph.channels.append(Channel(f1.id, "out", d1.id, "in"))
    return graph


# --- Runners ---
def run_sync_while(iterations: int) -> float:
    start_time = time.perf_counter()
    i = 0
    while i < iterations:
        i += 1
    return time.perf_counter() - start_time


async def run_async_no_yield(iterations: int) -> float:
    start_time = time.perf_counter()
    for _ in range(iterations):
        pass
    return time.perf_counter() - start_time


async def run_async_yielding(iterations: int) -> float:
    start_time = time.perf_counter()
    for _ in range(iterations):
        await asyncio.sleep(0)
    return time.perf_counter() - start_time


def run_physical_tco_sync(
    iterations: int, graph: BipartiteGraph, function_map: dict[str, Callable]
):
    memory = VolatileMemory()
    reactor = Reactor(graph, memory, function_map)
    memory.put(graph.nodes["D1"], Token(payload=1))

    start_time = time.perf_counter()
    for _ in range(iterations):
        reactor.step()
    duration = time.perf_counter() - start_time
    return duration


def main():
    iterations = 10_000
    print(f"\n--- Cascade 性能多维基准测试 (迭代: {iterations}) ---")
    try:
        import sys

        py_version = ".".join(map(str, sys.version_info[:3]))
        print(f"Python 版本: {py_version}")
    except Exception:
        pass
    print("------------------------------------------------------------")

    # 1. Ground Truth (Sync)
    duration_sync = run_sync_while(iterations)
    ops_sync = iterations / duration_sync
    print(
        f"1. Sync While         : {duration_sync:.6f}s | {ops_sync:12,.0f} ops/s (基准)"
    )

    # 2. Async (No Yield)
    duration_async_noyield = asyncio.run(run_async_no_yield(iterations))
    ops_async_noyield = iterations / duration_async_noyield
    overhead_noyield = ops_sync / ops_async_noyield
    print(
        f"2. Async (No Yield)   : {duration_async_noyield:.6f}s | {ops_async_noyield:12,.0f} ops/s (开销: {overhead_noyield:.1f}x)"
    )

    # 3. Async (Yielding)
    duration_async_yield = asyncio.run(run_async_yielding(iterations))
    ops_async_yield = iterations / duration_async_yield
    overhead_yield = ops_sync / ops_async_yield
    print(
        f"3. Async (Yielding)   : {duration_async_yield:.6f}s | {ops_async_yield:12,.0f} ops/s (开销: {overhead_yield:.1f}x)"
    )

    # 4. Physical TCO (The new sync version)
    graph = setup_physical_tco()
    func_map = {"F1": tco_func}
    duration_physical = run_physical_tco_sync(iterations, graph, func_map)
    ops_physical = iterations / duration_physical
    overhead_physical = ops_sync / ops_physical
    step_latency_us = (duration_physical / iterations) * 1_000_000
    print(
        f"4. Sync Kernel TCO    : {duration_physical:.6f}s | {ops_physical:12,.0f} ops/s (开销: {overhead_physical:.1f}x)"
    )

    print("------------------------------------------------------------")
    net_tax = ops_async_yield / ops_physical
    print(f"结论: 物理引擎相对于纯 Async(Yielding) 的净税收为: {net_tax:.2f}x")
    print(f"物理层单步延迟 (Step Latency): {step_latency_us:.2f} μs")


if __name__ == "__main__":
    main()
