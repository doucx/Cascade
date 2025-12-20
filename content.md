简要回答：
分析表明，**内存泄漏是必然的**，根源在于 `InMemoryStateBackend` 的设计缺陷。

1.  **泄漏源头**：`InMemoryStateBackend` 使用一个字典 (`self._results`) 永久存储所有任务的执行结果。在递归场景中，每一代都会生成新的任务 ID，并存入该字典。随着代数无限增加，字典也会无限膨胀。这就是为什么内存以恒定斜率增长（+600MB / 1000代）。
2.  **速度分析**：每代 3 秒意味着吞吐量约为 **333 Tasks/sec**（1000个代理 / 3秒）。考虑到每个任务都涉及图构建、依赖解析、状态存储和 `asyncio` 调度，对于纯 Python 实现的解释型引擎来说，这个速度在预期范围内，但受内存膨胀引起的 GC 压力影响，速度会逐渐变慢。

**解决方案**：
必须引入 **状态垃圾回收 (State GC)** 机制。在 TCO（尾递归优化）模式下，一旦引擎决定进入下一代（即返回了一个新的 `LazyResult`），当前这一代的中间计算结果（Graph 和 Results）在逻辑上就已经完成了使命。

我们将修改 `Engine`，在 TCO 循环发生“代际跳跃”时，主动清理 `StateBackend`。

摘要头：
## [WIP] fix: Implement State GC in Engine TCO loop to prevent memory leaks

### 标签
#intent/fix #intent/refine #flow/ready #priority/high
#comp/runtime #concept/memory #concept/tco #scope/core
#ai/instruct
#task/domain/physics
#task/object/recursion-tco
#task/action/bug-fix
#task/state/continue

### 用户需求
1.  **消除内存泄漏**：确保在无限递归运行时，内存占用保持平稳，而不是线性增长。
2.  **验证 TCO 完备性**：证明 Cascade 不仅在栈深度上支持无限递归，在堆内存管理上也能支持。

### 评论
这是一个关键的架构修正。它确立了 Cascade 运行时的一个重要语义：**TCO 边界即状态生命周期边界**。这意味着通过 `return new_workflow` 传递的数据必须是值（Values）或外部引用（Refs），而不能依赖上一代的内部临时状态。这与函数式编程中的尾调用语义是一致的。

### 目标
1.  修改 `InMemoryStateBackend`，添加 `clear()` 方法。
2.  修改 `Engine.run`，在 TCO 循环末尾调用 `state_backend.clear()`。
3.  重新运行 `recursion_test.py` 验证修复效果。

### 基本原理
在 `Engine.run` 的 `while True` 循环中，每次迭代代表一代。当 `result` 被判定为 `LazyResult` 时，说明当前图已执行完毕，并生成了下一代的入口。此时，当前图产生的所有 `_results` 都可以安全丢弃，因为下一代的依赖已经通过 `LazyResult` 的参数（args/kwargs）捕获了（参数解析器已经将 LazyResult 解析为具体的值）。

---

### Script

#### Acts 1: 为 `InMemoryStateBackend` 添加清理能力

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/adapters/state/in_memory.py
~~~~~
~~~~~python
    def get_skip_reason(self, node_id: str) -> Optional[str]:
        return self._skipped.get(node_id)
~~~~~
~~~~~python
    def get_skip_reason(self, node_id: str) -> Optional[str]:
        return self._skipped.get(node_id)

    def clear(self) -> None:
        """Clears all stored state. Used for garbage collection between TCO steps."""
        self._results.clear()
        self._skipped.clear()
~~~~~

#### Acts 2: 在 `Engine` 的 TCO 循环中触发清理

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                    # 4. Check for Tail Call (LazyResult)
                    if isinstance(result, (LazyResult, MappedLazyResult)):
                        current_target = result
                        # CRITICAL: Yield control to the event loop between TCO iterations.
                        # This allows other tasks (like the experiment timeout) to run.
                        await asyncio.sleep(0)
                    else:
                        final_result = result
                        break
~~~~~
~~~~~python
                    # 4. Check for Tail Call (LazyResult)
                    if isinstance(result, (LazyResult, MappedLazyResult)):
                        current_target = result
                        
                        # STATE GC: Since we are moving to a new generation (new graph),
                        # the transient state of the previous generation is no longer needed.
                        # We clear it to prevent memory leaks in infinite recursion.
                        if hasattr(state_backend, "clear"):
                            state_backend.clear()
                            
                        # CRITICAL: Yield control to the event loop between TCO iterations.
                        # This allows other tasks (like the experiment timeout) to run.
                        await asyncio.sleep(0)
                    else:
                        final_result = result
                        break
~~~~~

### 下一步建议
再次运行 `python -m observatory.protoplasm.physics.recursion_test`。

**预期结果**：
1.  **内存平稳**：Delta 值应该在初始增长（加载库和初始对象）后迅速稳定下来，不再随代数线性增长。
2.  **Net Leak**：最终报告中的净泄漏应大幅降低（可能 < 5MB）。
3.  **运行稳定性**：由于内存压力减轻，后期运行速度可能会更加稳定。
