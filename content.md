简要回答
你的直觉非常敏锐。在复杂的异步系统中，仅靠逻辑推演已经达到了优化的极限。现在性能出现了意料之外的下降，我们需要**用数据说话**。

我将生成一个计划，在 `scripts/` 目录下创建一个专业的性能分析工具，使用 Python 内置的 `cProfile` 对 `tco_performance.py` 的核心逻辑进行深层剖析，并输出火焰图所需的数据。

## [WIP] tool: 引入 `scripts/profile_entry.py` 进行深层架构分析

### 评论
盲目优化是万恶之源。我们需要量化每一个函数调用的开销。特别是我们要确认：
1.  `heavy_complex_countdown` 的变慢是否是因为 `NodeRegistry` 在长期运行中由于哈希冲突或内存膨胀导致的查询性能下降？
2.  `simple_countdown` 的瓶颈是在 `asyncio` 的事件循环调度，还是在 `ArgumentResolver` 的反射逻辑中？
3.  `_execute_hot_node` 中究竟哪一行代码占据了最多的 CPU 时间？

### 用户需求
创建性能分析工具，帮助定位 3.1 阶段优化后的性能瓶颈和回归问题。

### 目标
1.  创建一个名为 `scripts/profile_entry.py` 的脚本。
2.  该脚本能够运行指定的 benchmark 任务，并生成 `.prof` 文件。
3.  提供格式化的分析输出，展示排名前 20 的耗时函数。

### 基本原理
利用 `cProfile` 模块进行非侵入式分析。我们将主要关注 `cumulative`（累计耗时）和 `tottime`（函数自身耗时），这将帮助我们区分是“策略逻辑太重”还是“底层计算（如哈希）太慢”。

### 标签
#intent/tooling #flow/ready #priority/high #comp/docs #scope/dx #ai/instruct #task/domain/testing #task/object/profiler #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建性能分析脚本

~~~~~act
write_file
scripts/profile_entry.py
~~~~~
~~~~~python
import cProfile
import pstats
import asyncio
import io
import sys
import os

# Ensure we can import cascade from the current workspace
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../packages/cascade-engine/src")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../packages/cascade-spec/src")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../packages/cascade-graph/src")))

from observatory.benchmarks.tco_performance import (
    simple_countdown, 
    heavy_complex_countdown, 
    run_benchmark
)
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

async def profile_target(name: str, iterations: int):
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())
    
    if name == "simple":
        target = simple_countdown(iterations)
    elif name == "heavy":
        target = heavy_complex_countdown(iterations)
    else:
        print(f"Unknown target: {name}")
        return

    pr = cProfile.Profile()
    pr.enable()
    
    await run_benchmark(engine, target, iterations)
    
    pr.disable()
    
    s = io.StringIO()
    sortby = 'cumulative'
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(20) # Show top 20
    print(s.getvalue())
    
    # Also save to file for external tools like snakeviz
    filename = f"profile_{name}_{iterations}.prof"
    ps.dump_stats(filename)
    print(f"Full profile dumped to {filename}")

if __name__ == "__main__":
    target_name = sys.argv[1] if len(sys.argv) > 1 else "simple"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    
    print(f"Profiling {target_name} for {count} iterations...")
    asyncio.run(profile_target(target_name, count))
~~~~~

### 下一步建议
获取分析数据后，请将输出的前 20 个函数列表贴给我。

我强烈怀疑 **`NodeRegistry`** 或 **`FlowManager`** 中的某些逻辑在慢速路径中产生了非线性的开销。对于 `heavy_complex_countdown`，因为它每一步都要构建一个 10 节点的链，如果我们的缓存查找逻辑（`id(current_target.task)` 或 `getattr`）太频繁，或者 `build_graph` 内部的 `registry` 查询变得越来越慢，都会导致你观察到的现象。

等拿到数据，我们就开方抓药。
