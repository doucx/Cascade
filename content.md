您是对的，感谢您的指正。我的上一个计划违反了该脚本“自包含”的原则，不应该为了分析工具而去修改被分析的代码。这是一个重要的疏忽。

我将遵循您的指示：**允许冗余**，并将所有必要的依赖项直接复制到 `profile_entry.py` 中，以保持其独立性。

这是修正后的计划。

## [WIP] perf(engine): 添加 stable TCO 剖析器以诊断性能回归 (v2)

### 错误分析
在对 `StateBackend` 进行异步化重构并修复 `InMemoryStateBackend` 的性能后，`stable_complex_loop` 基准测试仍然显示出约 25% 的性能回归。初步分析表明，这可能是由于在 TCO 的 JIT 缓存路径中引入了高频的 `await` 调用所带来的累积开销。

### 用户需求
修改性能剖析脚本 `scripts/profile_entry.py`，使其支持对 `stable_complex_loop` 基准测试进行剖析，同时**保持脚本的自包含性**，不修改基准测试文件本身。

### 评论
这是一个教科书式的性能调优案例。我们已经有了一个明确的假设（“异步税”），现在需要通过精确的测量工具（cProfile）来验证它。根据用户指示，我们将通过在剖析脚本中复制必要的依赖项来保持其独立性，这是一个正确的工具设计原则。

### 目标
1.  修改 `scripts/profile_entry.py`，导入 `stable_complex_loop` 和 `noop` 任务。
2.  在 `scripts/profile_entry.py` 内部**复制**用于创建复杂依赖链 `static_dep_chain` 的逻辑。
3.  添加一个新的 `stable` 目标，该目标可以正确设置并运行 `stable_complex_loop` 基准测试。

### 基本原理
通过 `cProfile`，我们可以获得 `stable_complex_loop` 在 TCO 循环中每个函数调用的精确耗时和调用次数。这将使我们能够量化 `await flow_manager.should_skip` 和 `await arg_resolver.resolve` 等新异步调用所带来的开销，从而验证我们的性能回归假设。

### 标签
#intent/tooling #intent/fix #flow/ready #priority/critical #comp/engine #scope/dx #ai/instruct #task/domain/core #task/object/performance #task/action/analysis #task/state/continue

---

### Script

#### Acts 1: 更新性能剖析脚本

我们将重写 `profile_entry.py`，使其能够独立运行 `stable` 场景的剖析。

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
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../packages/cascade-engine/src")
    )
)
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../packages/cascade-spec/src")
    )
)
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../packages/cascade-graph/src")
    )
)

from observatory.benchmarks.tco_performance import (
    simple_countdown,
    heavy_complex_countdown,
    stable_complex_loop,
    noop,
    run_benchmark,
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
    elif name == "stable":
        # Recreate the dependency chain locally to keep the script self-contained
        # for this specific test case, as per user instruction. Redundancy is fine.
        static_dep_chain = noop()
        for _ in range(10):
            static_dep_chain = noop(_dummy=static_dep_chain)
        target = stable_complex_loop([iterations], _dummy=static_dep_chain)
    else:
        print(f"Unknown target: {name}")
        return

    pr = cProfile.Profile()
    pr.enable()

    await run_benchmark(engine, target, iterations)

    pr.disable()

    s = io.StringIO()
    sortby = "cumulative"
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(20)  # Show top 20
    print(s.getvalue())

    # Also save to file for external tools like snakeviz
    filename = f"profile_{name}_{iterations}.prof"
    ps.dump_stats(filename)
    print(f"Full profile dumped to {filename}")


if __name__ == "__main__":
    target_name = sys.argv if len(sys.argv) > 1 else "simple"
    count = int(sys.argv) if len(sys.argv) > 2 else 1000

    print(f"Profiling {target_name} for {count} iterations...")
    asyncio.run(profile_target(target_name, count))
~~~~~

### 下一步建议
我们已经准备好了诊断工具。请执行此计划，然后运行以下命令：

`python scripts/profile_entry.py stable 1000`

请将完整的输出提供给我。这将为我们提供最终诊断性能瓶颈所需的数据，并指导我们进行下一轮精确的优化。
