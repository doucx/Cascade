简要回答：
好的，我们将着手实现可视化增强，让静态分析的“潜能”在图中显形。

## [WIP] feat(sdk): 增强可视化以区分静态分析路径

### 摘要头
`# [WIP] feat(sdk): Enhance visualization for static analysis paths`

### 用户需求
用户希望在 `cs.visualize` 生成的架构图中，能够直观地、一眼区分出哪些是实际会被调度的“真实节点”，哪些是由静态分析预测出的“影子节点”（Potential Nodes）。

### 评论
可视化的核心价值在于降低认知负荷。如果所有节点看起来都一样，静态分析引入的大量影子节点反而会增加图的混乱度。通过样式的区分（如虚线、灰色、半透明），我们可以利用“前意识处理”（Pre-attentive Processing），让开发者在关注主流程的同时，也能感知到潜在的跳转路径，而不被其干扰。

### 目标
1.  修改 `visualize` 函数，在渲染前预扫描图结构，识别出所有通过 `POTENTIAL` 边引入的“影子节点”。
2.  为影子节点应用独特的视觉样式：
    *   **边框**: 虚线 (`style="dashed,filled"`)。
    *   **填充**: 浅灰色 (`fillcolor="whitesmoke"` 或类似)。
    *   **文字**: 灰色 (`fontcolor="gray50"`), 并附加 `(Potential)` 标记。
3.  优化 `POTENTIAL` 边的样式，使其更符合“预测路径”的语义（如使用红色虚线）。

### 基本原理
我们复用 Solver 中用于剔除影子节点的逻辑：`shadow_ids = targets of POTENTIAL edges`。利用这个集合，我们在生成 DOT 节点定义时进行条件判断，动态注入样式属性。

### 标签
#intent/build #flow/ready #priority/medium #comp/sdk #comp/docs #concept/ui #scope/ux #ai/instruct #task/domain/ui #task/object/visualizer #task/action/enhance #task/state/continue

---

### Script

#### Acts 1: 增强 `visualize.py` 渲染逻辑

我们将修改 `visualize.py`。
1.  添加预处理步骤：扫描 `graph.edges`，收集所有 `EdgeType.POTENTIAL` 指向的目标节点 ID 到 `shadow_node_ids` 集合中。
2.  在节点渲染循环中，检查当前节点是否在 `shadow_node_ids` 中。
3.  如果是，覆盖默认的样式属性（虚线框、灰色文字等）。

~~~~~act
write_file
packages/cascade-sdk/src/cascade/tools/visualize.py
~~~~~
~~~~~python
from typing import Any, Set
from cascade.spec.lazy_types import LazyResult
from cascade.graph.build import build_graph
from cascade.graph.model import Node, EdgeType


def visualize(target: LazyResult[Any]) -> str:
    """
    Builds the computation graph for a target and returns its representation
    in the Graphviz DOT language format.
    """
    graph = build_graph(target)

    dot_parts = [
        "digraph CascadeWorkflow {",
        '  rankdir="TB";',
        '  node [shape=box, style="rounded,filled", fillcolor=white];',
    ]

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

        label = f"{node.name}\\n({node.node_type}){label_suffix}"
        
        dot_parts.append(
            f'  "{node.id}" [label="{label}", shape={shape}, style={style}, '
            f'fillcolor={fillcolor}, fontcolor={fontcolor}];'
        )

    # 2. Define Edges
    for edge in graph.edges:
        style = ""

        if edge.edge_type == EdgeType.CONDITION:
            style = ' [style=dashed, color=gray, label="run_if"]'
        elif edge.edge_type == EdgeType.IMPLICIT:
            style = ' [style=dotted, color=lightgray, arrowhead=none, label="implicit"]'
        elif edge.edge_type == EdgeType.ROUTER_ROUTE:
            # Router route edge
            style = ' [style=dashed, color=orange, arrowhead=open, label="route"]'
        elif edge.router:
            # Router selector edge (which is EdgeType.DATA)
            style = f' [style=dashed, color=blue, label="route via: {edge.arg_name}"]'
        elif edge.edge_type == EdgeType.CONSTRAINT:
            style = (
                f' [style=dotted, color=purple, label="constraint: {edge.arg_name}"]'
            )
        elif edge.edge_type == EdgeType.SEQUENCE:
            style = ' [style=dashed, color=darkgray, arrowhead=open, label="next"]'
        elif edge.edge_type == EdgeType.POTENTIAL:
            # Use a reddish color to indicate a predicted/potential path, dashed
            style = ' [style=dashed, color="#d9534f", fontcolor="#d9534f", arrowhead=open, label="potential"]'
        else:
            style = f' [label="{edge.arg_name}"]'

        dot_parts.append(f'  \"{edge.source.id}\" -> \"{edge.target.id}\"{style};')

    dot_parts.append("}")
    return "\n".join(dot_parts)


def _get_node_shape(node: Node) -> str:
    """Returns the Graphviz shape for a given node type."""
    if node.node_type == "param":
        return "ellipse"
    if node.node_type == "map":
        return "hexagon"
    # Future: Routers could be a diamond, but they are edges in our model
    return "box"
~~~~~

### 下一步建议
我们已经完成了可视化逻辑的增强。
1.  **验证**: 你可以使用 `test_visualize.py` 或者创建一个简单的脚本来生成一个包含 TCO 逻辑的 DOT 文件，然后用 Graphviz 渲染查看效果。
2.  **合并**: 确认无误后，我们可以提交这个更改。这将完成路线图的第三阶段的一部分。
3.  **后续**: 考虑是否需要为 `test_visualize.py` 添加针对 shadow nodes 样式的断言，以防止未来回归。
