import asyncio
import time
import sys
import os

# 确保可以导入本地 package
sys.path.append(
    os.path.join(os.path.dirname(__file__), "..", "packages", "cascade-spec", "src")
)
sys.path.append(
    os.path.join(os.path.dirname(__file__), "..", "packages", "cascade-vm", "src")
)

from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode, Token
from cascade.spec.physical.ports import PortDef, PortRole
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
        await asyncio.sleep(0)  # 强制让出控制权，模拟一次完整的事件循环调度
    duration = time.perf_counter() - start_time
    return duration


# --- 新增：纯同步的内核函数 (模拟 std IC) ---
def sync_increment(inputs, node, resources):
    val = inputs["in"].payload
    return {"out": Token(payload=val + 1)}


# --- 异步工作单元 (模拟用户 task) ---
async def async_increment(inputs, node, resources):
    val = inputs["in"].payload
    # 模拟异步 IO 操作
    await asyncio.sleep(0)
    return {"out": Token(payload=val + 1)}


async def run_physical_tco_async(iterations: int):
    d_state = PhysicsDataNode(id="D_state", name="StateSlot", capacity=1)
    f_inc = PhysicsFuncNode(
        id="F_inc",
        name="Incremetor",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
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


# --- 新增：纯同步的物理场测试 ---
async def run_physical_tco_sync(iterations: int):
    d_state = PhysicsDataNode(id="D_state", name="StateSlot", capacity=1)
    f_inc = PhysicsFuncNode(
        id="F_inc",
        name="Incremetor",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )
    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_state, f_inc]}
    graph.channels.append(Channel("D_state", "out", "F_inc", "in"))
    graph.channels.append(Channel("F_inc", "out", "D_state", "in"))

    memory = VolatileMemory()
    executor = PhysicsExecutor()
    func_map = {"F_inc": sync_increment} # <--- 使用同步函数
    reactor = Reactor(graph, memory, executor, func_map)

    memory.put(d_state, Token(payload=0))

    start_time = time.perf_counter()
    for _ in range(iterations):
        await reactor.step()
        # 即使是同步函数，Reactor 仍然调度一个包装器 Task，所以需要等待它完成
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
    print(
        f"1. Sync While         : {d_sync:.6f}s | {ITERATIONS / d_sync:12,.0f} ops/s (基准)"
    )

    # 2. Async (No Yield)
    d_asy_ny = await async_while_no_yield(ITERATIONS)
    print(
        f"2. Async (No Yield)   : {d_asy_ny:.6f}s | {ITERATIONS / d_asy_ny:12,.0f} ops/s (开销: {d_asy_ny / d_sync:.1f}x)"
    )

    # 3. Async (Yielding)
    d_asy_y = await async_while_yielding(ITERATIONS)
    print(
        f"3. Async (Yielding)   : {d_asy_y:.6f}s | {ITERATIONS / d_asy_y:12,.0f} ops/s (开销: {d_asy_y / d_sync:.1f}x)"
    )

    # 4. Physical Field (Async Worker)
    d_phys_async = await run_physical_tco_async(ITERATIONS)
    print(
        f"4. Async Worker TCO   : {d_phys_async:.6f}s | {ITERATIONS / d_phys_async:12,.0f} ops/s (开销: {d_phys_async / d_sync:.1f}x)"
    )
    
    # 5. Physical Field (Sync Kernel)
    d_phys_sync = await run_physical_tco_sync(ITERATIONS)
    print(
        f"5. Sync Kernel TCO    : {d_phys_sync:.6f}s | {ITERATIONS / d_phys_sync:12,.0f} ops/s (开销: {d_phys_sync / d_sync:.1f}x)"
    )

    print("-" * 60)
    print(f"结论: 异步 Worker 净税收 (vs Async Yielding): {d_phys_async / d_asy_y:.2f}x")
    print(f"结论: 同步 Kernel 净税收 (vs Async Yielding): {d_phys_sync / d_asy_y:.2f}x")
    print(f"同步内核单步延迟 (Step Latency): {(d_phys_sync / ITERATIONS) * 1_000_000:.2f} μs")


if __name__ == "__main__":
    asyncio.run(main())
