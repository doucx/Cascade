好的，我们开始代码清理。

在我们的性能冲刺中，最明显、最“不择手段”的临时优化是在 `ArgumentResolver` 中直接访问 `InMemoryStateBackend` 的私有 `_results` 字典。这个“后门”虽然有效，但严重违反了我们基于协议的架构原则，形成了对特定实现的硬耦合。

现在，既然我们已经战略性地决定停止微观优化，并将架构健康度置于首位，是时候移除这个“技术债”了。

我将生成一个计划，移除这个临时优化，让 `ArgumentResolver` 严格遵守 `StateBackend` 的公共协议。

## [WIP] refactor: Remove temporary optimization from ArgumentResolver

### 用户需求
移除在性能优化阶段引入的所有临时性或“hacky”的代码，特别是 `ArgumentResolver` 中对 `InMemoryStateBackend` 私有成员的直接访问，以恢复代码的整洁性和协议合规性。

### 评论
这是一个对长期可维护性至关重要的清理步骤。直接访问 `_results` 字典虽然在压测中提供了性能提升，但它创建了一个脆弱的、隐式的耦合，使得引入新的 `StateBackend` 实现变得危险。移除这个“后门”可以确保我们的核心逻辑只依赖于公开、稳定的协议，这比在 Python 极限下压榨出的最后一点性能更有价值。

### 目标
1.  修改 `cascade.runtime.resolvers.ArgumentResolver._get_node_result` 方法。
2.  移除 `if hasattr(state_backend, "_results")` 这个特殊分支。
3.  确保所有状态访问都通过 `await state_backend.has_result()` 和 `await state_backend.get_result()` 这两个官方异步协议方法进行。

### 基本原理
优先保证架构的完整性和协议的遵从性，而不是一个破坏封装的微观优化。此举将使系统更加健壮、可预测，并易于未来的扩展。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #concept/state #scope/core #ai/instruct #task/domain/core #task/object/architectural-health #task/action/cleanup #task/state/continue

---

### Script

#### Acts 1: 恢复 `ArgumentResolver` 的协议合规性

我们将移除 `_get_node_result` 中的快速路径，使其严格遵守 `StateBackend` 协议。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
    async def _get_node_result(
        self,
        node_id: str,
        consumer_id: str,
        arg_name: str,
        state_backend: StateBackend,
        graph: Graph,
    ) -> Any:
        """Helper to get a node's result, with skip penetration logic."""
        # SUPER FAST PATH: Direct dict access for InMemoryStateBackend
        # This avoids 2 awaits per dependency (has_result + get_result)
        if hasattr(state_backend, "_results"):
            # We assume it's InMemoryStateBackend-like
            if node_id in state_backend._results:
                return state_backend._results[node_id]
        else:
            # Standard Protocol Path
            if await state_backend.has_result(node_id):
                return await state_backend.get_result(node_id)

        # Slow Path: Check for skip/penetration
        skip_reason = await state_backend.get_skip_reason(node_id)
~~~~~
~~~~~python
    async def _get_node_result(
        self,
        node_id: str,
        consumer_id: str,
        arg_name: str,
        state_backend: StateBackend,
        graph: Graph,
    ) -> Any:
        """Helper to get a node's result, with skip penetration logic."""
        if await state_backend.has_result(node_id):
            return await state_backend.get_result(node_id)

        # Slow Path: Check for skip/penetration
        skip_reason = await state_backend.get_skip_reason(node_id)
~~~~~

### 下一步建议

我们已经完成了代码清理，恢复了架构的整洁性。至此，从“建立双层身份体系”到“性能压测与优化”再到“代码清理”的整个宏大任务已经全部完成。

这是一个完美的收尾点。我建议我们创建一个最终的 `[COMMIT]` 计划，将性能优化阶段的所有工作（包括对压测脚本的改进和这次的代码清理）作为一个完整的单元提交。

如果你同意，我将生成这个最终的提交计划。
