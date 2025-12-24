好的，我们开始执行 “阶段零：性能基线优化”。

你的分析是正确的。在将 `StateBackend` 异步化之后，`GraphExecutionStrategy` 的 TCO 循环（快速路径）中被引入了 `await state_backend.clear()` 和 `await asyncio.sleep(0)`。这两个 `await` 在每一次“热循环”迭代中都会强制进行不必要的事件循环上下文切换，导致了显著的性能回退。

我们的目标是将这些异步操作移出 TCO 快速路径，仅在进入“慢速路径”（即需要构建新图时）执行。这样可以确保快速路径的循环体对事件循环是零开销的，从而恢复其应有的性能基线。

我将生成一个计划来执行这个重构。

## [WIP] refactor: 移除 TCO 快速路径中的异步开销

### 用户需求
根据《综合架构演进建议书》中的定义，执行“阶段零：性能基线优化”，将 TCO 快速路径中的 `await state_backend.clear()` 和 `await asyncio.sleep(0)` 调用移至慢速路径。

### 评论
这是一个关键的性能基线校准步骤。只有将 TCO 快速路径的性能恢复到其“零开销”的最佳状态，我们才能准确地衡量后续阶段（如统一哈希管道）引入的计算开销。这次重构将使我们的性能测试和优化工作建立在一个稳定可靠的基础上。

### 目标
1.  定位 `GraphExecutionStrategy.execute` 方法中的 TCO `while True:` 循环。
2.  从循环末尾的快速路径逻辑中移除 `await state_backend.clear()` 和 `await asyncio.sleep(0)`。
3.  将这两个调用移动到慢速路径（`else` 块）中，在调用 `build_graph` 之前。

### 基本原理
TCO 快速路径（Fast Path）的核心价值在于其近乎零成本的循环。每一次迭代都不应该与 `asyncio` 事件循环发生交互。因此，任何 `await` 操作都应该被排除。相反，慢速路径（Slow Path）本身就是高成本操作（因为它需要构建图、求解计划等），在此处增加两个异步调用所带来的额外开销可以忽略不计，却是逻辑上正确的位置（在开始构建新图之前清理状态并让出控制权）。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #scope/core #ai/instruct #task/domain/runtime #task/object/tco-fast-path #task/action/optimization #task/state/begin

---

### Script

#### Acts 1: 重构 `GraphExecutionStrategy` 的 TCO 循环

我们将修改 `graph.py` 文件。首先，从 `while` 循环的末尾移除异步状态清理和 `sleep` 调用。然后，将这段逻辑粘贴到进入慢速路径（`else` 块）的开头。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
            # 5. Check for Tail Call (LazyResult) - TCO Logic
            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
                # STATE GC (Asynchronous)
                if hasattr(state_backend, "clear") and inspect.iscoroutinefunction(
                    state_backend.clear
                ):
                    await state_backend.clear()
                # Yield control
                await asyncio.sleep(0)
            else:
                return result
~~~~~
~~~~~python
            # 5. Check for Tail Call (LazyResult) - TCO Logic
            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
            else:
                return result
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                else:
                    # SLOW PATH: Build Graph
                    graph, instance_map = build_graph(
                        current_target, registry=self._node_registry
                    )

                    if current_target._uuid not in instance_map:
~~~~~
~~~~~python
                else:
                    # SLOW PATH: Build Graph
                    # STATE GC (Asynchronous)
                    if hasattr(state_backend, "clear") and inspect.iscoroutinefunction(
                        state_backend.clear
                    ):
                        await state_backend.clear()
                    # Yield control
                    await asyncio.sleep(0)

                    graph, instance_map = build_graph(
                        current_target, registry=self._node_registry
                    )

                    if current_target._uuid not in instance_map:
~~~~~

### 下一步建议
我们已经完成了性能基线的恢复工作。现在，我们可以放心地进行下一步的重构，并且能够准确地衡量其带来的影响。

根据路线图，我建议我们开始实施 **阶段一：基石重构 —— 统一哈希管道 (The Hashing Pipeline)**。如果你同意，我将为此准备一个新的计划。
