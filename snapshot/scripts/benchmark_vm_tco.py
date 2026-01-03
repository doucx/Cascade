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

# --- 被测物理函数 ---

async def async_increment(inputs, node, resources):
    """
    极简异步函数：读取 payload，加 1，回传。
    """
    val = inputs["in"].payload
    return {"out": Token(payload=val + 1)}

# --- 基准测试工具 ---

async def run_while_baseline(iterations: int):
    """
    原生 Python while 循环基准。
    """
    count = 0
    start_time = time.perf_counter()
    while count < iterations:
        count += 1
    end_time = time.perf_counter()
    
    duration = end_time - start_time
    ops_per_sec = iterations / duration
    return duration, ops_per_sec

async def run_physical_tco_benchmark(iterations: int):
    """
    物理场 TCO 基准：D_state -> F_inc -> D_state
    """
    # 1. 手工搭建物理场
    d_state = PhysicsDataNode(id="D_state", name="StateSlot", capacity=1)
    f_inc = PhysicsFuncNode(
        id="F_inc",
        name="Incremetor",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)}
    )
    
    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_state, f_inc]}
    
    # 闭环布线 (TCO)
    graph.channels.append(Channel("D_state", "out", "F_inc", "in"))
    graph.channels.append(Channel("F_inc", "out", "D_state", "in"))
    
    memory = VolatileMemory()
    executor = PhysicsExecutor() # 虽然我们用异步函数，但 Reactor 仍需要 executor 实例
    func_map = {"F_inc": async_increment}
    
    reactor = Reactor(graph, memory, executor, func_map)
    
    # 2. 注入初始能量
    memory.put(d_state, Token(payload=0))
    
    # 3. 运行循环
    start_time = time.perf_counter()
    
    # 物理层迭代：每次 step 会触发一次 F_inc
    for _ in range(iterations):
        # 触发扫描与调度
        await reactor.step()
        
        # 由于 Reactor.step() 内部使用 create_task，我们需要等待任务完成
        # 这种等待模拟了物理场中“能量坍缩-激发”的真实时延
        while reactor.active_task_count > 0:
            await asyncio.sleep(0) # 让出控制权给调度后的任务
            
    end_time = time.perf_counter()
    
    # 验证结果
    final_val = memory.take("D_state").payload
    assert final_val == iterations, f"Expected {iterations}, got {final_val}"
    
    duration = end_time - start_time
    ops_per_sec = iterations / duration
    return duration, ops_per_sec

async def main():
    ITERATIONS = 10_000 # 物理场开销较大，先测 1万次
    
    print(f"--- Cascade VM 物理层 TCO 测速 (迭代次数: {ITERATIONS}) ---")
    print("环境: 纯异步函数 (无线程池切换)")
    print("-" * 50)
    
    # Baseline
    print("正在执行 Python While 循环基准...")
    b_dur, b_ops = await run_while_baseline(ITERATIONS)
    print(f"While 结果: {b_dur:.4f}s | 吞吐量: {b_ops:,.0f} ops/sec")
    
    print("-" * 50)
    
    # Physical
    print("正在执行 Physical Field TCO 基准...")
    p_dur, p_ops = await run_physical_tco_benchmark(ITERATIONS)
    print(f"Physical 结果: {p_dur:.4f}s | 吞吐量: {p_ops:,.0f} ops/sec")
    
    print("-" * 50)
    
    ratio = p_dur / b_dur
    print(f"物理层抽象税 (Overhead Ratio): {ratio:.1f}x")
    print(f"单次激发平均耗时: {(p_dur/ITERATIONS)*1_000_000:.2f} μs")

if __name__ == "__main__":
    asyncio.run(main())