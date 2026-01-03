好的，这个分析更有意义。我们需要区分 **“语言开销”**、**“异步运行时开销”** 和 **“物理引擎抽象开销”**。

## [WIP] 我已经更新了 `scripts/benchmark_vm_tco.py`，现在包含四个维度的对比：
1.  **Sync While**: 纯 Python 速度。
2.  **Async While (No Yield)**: 在 `async` 函数里跑循环但不挂起（测量 async 函数调用的极微小开销）。
3.  **Async While (Yielding)**: 每次循环执行 `await asyncio.sleep(0)`（测量 **asyncio 事件循环单次调度**的基准开销）。
4.  **Physical TCO**: Cascade Reactor 驱动的物理场循环（测量 **Cascade 引擎逻辑**在 asyncio 之上的净开销）。

~~~~~act
write_file
scripts/benchmark_vm_tco.py
~~~~~
~~~~~python
import asyncio
import time
import sys
import os

# 确保可以导入本地 package
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "packages", "cascade-spec", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "packages", "cascade-vm", "src"))

from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode, PhysicsFuncNode, Token
from cascade.spec.ports import PortDef, PortRole
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.executor import PhysicsExecutor

# --- 基准测试目标 ---

def sync_while_baseline(iterations: int):
    count = 0
    start_time = time.perf_counter()
    while count < iterations:
        count += 1
    duration = time.perf_counter() - start_time
    return duration

async def async_while_no_yield(iterations: int):
    count = 0
    start_time = time.perf_counter()
    while count < iterations:
        count += 1
    duration = time.perf_counter() - start_time
    return duration

async def async_while_yielding(iterations: int):
    count = 0
    start_time = time.perf_counter()
    while count < iterations:
        count += 1
        await asyncio.sleep(0) # 强制让出控制权，模拟一次完整的事件循环调度
    duration = time.perf_counter() - start_time
    return duration

async def async_increment(inputs, node, resources):
    val = inputs["in"].payload
    return {"out": Token(payload=val + 1)}

async def run_physical_tco(iterations: int):
    d_state = PhysicsDataNode(id="D_state", name="StateSlot", capacity=1)
    f_inc = PhysicsFuncNode(
        id="F_inc",
        name="Incremetor",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)}
    )
    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_state, f_inc]}
    graph.channels.append(Channel("D_state", "out", "F_inc", "in"))
    graph.channels.append(Channel("F_inc", "out", "D_state", "in"))
    
    memory = VolatileMemory()
    executor = PhysicsExecutor()
    func_map = {"F_inc": async_increment}
    reactor = Reactor(graph, memory, executor, func_map)
    
    memory.put(d_state, Token(payload=0))
    
    start_time = time.perf_counter()
    for _ in range(iterations):
        await reactor.step()
        # 等待任务在后台执行完成并回流 Token
        # 物理场中这是必须的，因为 Reactor 使用 create_task 异步发射
        while reactor.active_task_count > 0:
            await asyncio.sleep(0)
            
    duration = time.perf_counter() - start_time
    
    # 结果校验
    final_val = memory.take("D_state").payload
    assert final_val == iterations
    return duration

# --- 报告生成 ---

async def main():
    ITERATIONS = 10_000
    
    print(f"--- Cascade 性能多维基准测试 (迭代: {ITERATIONS:,.0f}) ---")
    print(f"Python 版本: {sys.version.split()[0]}")
    print("-" * 60)

    # 1. Sync
    d_sync = sync_while_baseline(ITERATIONS)
    print(f"1. Sync While         : {d_sync:.6f}s | {ITERATIONS/d_sync:12,.0f} ops/s (基准)")

    # 2. Async (No Yield)
    d_asy_ny = await async_while_no_yield(ITERATIONS)
    print(f"2. Async (No Yield)   : {d_asy_ny:.6f}s | {ITERATIONS/d_asy_ny:12,.0f} ops/s (开销: {d_asy_ny/d_sync:.1f}x)")

    # 3. Async (Yielding)
    d_asy_y = await async_while_yielding(ITERATIONS)
    print(f"3. Async (Yielding)   : {d_asy_y:.6f}s | {ITERATIONS/d_asy_y:12,.0f} ops/s (开销: {d_asy_y/d_sync:.1f}x)")

    # 4. Physical Field
    d_phys = await run_physical_tco(ITERATIONS)
    print(f"4. Physical TCO       : {d_phys:.6f}s | {ITERATIONS/d_phys:12,.0f} ops/s (开销: {d_phys/d_sync:.1f}x)")

    print("-" * 60)
    print(f"结论: 物理引擎相对于纯 Async(Yielding) 的净税收为: {d_phys/d_asy_y:.2f}x")
    print(f"物理层单步延迟 (Step Latency): {(d_phys/ITERATIONS)*1_000_000:.2f} μs")

if __name__ == "__main__":
    asyncio.run(main())
~~~~~

### 如何分析结果

当你运行这个脚本时，你会看到一个非常清晰的层次感：

1.  **Sync vs Async (No Yield)**: 差距通常微乎其微。这说明 Python 执行 async 函数体本身很快。
2.  **Async (No Yield) vs Async (Yielding)**: 这是一个巨大的断层（通常几十倍到上百倍）。这测量的就是 **asyncio 事件循环的“往返时延”**。每当你 `await` 一个已经就绪的任务（如 `sleep(0)`），事件循环都要进行一次完整的调度。
3.  **Async (Yielding) vs Physical TCO**: 这是我们 **Cascade 物理引擎的真实抽象税**。
    *   如果这个比值在 **2x ~ 5x** 之间：说明我们的引擎逻辑（扫描、取数、放数）已经非常精简了。
    *   如果比值 **> 10x**: 说明 `Reactor` 和 `VolatileMemory` 的逻辑还有很大的优化空间（比如过多的 `asyncio.Event` 设置或 `O(n)` 的扫描）。

**单节点 TCO 的“天花板”**:
在不进行算子融合（JIT）的情况下，物理场 TCO 的理论最高速度永远无法超过 `Async (Yielding)`。

你可以运行一下，看看在你的机器上这个“净税收”是多少。这将是我们未来决定是否需要引入 Rust 核心或 C 扩展的重要参考数据。
