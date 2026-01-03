import asyncio
import time
import sys
from typing import Dict

from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode, PhysicsFuncNode, Token
from cascade.spec.ports import PortDef, PortRole
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.executor import PhysicsExecutor

# --- 配置 ---
ITERATIONS = 10000  # 物理跳跃次数。注意：由于 asyncio 调度开销，不建议设置过大（如 100万）

# --- 物理逻辑 ---
# 我们使用一个同步函数来减少额外的 await 开销，直接对比物理层的调度性能
def physical_inc(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    count = inputs["in"].payload
    # 返回到同一个端口，触发下一次循环
    return {"out": Token(payload=count + 1)}

async def run_physical_bench(n: int):
    # 1. 搭建最简闭环拓扑: D_loop -> F_logic -> D_loop
    d_loop = PhysicsDataNode(id="D_loop", name="LoopBuffer", capacity=1)
    f_logic = PhysicsFuncNode(
        id="F_logic",
        name="IncLogic",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)}
    )
    
    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_loop, f_logic]}
    graph.channels.append(Channel("D_loop", "out", "F_logic", "in"))
    graph.channels.append(Channel("F_logic", "out", "D_loop", "in"))
    
    memory = VolatileMemory()
    executor = PhysicsExecutor()
    func_map = {"F_logic": physical_inc}
    reactor = Reactor(graph, memory, executor, func_map)
    
    # 2. 注入启动 Token
    memory.put(d_loop, Token(payload=0))
    
    print(f"开始物理层 TCO 测速 (迭代次数: {n})...")
    start_time = time.perf_counter()
    
    # 3. 运行驱动循环
    # 在这个测试中，我们直接在主循环里驱动 Reactor。
    # 每次 count 达到 n 时停止。
    current_count = 0
    while current_count < n:
        # 扫描并激发
        await reactor.step()
        
        # 等待当前任务完成（由于 Reactor 是异步调度的）
        while reactor.active_task_count > 0:
            await asyncio.sleep(0) # 让出控制权给执行任务
        
        # 检查进度（从内存中偷看一眼，不消耗 Token）
        current_count = memory._buffers["D_loop"][0].payload
        
    end_time = time.perf_counter()
    duration = end_time - start_time
    ops = n / duration
    
    print(f"物理层耗时: {duration:.4f}s")
    print(f"物理层吞吐量: {ops:.2f} hops/sec")
    return duration

def run_native_bench(n: int):
    print(f"\n开始原生 Python while 循环测速 (迭代次数: {n})...")
    count = 0
    start_time = time.perf_counter()
    while count < n:
        count += 1
    end_time = time.perf_counter()
    duration = end_time - start_time
    ops = n / duration
    print(f"原生耗时: {duration:.4f}s")
    print(f"原生吞吐量: {ops:.2f} ops/sec")
    return duration

async def main():
    p_time = await run_physical_bench(ITERATIONS)
    n_time = run_native_bench(ITERATIONS)
    
    ratio = p_time / n_time
    print(f"\n--- 结论 ---")
    print(f"物理层比原生慢了约 {ratio:.1f} 倍")
    print(f"这就是我们未来要通过 '算子融合 (Macro-node Fusion)' 消除的抽象税。")

if __name__ == "__main__":
    asyncio.run(main())