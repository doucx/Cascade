简要回答
好的，我将创建一个 `GraphDumper` 工具类，位于 `cascade.compiler.utils.visualizer` 模块中。它将能够把 `BipartiteGraph` 渲染为标准的 DOT 格式文本，通过形状和颜色区分数据节点（圆形/椭圆）和函数节点（矩形），并在连线上标注端口信息，从而实现物理图的白盒可视化。

## [WIP] feat(compiler): 引入 `GraphDumper` 以支持物理图的 DOT 可视化

### 用户需求
为了摆脱“盲人摸象”的调试困境，需要一个工具能够将编译器生成的复杂物理二分图 (`BipartiteGraph`) 转换为人类可读的可视化格式（DOT 语言）。

### 评论
这是一个关键的开发者体验 (DX) 改进。物理图包含大量微观细节（三连体、旁路观测、资源闭环），纯文本日志难以解析。DOT 图可以直观地展示拓扑结构、断连和资源流向，是实现“白盒验证”的基础设施。

### 目标
1.  在 `cascade-compiler` 中实现 `GraphDumper` 类。
2.  支持将 `BipartiteGraph` 导出为 DOT 字符串。
3.  通过节点形状区分 `DataNode` (圆形) 和 `FuncNode` (矩形)。
4.  通过颜色区分不同角色的节点 (Bleacher, Worker, Stainer, Resource)。
5.  在边上清晰标注源端口和目标端口。

### 基本原理
我们将 DOT 生成逻辑封装在 `compiler.utils` 中。为了增强可读性，我们将应用简单的启发式规则来为不同类型的节点上色（例如，Bleacher 为红色，Stainer 为绿色，Data 为蓝色）。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/compiler #task/domain/compiler #task/object/graph-dumper #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建 `visualizer.py`

实现核心的 DOT 生成逻辑。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/utils/visualizer.py
~~~~~
~~~~~python
from typing import List
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import PhysicsDataNode, PhysicsFuncNode, PhysicsNode


class GraphDumper:
    """
    Utility to render a BipartiteGraph into Graphviz DOT format for visualization.
    """

    def to_dot(self, graph: BipartiteGraph) -> str:
        lines: List[str] = [
            "digraph G {",
            "  rankdir=LR;",
            "  node [fontname=\"Helvetica\", fontsize=10];",
            "  edge [fontname=\"Helvetica\", fontsize=8];",
        ]

        # 1. Render Nodes
        for node_id, node in graph.nodes.items():
            attrs = self._get_node_attributes(node)
            attr_str = ", ".join([f'{k}="{v}"' for k, v in attrs.items()])
            lines.append(f'  "{node_id}" [{attr_str}];')

        # 2. Render Edges (Channels)
        for channel in graph.channels:
            src = channel.source_node_id
            tgt = channel.target_node_id

            label = f"{channel.source_port} -> {channel.target_port}"
            if channel.tag_filter:
                label += f"\\n[{channel.tag_filter}]"

            # Check for Observability edges to style them differently (dashed)
            style = "solid"
            color = "black"
            if "obs" in channel.source_port or "obs" in channel.target_port:
                style = "dashed"
                color = "#9e9e9e"  # Grey

            lines.append(
                f'  "{src}" -> "{tgt}" [label="{label}", style="{style}", color="{color}"];'
            )

        lines.append("}")
        return "\n".join(lines)

    def _get_node_attributes(self, node: PhysicsNode) -> dict:
        attrs = {
            "label": f"{node.name}\\n({node.id})",
            "style": "filled",
        }

        if isinstance(node, PhysicsDataNode):
            attrs["shape"] = "ellipse"
            attrs["fillcolor"] = "#e1f5fe"  # Light Blue
            attrs["color"] = "#01579b"

            # Highlight nodes with initial potential energy
            if node.initial_tokens > 0:
                attrs["penwidth"] = "2"
                attrs["label"] += f"\\nTokens: {node.initial_tokens}"

            # Special coloring for Resources buffers/ledgers
            if "resource" in node.id or "ledger" in node.id:
                attrs["fillcolor"] = "#e0f7fa"  # Cyan tint
            elif "trace" in node.id:
                attrs["fillcolor"] = "#f5f5f5"  # Grey (less important)

        elif isinstance(node, PhysicsFuncNode):
            attrs["shape"] = "box"
            attrs["fillcolor"] = "#fff9c4"  # Light Yellow (Default Worker)
            attrs["color"] = "#fbc02d"

            # Color coding based on role heuristics
            if ".bleach" in node.id:
                attrs["fillcolor"] = "#ffccbc"  # Light Orange
                attrs["color"] = "#d84315"
            elif ".stain" in node.id:
                attrs["fillcolor"] = "#c8e6c9"  # Light Green
                attrs["color"] = "#2e7d32"
            elif "allocator" in node.id:
                attrs["fillcolor"] = "#b2ebf2"  # Cyan
                attrs["color"] = "#006064"
            elif "reclaimer" in node.id:
                attrs["fillcolor"] = "#b2dfdb"  # Teal
                attrs["color"] = "#004d40"
            elif "observer" in node.id:
                attrs["fillcolor"] = "#e1bee7"  # Purple
                attrs["color"] = "#4a148c"
            elif "probe" in node.id:
                attrs["fillcolor"] = "#ffecb3"  # Amber
                attrs["shape"] = "hexagon"

        return attrs
~~~~~

#### Acts 2: 导出 `GraphDumper`

在 `utils` 包中公开新类。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/utils/__init__.py
~~~~~
~~~~~python.old
from .naming import PhysicalIdGenerator
from .reflection import ReflectionAnalyzer, TaskAnalyzer
from .hashing import HashingService

__all__ = [
    "PhysicalIdGenerator",
    "ReflectionAnalyzer",
    "TaskAnalyzer",
    "HashingService",
]
~~~~~
~~~~~python.new
from .naming import PhysicalIdGenerator
from .reflection import ReflectionAnalyzer, TaskAnalyzer
from .hashing import HashingService
from .visualizer import GraphDumper

__all__ = [
    "PhysicalIdGenerator",
    "ReflectionAnalyzer",
    "TaskAnalyzer",
    "HashingService",
    "GraphDumper",
]
~~~~~

#### Acts 3: 添加单元测试

确保 Dumper 能正确处理基本的图结构而不崩溃，并生成预期的 DOT 语法。

~~~~~act
write_file
packages/cascade-compiler/tests/unit/utils/test_visualizer.py
~~~~~
~~~~~python
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode, PhysicsFuncNode
from cascade.compiler.utils.visualizer import GraphDumper


def test_dumper_generates_valid_dot():
    # Setup a simple graph
    d1 = PhysicsDataNode(id="d1", name="Data1", initial_tokens=1)
    f1 = PhysicsFuncNode(id="task.bleach", name="Bleacher")
    f2 = PhysicsFuncNode(id="task.worker", name="Worker")

    graph = BipartiteGraph()
    graph.nodes = {"d1": d1, "task.bleach": f1, "task.worker": f2}

    graph.channels.append(Channel("d1", "out", "task.bleach", "in"))
    graph.channels.append(
        Channel("task.bleach", "worker_input", "task.worker", "in", tag_filter="XYZ")
    )
    # Observability channel
    graph.channels.append(Channel("task.bleach", "obs_output", "bus", "in"))

    dumper = GraphDumper()
    dot_output = dumper.to_dot(graph)

    # Assertions
    assert "digraph G {" in dot_output
    assert 'rankdir=LR;' in dot_output

    # Check Nodes
    assert '"d1" [label="Data1\\n(d1)\\nTokens: 1"' in dot_output
    assert 'shape="ellipse"' in dot_output
    assert '"task.bleach" [label="Bleacher\\n(task.bleach)"' in dot_output
    # Check heuristic coloring
    assert 'fillcolor="#ffccbc"' in dot_output  # Bleacher color

    # Check Edges
    assert '"d1" -> "task.bleach" [label="out -> in"' in dot_output
    assert '"task.bleach" -> "task.worker"' in dot_output
    assert 'label="worker_input -> in\\n[XYZ]"' in dot_output

    # Check Obs Edge Styling
    assert 'style="dashed"' in dot_output
~~~~~

### 下一步建议
一旦 `GraphDumper` 就位，我们应该立即将其集成到 `GraphValidator` 或创建一个新的 `DebugTool` 中，用它来检查当前导致死锁的物理图。这将是“白盒验证”的第一个里程碑。建议下一步直接编写一个脚本，使用 `Builder` 生成一个导致问题的图，并用 `GraphDumper` 输出其 DOT 内容。
