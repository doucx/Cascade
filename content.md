简要回答：
分析表明脚本存在三个问题：
1.  **内存监测失效**：由于环境中未安装 `psutil`，脚本回退到了返回 `0.0` 的空函数。
2.  **“静默”运行**：手动实例化的 `MessageBus` 没有挂载任何日志订阅者（Subscriber），因此你看不到任何任务启动或完成的日志，无法判断 Agent 是否存活。
3.  **并发过载**：同时启动 10,000 个 Agent 会瞬间产生巨大的 CPU 负载（用于图构建和任务调度），导致事件循环响应极慢，看起来像卡死。

**修正方案**：
1.  **增强内存读取**：添加读取 `/proc/self/status` 作为 Linux 环境下的无依赖回退方案，确保能读到内存数据。
2.  **增加可观测性**：手动挂载 `HumanReadableLogSubscriber`，并将日志级别设为 `WARNING`（避免刷屏但能看到错误）或抽样打印进度。
3.  **降低并发规模**：将 Agent 数量暂时调整为 **1,000**，以确保测试能在合理时间内完成并验证 TCO 机制。1,000 个长生不死的 Agent 足以暴露内存泄漏问题。

摘要头：
## [WIP] fix: Enhance observability and reduce scale in recursion test

### 标签
#intent/fix #flow/ready #priority/high
#comp/observatory #concept/memory #scope/core
#ai/instruct
#task/domain/physics
#task/object/recursion-tco
#task/action/bug-fix
#task/state/continue

### 用户需求
1.  **修复内存监控**：在没有 `psutil` 的情况下也能获取内存数据。
2.  **确认 Agent 状态**：通过日志输出证明 Agent 确实在递归运行。
3.  **防止卡死**：调整测试参数以适应单线程 Python 的调度能力。

### 目标
修改 `recursion_test.py`，实现 Linux 原生内存读取，添加日志订阅者，并将并发数降至 1,000。

### 基本原理
*   **/proc/self/status**: Linux 内核提供的进程状态文件，其中 `VmRSS` 字段即为物理内存占用。
*   **采样日志**: 我们不需要打印 1,000 个 Agent 的每一代日志，只需打印其中一个 Agent 的状态即可证明系统在运行。

---

### Script

#### Acts 1: 增强 `recursion_test.py`

~~~~~act
write_file
observatory/protoplasm/physics/recursion_test.py
~~~~~
~~~~~python
import asyncio
import time
import os
import re
import random
from typing import Optional

import cascade as cs
from cascade.runtime.subscribers import HumanReadableLogSubscriber
from cascade.common.messaging import bus as global_bus
from cascade.common.renderers import CliRenderer

# --- Memory Monitoring Utils ---

def get_memory_mb():
    """
    Tries to get memory usage via psutil, then /proc/self/status (Linux),
    then returns 0.0 if all fail.
    """
    # 1. Try psutil
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        pass

    # 2. Try reading /proc/self/status (Linux specific)
    try:
        with open("/proc/self/status", "r") as f:
            content = f.read()
            # Look for "VmRSS:    1234 kB"
            match = re.search(r"VmRSS:\s+(\d+)\s+kB", content)
            if match:
                return float(match.group(1)) / 1024.0
    except FileNotFoundError:
        pass

    print("⚠️  Warning: Cannot determine memory usage (psutil missing & not on Linux?)")
    return 0.0

# --- Configuration ---
NUM_AGENTS = 1000      # Reduced from 10,000 to ensure responsiveness
NUM_GENERATIONS = 1000 # Total generations to simulate
REPORT_INTERVAL = 2    # Monitor interval in seconds

# --- The Recursive Agent ---

def controlled_agent(agent_id: int, gen: int, limit: int):
    """
    A recursive agent that stops after `limit` generations.
    """
    # We use a task for the step to involve the Engine's scheduling machinery
    @cs.task(name=f"step")
    def step(v): 
        return v + 1
    
    next_v = step(gen)
    
    # We use a task for the check/recursion to test TCO
    @cs.task(name=f"loop")
    def loop(v):
        if v >= limit:
            return v
        return controlled_agent(agent_id, v, limit)
        
    return loop(next_v)

# --- Experiment Orchestrator ---

async def run_recursion_experiment():
    print(f"🚀 Starting Recursion & Memory Experiment...")
    print(f"   - Agents: {NUM_AGENTS}")
    print(f"   - Target Generations: {NUM_GENERATIONS}")
    
    initial_mem = get_memory_mb()
    print(f"Initial Memory Usage: {initial_mem:.2f} MB")

    # 1. Setup Engine with Visibility
    # We attach a subscriber to the bus so we can see if things go wrong.
    # But we set min_level="WARNING" to avoid flooding stdout with 1000 agents' info.
    
    # Configure global renderer for the bus (used by subscribers)
    global_bus.set_renderer(CliRenderer(store=global_bus.store, min_level="WARNING"))
    
    engine_bus = cs.MessageBus()
    # Attach subscriber to the engine's bus
    HumanReadableLogSubscriber(engine_bus)
    
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=engine_bus
    )

    print(f"Starting {NUM_AGENTS} agents...")
    start_time = time.perf_counter()
    
    # 2. Launch Agents
    # We stagger the start slightly to avoid thundering herd on graph build
    tasks = []
    for i in range(NUM_AGENTS):
        tasks.append(engine.run(controlled_agent(i, 0, NUM_GENERATIONS)))
        if i % 100 == 0:
            await asyncio.sleep(0) # Yield to event loop
    
    print(f"All agents scheduled. Monitoring...")

    # 3. Monitor memory in a background loop
    async def monitor_mem():
        max_mem = initial_mem
        while True:
            await asyncio.sleep(REPORT_INTERVAL)
            mem = get_memory_mb()
            max_mem = max(max_mem, mem)
            print(f"   [Monitor] Memory: {mem:.2f} MB (Delta: {mem - initial_mem:+.2f} MB) | Max Delta: {max_mem - initial_mem:+.2f} MB")

    monitor_task = asyncio.create_task(monitor_mem())

    try:
        # Wait for all agents to finish
        results = await asyncio.gather(*tasks)
        print(f"\n✅ Successfully reached {NUM_GENERATIONS} generations for all {NUM_AGENTS} agents.")
    except Exception as e:
        print(f"\n❌ Experiment failed with error: {e}")
        raise
    finally:
        monitor_task.cancel()

    end_time = time.perf_counter()
    final_mem = get_memory_mb()
    
    print("\n--- Recursion Stability Report ---")
    print(f"Total Time:      {end_time - start_time:.2f} s")
    print(f"Total Recursions: {NUM_AGENTS * NUM_GENERATIONS:,.0f}")
    print(f"Initial Memory:   {initial_mem:.2f} MB")
    print(f"Final Memory:     {final_mem:.2f} MB")
    print(f"Net Leak:         {final_mem - initial_mem:+.2f} MB")
    print("----------------------------------")
    
    # Check for leaks
    # Allow some overhead for python objects, but it shouldn't be massive
    if (final_mem - initial_mem) > 50: 
        print("⚠️  POTENTIAL LEAK: Memory increased significantly (>50MB).")
    else:
        print("✅  STABLE: Memory usage remained within reasonable bounds.")

if __name__ == "__main__":
    asyncio.run(run_recursion_experiment())
~~~~~

### 下一步建议
运行修正后的测试：
`python -m observatory.protoplasm.physics.recursion_test`

这次你应该能看到：
1.  **有效的内存读数**（基于 Linux `/proc`）。
2.  **定期的监控日志**。
3.  **最终的成功报告**。

如果脚本成功运行且 Net Leak 较小（例如 < 20MB），则证明 TCO 机制有效且无明显内存泄漏。如果内存持续上涨，我们将需要检查 `Engine` 对历史 `LazyResult` 的引用处理。
