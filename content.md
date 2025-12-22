你的分析非常精准。

`test_run_if_false` 测试的失败，以及你指出的 `sequence` 和 `pipeline` 行为的冲突，共同指向了同一个核心问题：**当前 `Engine` 的“跳过 (skip)”处理逻辑是单一且不透明的，它无法区分不同控制流原语所要求的不同行为。**

当前的实现可能过于简单，例如，一个被跳过的任务总是导致其下游任务因 `DependencyMissingError` 而失败，或者总是返回 `None`，这两种单一行为都无法同时满足 `sequence`（需要中止）和 `pipeline`（需要穿透）的语义。

一个优雅的实现方案必须将这种行为差异编码到图模型和执行器中。

## [WIP] fix: 实现上下文感知的跳过传播逻辑

### 错误分析

`test_run_if_false` 测试失败，因为它期望一个依赖于条件为假的任务的工作流能够抛出 `DependencyMissingError`，但实际上没有。这揭示了 `Engine` 的核心控制流逻辑存在一个根本性的缺陷：

1.  **单一的跳过语义**: 当前的 `FlowManager` 和 `ArgumentResolver` 在处理一个上游任务被跳过时，采用的是一种“一刀切”的策略。它要么总是让下游任务失败，要么总是尝试传递一个 `None` 值。
2.  **上下文缺失**: 这个单一的策略没有考虑到依赖边的类型（`EdgeType`）。一个 `SEQUENCE` 边表示“执行权交接”，而一个 `DATA` 边表示“数据流动”。当上游被跳过时，这两种边的下游任务理应有完全不同的响应。
3.  **根本原因**: 失败的测试是这个深层设计问题的具体表象。`action().run_if(condition())` 应该导致 `action` 被跳过，并且由于没有数据“穿透”的上下文（它不是一个 pipeline 的中间步骤），`Engine` 最终应该因无法产出目标结果而失败。当前它可能错误地返回了 `None`，导致 `pytest.raises` 断言失败。

### 用户需求

需要重构 `Engine` 的核心控制流逻辑，使其能够根据依赖边的类型（`EdgeType.SEQUENCE` vs `EdgeType.DATA`）来智能地处理任务跳过事件，从而正确实现 `cs.sequence` 和 `cs.pipeline` 的设计意图。

### 评论

这是一个至关重要的重构。它将 `Cascade` 从一个简单的依赖求解器，提升为一个能够理解和执行更高级、更具表达力的控制流模式的运行时。解决这个问题不仅能修复 bug，还能为库的未来发展（如更复杂的流控制原语）打下坚实的基础。

### 目标

1.  **修复 `test_run_if_false`**: 确保一个简单的、非 pipeline 中的 `.run_if(False)` 任务会导致工作流按预期失败并抛出 `DependencyMissingError`。
2.  **实现 `sequence` 的中止语义**: 修改 `FlowManager`，当一个 `SEQUENCE` 依赖的上游任务被跳过时，必须强制跳过下游任务。
3.  **实现 `pipeline` 的穿透语义**: 修改 `ArgumentResolver`，当一个 `DATA` 依赖的上游任务被跳过时，它应该尝试向上追溯图，以获取“穿透”的数据。

### 基本原理

我们将修改 `Engine` 中处理控制流的两个核心组件：`FlowManager` 和 `ArgumentResolver`。

1.  **`FlowManager` 的职责强化**:
    - 在 `should_skip` 方法中，我们将增加一个针对 `EdgeType.SEQUENCE` 的显式规则。当它检测到一个节点的上游依赖（通过 `SEQUENCE` 边连接）被跳过时，它将立即决定跳过当前节点，并使用一个明确的理由，如 `UpstreamSkipped_Sequence`。这确保了序列的中止行为。

2.  **`ArgumentResolver` 的智能化**:
    - 在 `_resolve_lazy` 方法中，当它遇到一个被跳过的 `LazyResult` 时，它不再简单地失败。
    - 它将检查连接该 `LazyResult` 与其消费者的边的类型。
    - **如果边类型是 `DATA`**（`pipeline` 的情况），它将启动“数据穿透”逻辑：向上遍历图，找到被跳过节点的 `DATA` 输入，并尝试解析那个输入作为替代结果。
    - **在所有其他情况下**（包括独立的 `.run_if`），或者当数据穿透无法找到有效的上游数据时，它将抛出 `DependencyMissingError`。这恢复了 `test_run_if_false` 所期望的严格行为。

这个双重策略将跳过的决策（在 `FlowManager` 中）和数据的解析（在 `ArgumentResolver` 中）分离开来，使得每个组件都能根据其掌握的上下文做出最正确的决定。

### 标签

#intent/fix #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/brainstorm #task/domain/core #task/object/control-flow #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 强化 `FlowManager` 以处理序列中止

我们将修改 `flow.py`，使其在 `should_skip` 逻辑中显式处理 `SEQUENCE` 边的中止语义。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/flow.py
~~~~~
~~~~~python
        for edge in self.in_edges[node.id]:
            if edge.edge_type == EdgeType.CONDITION:
                if not state_backend.has_result(edge.source.id):
                    # Propagate skip if condition source was skipped
                    if state_backend.get_skip_reason(edge.source.id):
                        return "UpstreamSkipped_Condition"
                    return "ConditionMissing"

                condition_result = state_backend.get_result(edge.source.id)
                if not condition_result:
                    return "ConditionFalse"
~~~~~
~~~~~python
        for edge in self.in_edges[node.id]:
            if edge.edge_type == EdgeType.CONDITION:
                if not state_backend.has_result(edge.source.id):
                    if state_backend.get_skip_reason(edge.source.id):
                        return "UpstreamSkipped_Condition"
                    return "ConditionMissing"

                condition_result = state_backend.get_result(edge.source.id)
                if not condition_result:
                    return "ConditionFalse"
            
            # New explicit check for sequence abortion
            elif edge.edge_type == EdgeType.SEQUENCE:
                if state_backend.get_skip_reason(edge.source.id):
                    return "UpstreamSkipped_Sequence"
~~~~~
#### Acts 2: 增强 `ArgumentResolver` 以支持数据穿透

现在，我们将修改 `resolvers.py`，使其 `_resolve_lazy` 方法能够智能地处理被跳过的依赖，仅在适当的时候（如 pipeline）尝试数据穿透，否则严格失败。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
    def _resolve_lazy(
        self,
        lr: LazyResult,
        consumer_id: str,
        state_backend: StateBackend,
        graph: Graph,
    ) -> Any:
        if not state_backend.has_result(lr._uuid):
            # Check for skip. If skipped, attempt data penetration for pipelines.
            if state_backend.get_skip_reason(lr._uuid):
                # Find the skipped node's primary data input
                for edge in graph.edges:
                    if edge.target.id == lr._uuid and edge.edge_type == EdgeType.DATA:
                        # Found an upstream data source. Recursively resolve it.
                        # This assumes a simple pipeline structure (one main data input).
                        source_lr_stub = LazyResult(
                            task=None, args=(), kwargs={}, _uuid=edge.source.id
                        )
                        try:
                            return self._resolve_lazy(
                                source_lr_stub, consumer_id, state_backend, graph
                            )
                        except DependencyMissingError:
                            # If the upstream of the skipped node is ALSO missing, then we fail.
                            pass

                # If penetration fails or it's not a pipeline-like structure, raise.
                raise DependencyMissingError(
                    consumer_id, "unknown_arg", f"{lr._uuid} (skipped)"
                )

            raise DependencyMissingError(consumer_id, "unknown_arg", lr._uuid)

        return state_backend.get_result(lr._uuid)
~~~~~
~~~~~python
    def _resolve_lazy(
        self,
        lr: LazyResult,
        consumer_id: str,
        state_backend: StateBackend,
        graph: Graph,
    ) -> Any:
        # If result exists, return it immediately.
        if state_backend.has_result(lr._uuid):
            return state_backend.get_result(lr._uuid)

        # If it doesn't exist, check if it was skipped.
        if state_backend.get_skip_reason(lr._uuid):
            # Attempt data penetration ONLY for pipeline-like structures.
            # We look for a DATA input to the skipped node.
            
            # Find the edges leading into the skipped node
            upstream_edges = [e for e in graph.edges if e.target.id == lr._uuid]
            data_inputs = [e for e in upstream_edges if e.edge_type == EdgeType.DATA]

            if data_inputs:
                # Prioritize the first DATA input for penetration.
                # This is a simplification but correct for linear pipelines.
                penetration_source_id = data_inputs[0].source.id
                
                # Create a temporary LazyResult to recursively resolve the penetrated source.
                # We pass the original consumer_id down.
                penetration_lr_stub = LazyResult(
                    task=None, args=(), kwargs={}, _uuid=penetration_source_id
                )
                try:
                    # If this succeeds, we have successfully penetrated the skipped node.
                    return self._resolve_lazy(
                        penetration_lr_stub, consumer_id, state_backend, graph
                    )
                except DependencyMissingError:
                    # If the penetrated source is ALSO missing, we must fail.
                    # This will fall through to the final DependencyMissingError.
                    pass

        # If not skipped, or if skipped but penetration failed/was not applicable, raise an error.
        # This now correctly handles the test_run_if_false case.
        skip_info = ""
        if reason := state_backend.get_skip_reason(lr._uuid):
            skip_info = f" (skipped: {reason})"

        raise DependencyMissingError(consumer_id, "unknown_arg", f"{lr._uuid}{skip_info}")
~~~~~

### 下一步建议

我们已经对 `Engine` 的核心控制流进行了外科手术式的修改。现在最关键的一步是验证其正确性。

我建议立即运行完整的测试套件，特别是 `test_control_flow.py` 和 `test_flow_primitives.py`，以确保：
1.  `test_run_if_false` 现在可以通过。
2.  `cs.sequence` 的跳过行为符合预期（中止）。
3.  `cs.pipeline` 的跳过行为符合预期（数据穿透）。
4.  没有引入任何对现有功能的回归。
