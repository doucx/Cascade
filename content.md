好的，我们正式开始执行奇点内核重构的 **阶段 3：终极验证与基准测试**。

第一项任务是重构基准测试脚本 `scripts/benchmark_vm_tco.py`，以准确测量我们全新的、绝对同步的 `Reactor` 内核的性能。旧的脚本是为异步 `Reactor` 设计的，现在必须进行调整。

我将生成一个计划来移除所有异步相关的代码，并将其转换为一个纯粹的同步测试。

## [WIP] refactor: 重构基准测试以反映同步内核

### 用户需求

根据“奇点内核重构”项目计划，执行任务 3.1：重构 `scripts/benchmark_vm_tco.py` 文件，使其适应并能准确测量新的同步 `Reactor` 的性能。

### 评论

这是验证我们架构重构是否成功的关键一步。通过这次重构，基准测试将能够直接测量物理内核的原始“步进”性能，不受任何 `asyncio` 事件循环开销的干扰。我们期望看到性能达到百万操作每秒（Mops/s）级别，这将是新架构压倒性优势的直接证明。

### 目标

1.  定位 `scripts/benchmark_vm_tco.py` 中的 `run_physical_tco_sync` 函数和 `main` 函数。
2.  将 `run_physical_tco_sync` 从 `async def` 修改为 `def`，并移除其内部对 `reactor.step()` 的 `await` 调用。
3.  同步修改 `main` 函数，移除其 `async` 定义和对 `asyncio.run()` 的依赖，以直接调用新的同步测试函数。

### 基本原理

由于 `Reactor.step()` 方法已经从一个协程 (`async def`) 被重构为一个常规的同步方法 (`def`)，任何调用它的代码都必须相应地更新。基准测试脚本作为性能的“黄金标准”，必须首先被修正，以消除异步开销，确保我们测量的是纯粹的、无干扰的内核计算性能。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #concept/state #task/domain/testing #task/object/benchmark #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修改基准测试脚本

我们将一次性更新 `scripts/benchmark_vm_tco.py`，移除所有不必要的异步操作，使其完全同步。

~~~~~act
write_file
scripts/benchmark_vm_tco.py
~~~~~
~~~~~python
import time
import asyncio
from typing import Dict, Callable

from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode, Token
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.topology import Channel
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory


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


def run_physical_tco_sync(iterations: int, graph: BipartiteGraph, function_map: Dict[str, Callable]):
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
~~~~~

### 下一步建议

基准测试脚本已经更新。下一步是运行它，以验证新架构的性能是否达到预期。

我建议你现在就运行这个脚本：`python scripts/benchmark_vm_tco.py`，并将结果与项目文档中的预期（百万操作每秒级别）进行比较。

如果性能达标，我们就可以继续 **任务 3.2**：编写一个“跨界”集成测试，以验证物理内核和异步计算服务之间的端到端通信。
