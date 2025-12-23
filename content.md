简要回答
我的上一次分析是错误的，我对此表示歉意。

直接拣选 `620f8ae` 失败的事实证明，尽管该提交的意图是好的，但它并非像我判断的那样“完全独立”。它很可能是在已经包含有问题的 `ArgumentResolver` 变更的代码基上创建的，因此它的某些部分（特别是对 `_are_args_simple` 的修改）与那些引入回归的提交存在隐性耦合。

正确的做法不是机械地应用整个提交，而是**外科手术式地重新实现**其核心的、安全的优化思想。我将创建一个新的计划，只提取并应用 `620f8ae` 中真正带来性能提升且无害的部分（即 O(1) 图查找），并**明确地排除**那些有风险的变更。

## [WIP] perf: Re-implement O(1) graph lookups from 620f8ae

### 错误分析
`git cherry-pick 620f8ae` 失败，并复现了与之前被回滚的提交完全相同的 `TypeError` 和 `AttributeError`。

**原因**:
提交 `620f8ae` 并非一个纯粹的、原子的优化。它不仅包含了安全的 O(1) 图查找优化，还包含了对 `_are_args_simple` 函数的修改。这个修改放宽了 TCO 快速路径的准入条件，使得那些需要复杂参数解析（如 `cs.Param` 和 `cs.inject`）的任务被错误地送入了无法处理它们的“快速通道”，从而重新触发了在 `2b54a6e` 中引入、后又被回滚的底层逻辑缺陷。

**解决方案**:
我们将手动创建一个新的变更集，只包含 `620f8ae` 中以下两个关键且安全的优化，而忽略所有其他更改：
1.  为 `Graph` 对象增加 `id -> Node` 的索引。
2.  在 `GraphExecutionStrategy` 中使用该索引进行 O(1) 查找。

### 用户需求
在当前稳定的代码基上，安全地应用 `620f8ae` 提交中包含的性能优化，同时确保不引入任何回归错误。

### 评论
这是一个“概念拣选”而非“代码拣选”的操作。我们吸取了 `620f8ae` 的核心思想——将图查找从 O(N) 优化到 O(1)——并将其作为一组干净的、独立的补丁应用到当前代码上。这种方法隔离了风险，确保我们只获得性能收益，而不继承任何隐性的逻辑依赖。

### 目标
1.  修改 `cascade.graph.model.Graph`，增加一个 O(1) 的节点查找索引。
2.  更新 `cascade.runtime.strategies.graph.GraphExecutionStrategy`，使用新的索引来消除线性扫描。
3.  对 `cascade.runtime.resolvers.ArgumentResolver` 进行一个次要的、安全的边缘优化。

### 基本原理
通过将 `Graph.nodes` 从一个纯列表演进为一个同时维护列表和字典索引的数据结构，我们可以将 TCO 快速路径中一个高频操作的成本降至可忽略不计的水平。由于我们只修改数据结构和其访问方式，而不改变任何参数解析或执行的逻辑流，因此该操作本质上是安全的。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #comp/graph #scope/core #ai/refine #task/domain/core #task/object/performance #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 为 `Graph` 增加 O(1) 节点查找索引

我们将修改 `Graph` 模型，在添加节点时自动建立 `id -> Node` 的索引，并将线性查找方法替换为 O(1) 的字典访问。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
@dataclass
class Graph:
    """A container for nodes and edges representing the workflow topology."""

    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node: Node):
        if node not in self.nodes:
            self.nodes.append(node)

    def add_edge(self, edge: Edge):
        self.edges.append(edge)
~~~~~
~~~~~python
@dataclass
class Graph:
    """A container for nodes and edges representing the workflow topology."""

    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    
    # O(1) index for fast lookup
    _node_index: Dict[str, Node] = field(default_factory=dict, init=False, repr=False)

    def add_node(self, node: Node):
        if node.id not in self._node_index:
            self.nodes.append(node)
            self._node_index[node.id] = node

    def get_node(self, node_id: str) -> Optional[Node]:
        return self._node_index.get(node_id)

    def add_edge(self, edge: Edge):
        self.edges.append(edge)
~~~~~

#### Acts 2: 在执行策略中使用新的 O(1) 查找

现在我们更新 `GraphExecutionStrategy` 的 TCO 快速路径，以利用 `graph.get_node()` 带来的性能提升。

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
                    target_node = next(n for n in graph.nodes if n.id == root_node_id)
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

#### Acts 3: 应用安全的 `ArgumentResolver` 微优化

这是一个次要但有益的更改，它通过一次性过滤边来减少循环内的重复检查，并且与导致错误的逻辑无关。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
        # 2. Overlay Dependencies from Edges
        incoming_edges = [e for e in graph.edges if e.target.id == node.id]

        for edge in incoming_edges:
            if edge.edge_type == EdgeType.DATA:
                val = self._resolve_dependency(
                    edge, node.id, state_backend, graph, instance_map
                )
~~~~~
~~~~~python
        # 2. Overlay Dependencies from Edges
        # Optimization: Filter once
        incoming_edges = [e for e in graph.edges if e.target.id == node.id and e.edge_type == EdgeType.DATA]
        if not incoming_edges:
            return args, kwargs
            
        for edge in incoming_edges:
            if edge.edge_type == EdgeType.DATA:
                val = self._resolve_dependency(
                    edge, node.id, state_backend, graph, instance_map
                )
~~~~~

### 下一步建议
1.  **验证正确性**: 请立即运行 `pytest`。我预期所有测试都将通过，因为我们已经精确地避开了所有已知的雷区。
2.  **验证性能**: 在测试通过后，运行 `python observatory/benchmarks/tco_performance.py`。我们应该能观察到 `simple_countdown` 和 `stable_complex_loop` 的 TPS 显著回升，而 `heavy_complex_countdown` 保持不变。
