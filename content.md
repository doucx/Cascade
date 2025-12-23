简要回答
确实如此。在之前的“强制重置”操作中，我虽然更新了 `model.py` 使其具备 O(1) 索引能力，但**漏掉了更新 `strategies/graph.py` 去真正调用这个新 API**。

这意味着现在的引擎虽然有一个高性能的图数据结构，但执行策略仍然在使用笨拙的 `next()` 线性扫描。这就是为什么性能停留在 16k 而没有达到 21k 的原因——我们只修了一半。

## [WIP] perf: 在执行策略中激活 O(1) 图查找

### 评论
我们已经为 `Graph` 添加了 `get_node(id)` 方法（O(1)），但 `GraphExecutionStrategy` 的 TCO 快速路径仍然在使用旧的 `next(... if ...)` 线性扫描（O(N)）。这是一个遗漏的链接。
补上这个调用，性能应能立即恢复到 20k+ TPS 的水平。

### 用户需求
恢复“黄金提交”的性能表现。

### 目标
1.  修改 `packages/cascade-engine/src/cascade/runtime/strategies/graph.py`。
2.  将线性查找替换为 `graph.get_node()`。

### 基本原理
消除热路径中的 O(N) 操作。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #scope/core #ai/refine #task/domain/core #task/object/performance #task/action/enable-optimization #task/state/continue

---

### Script

#### Acts 1: 激活 `GraphExecutionStrategy` 中的 O(1) 查找

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                if fast_path_data:
                    # FAST PATH: Reuse Graph & Plan
                    # Unpack all 4 cached values: graph, indexed_plan, root_node_id, req_res
                    graph, indexed_plan, root_node_id, _ = fast_path_data
                    # Reconstruct virtual instance map for current iteration
                    target_node = graph.get_node(root_node_id)
                    instance_map = {current_target._uuid: target_node}
                    plan = self._rehydrate_plan(graph, indexed_plan)
~~~~~
~~~~~python
                if fast_path_data:
                    # FAST PATH: Reuse Graph & Plan
                    # Unpack all 4 cached values: graph, indexed_plan, root_node_id, req_res
                    graph, indexed_plan, root_node_id, _ = fast_path_data
                    # Reconstruct virtual instance map for current iteration
                    target_node = graph.get_node(root_node_id)
                    instance_map = {current_target._uuid: target_node}
                    plan = self._rehydrate_plan(graph, indexed_plan)
~~~~~
