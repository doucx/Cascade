好的，我们正式启动阶段三。

这是 Cascade 引擎性能演进中最关键的一步。前两个阶段的重构（统一哈希管道、静态分析）都是为了此刻的性能突破做准备。通过实现结构化 JIT，我们将彻底消除 TCO “简单路径”和“重型路径”之间巨大的性能鸿沟。

我将为你生成执行此项核心改造的计划。

## [WIP] feat(engine): 实现结构化 JIT 以启用 TCO 重型路径的快速通道

### 用户需求
开始实施“综合架构演进建议书”中的第三阶段：内核突破——结构化 JIT 与动态修补。

### 评论
这是一个决定性的、里程碑式的改进。它将使 Cascade 的 TCO 性能从“特定场景下很快”提升到“在所有结构稳定的递归场景下都很快”，是引擎从一个原型演进为高性能生产级运行时的关键。

### 目标
1.  修改 `GraphExecutionStrategy.execute` 的核心逻辑，移除脆弱的 `_are_args_simple` 检查。
2.  这将允许包含 `LazyResult` 参数的递归调用（即“重型路径”）能够命中 JIT 缓存 (`_cycle_cache`)，从而进入快速执行通道。
3.  利用现有的 `_execute_hot_node` 和 `ArgumentResolver`，通过 `input_overrides` 机制实现“动态参数修补”，即时地从 `state_backend` 解析新的动态参数，而无需重建整个计算图。

### 基本原理
前序阶段已经确立了 `Template Hash` (体现在 `_tco_cycle_id` 中) 作为计算结构“蓝图”的唯一标识。`_are_args_simple` 检查是一个保守的、临时的保护措施，它阻止了参数动态变化的递归进入快速通道。

现在，我们将信任 `Template Hash`。如果 `_tco_cycle_id` 匹配，就意味着计算的“骨架”是完全相同的，即使流经其中的“血肉”（动态参数）在变化。通过移除这个检查，我们让所有结构稳定的递归调用都进入快速通道。在这个通道中，`_execute_hot_node` 会将新的、动态的 `LazyResult` 参数作为 `input_overrides` 传递给 `ArgumentResolver`，后者会直接从状态后端获取它们的值，从而实现了“动态修补”，在纳秒级的时间内将新数据注入到缓存的旧执行计划中。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #concept/state #scope/core #ai/instruct #task/domain/performance #task/object/tco-heavy-path #task/action/optimization #task/state/begin

---

### Script

#### Acts 1: 移除 `_are_args_simple` 检查以启用 JIT

我们将修改 `GraphExecutionStrategy`，移除对 TCO 快速路径的参数检查限制。这将允许所有具有稳定结构签名的递归调用（无论其参数是否包含 `LazyResult`）都能利用缓存的图和执行计划。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
            if cycle_id and cycle_id in self._cycle_cache:
                if self._are_args_simple(current_target):
                    fast_path_data = self._cycle_cache[cycle_id]

            # The step stack holds "task" (step) scoped resources
~~~~~
~~~~~python
            if cycle_id and cycle_id in self._cycle_cache:
                fast_path_data = self._cycle_cache[cycle_id]

            # The step stack holds "task" (step) scoped resources
~~~~~

### 下一步建议
我们已经完成了核心逻辑的修改。现在最关键的一步是**验证性能收益**。

我强烈建议你立即运行位于 `observatory/benchmarks/tco_performance.py` 的性能测试套件。

**预期结果**：
在本次修改之后，`test_heavy_path_performance` 测试用例的性能指标（TPS）应该会有一个**数量级**的提升，从之前的 ~800 TPS 跃升至与 `test_simple_path_performance`（~100k TPS）相近的水平。

这将是本次架构演进成功的直接证明。如果你确认性能达标，我们将进入下一个阶段：为这个里程碑式的改进创建测试和提交。
