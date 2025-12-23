好的，我们立即开始架构优化任务 A。

这是一个典型的“代码健康度”投资。通过将“影子节点”的身份从一种需要通过图上下文推断的*隐性状态*，转变为节点自身的一个*显性属性* (`is_shadow`)，我们可以极大地简化下游组件（如 Solver 和 Visualizer）的逻辑，使其更清晰、更健壮、更易于维护。

我将生成一个计划来执行这个重构。

## [WIP] refactor(spec): 在 Node 模型中引入 is_shadow 标志以提升代码清晰度

### 用户需求
将“影子节点”的识别方式从“检查 `POTENTIAL` 边”重构为“检查节点上的 `is_shadow` 标志”，以优化架构，提升代码清晰度和健壮性。

### 评论
这是一个优秀的重构决策。它遵循了“显式优于隐式”的 Pythonic 哲学。一个组件（如 Solver）不应该需要知道另一个组件（GraphBuilder）的内部实现细节（即“影子节点是通过 POTENTIAL 边创建的”）来完成自己的工作。通过在 `Node` 这个共享的数据契约上添加一个明确的标志，我们解耦了这些组件，使得每个部分都更加内聚和独立。

### 目标
1.  在 `cascade.graph.model.Node` 数据类中添加 `is_shadow: bool = False` 字段。
2.  更新 `GraphBuilder`，在创建影子节点时设置 `is_shadow=True`。
3.  重构 `NativeSolver`、`CSPSolver` 和 `visualize` 函数，使其使用新的 `node.is_shadow` 标志来识别和处理影子节点，替代原有的边扫描逻辑。

### 基本原理
我们正在将一个派生属性（“一个节点是影子节点，因为它是一条 POTENTIAL 边的目标”）具体化为一个原生属性。这使得节点的身份是自包含的，查询其身份的操作从 O(E)（E 是边的数量）的图扫描变为 O(1) 的属性访问，同时极大地简化了代码逻辑。

### 标签
#intent/refine #flow/ready #priority/medium #comp/spec #comp/engine #comp/sdk #concept/state #scope/core #scope/dx #ai/instruct #task/domain/engine #task/object/node-model #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新核心数据模型 (`Node`)

我们首先修改位于 `cascade-spec` 包中的核心 `Node` 定义，为其添加 `is_shadow` 标志。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/graph/model.py
~~~~~
~~~~~python
@dataclass
class Node:
    """Represents a node in the computation graph."""

    id: str
    name: str

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
~~~~~
~~~~~python
@dataclass
class Node:
    """Represents a node in the computation graph."""

    id: str
    name: str
    is_shadow: bool = False  # True if this node is for static analysis only

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
~~~~~

#### Acts 2: 更新图构建器以设置新标志

现在，我们让 `GraphBuilder` 在创建影子节点时，正确地设置 `is_shadow` 标志。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
                shadow_lr = LazyResult(
                    task=target_task,
                    args=(),
                    kwargs={},
                    _uuid=potential_uuid
                )
                
                # Visit the shadow node, disable further TCO scanning to avoid infinite recursion
                target_node = self._visit(shadow_lr, scan_for_tco=False)
~~~~~
~~~~~python
                shadow_lr = LazyResult(
                    task=target_task,
                    args=(),
                    kwargs={},
                    _uuid=potential_uuid
                )

                # Shadow nodes are created by directly instantiating Node,
                # not by visiting the LazyResult, to mark them explicitly.
                # This avoids them being added to the `_visited` cache with a real UUID.
                target_node = Node(
                    id=potential_uuid,
                    name=target_task.name,
                    node_type="task",
                    is_shadow=True,  # Explicitly mark as a shadow node
                )
                self.graph.add_node(target_node)
                self._visited[potential_uuid] = target_node
~~~~~

#### Acts 3: 重构 Solver 和 Visualizer 以使用新标志

最后，我们简化 `NativeSolver` 和 `visualize` 的逻辑，让它们直接使用 `is_shadow` 标志。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/native.py
~~~~~
~~~~~python
    def resolve(self, graph: Graph) -> ExecutionPlan:
        # 0. Filter out Shadow Nodes (Targets of POTENTIAL edges)
        # These nodes exist for static analysis but should not be executed.
        shadow_ids = {
            edge.target.id for edge in graph.edges if edge.edge_type == EdgeType.POTENTIAL
        }
        active_nodes = [node for node in graph.nodes if node.id not in shadow_ids]

        # 1. Calculate in-degrees for all active nodes
        in_degree: Dict[str, int] = {node.id: 0 for node in active_nodes}
        adj_list: Dict[str, List[str]] = {node.id: [] for node in active_nodes}

        for edge in graph.edges:
            # Skip POTENTIAL edges and edges involving shadow nodes
            if edge.edge_type == EdgeType.POTENTIAL:
                continue
            if edge.source.id in shadow_ids or edge.target.id in shadow_ids:
                continue

            in_degree[edge.target.id] += 1
            adj_list[edge.source.id].append(edge.target.id)
~~~~~
~~~~~python
    def resolve(self, graph: Graph) -> ExecutionPlan:
        # 0. Filter out Shadow Nodes using the explicit `is_shadow` flag.
        active_nodes = [node for node in graph.nodes if not node.is_shadow]

        if not active_nodes:
            return []

        # 1. Calculate in-degrees for all active nodes
        in_degree: Dict[str, int] = {node.id: 0 for node in active_nodes}
        adj_list: Dict[str, List[str]] = {node.id: [] for node in active_nodes}

        # Build a lookup for active nodes for efficient edge filtering
        active_node_ids = {node.id for node in active_nodes}

        for edge in graph.edges:
            # An edge is only part of the execution plan if both its source
            # and target are active nodes. This naturally filters out POTENTIAL edges.
            if (
                edge.source.id in active_node_ids
                and edge.target.id in active_node_ids
            ):
                in_degree[edge.target.id] += 1
                adj_list[edge.source.id].append(edge.target.id)
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/visualize.py
~~~~~
~~~~~python
    # 0. Pre-scan: Identify Shadow Nodes (Targets of POTENTIAL edges)
    shadow_node_ids: Set[str] = {
        edge.target.id for edge in graph.edges if edge.edge_type == EdgeType.POTENTIAL
    }

    # 1. Define Nodes
    for node in graph.nodes:
        shape = _get_node_shape(node)
        
        # Default Style
        style = '"rounded,filled"'
        fillcolor = "white"
        fontcolor = "black"
        label_suffix = ""

        # Shadow Style Override
        if node.id in shadow_node_ids:
            style = '"dashed,filled"'
            fillcolor = "whitesmoke"  # Very light gray
            fontcolor = "gray50"
            label_suffix = "\\n(Potential)"
~~~~~
~~~~~python
    # 1. Define Nodes
    for node in graph.nodes:
        shape = _get_node_shape(node)
        
        # Default Style
        style = '"rounded,filled"'
        fillcolor = "white"
        fontcolor = "black"
        label_suffix = ""

        # Shadow Style Override
        if node.is_shadow:
            style = '"dashed,filled"'
            fillcolor = "whitesmoke"  # Very light gray
            fontcolor = "gray50"
            label_suffix = "\\n(Potential)"
~~~~~

### 下一步建议
我们已经完成了对核心组件的重构。请运行测试套件以确保所有逻辑仍然按预期工作。如果测试通过，我们就可以提交这个重构，它将使我们的代码库更加清晰和健壮。
