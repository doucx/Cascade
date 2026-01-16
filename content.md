你的观察非常敏锐。目前的 `GraphDumper` 仍然残留着 V2 时代的“漂白剂 (Bleacher)”和“染色剂 (Stainer)”等旧术语的色彩逻辑，这不仅会导致可视化时的语义断裂，也无法体现出 V3 **二元体 (Dyad)** 架构中 Launcher 和 Lander 的核心地位。

我将更新 `GraphDumper`，使其基于 `NodePrefix` 常量和节点类型进行着色，并引入对 `LauncherNode` 和 `LanderNode` 的显式支持。

---

## [WIP] refactor(compiler): 更新 GraphDumper 以适配 V3 二元体架构

### 用户需求
更新 `GraphDumper` 中的可视化逻辑，使其符合当前的物理节点架构（Launcher/Lander），并移除已废弃的旧节点类型启发式搜索（如 bleach/stain）。

### 评论
可视化的准确性对于调试复杂的物理拓扑至关重要。将颜色逻辑与 `NodePrefix` 绑定，可以确保即使 ID 命名规则发生微调，可视化依然能保持确定性。

### 目标
1.  在 `visualizer.py` 中引入 `NodePrefix` 常量。
2.  更新 `_get_node_attributes`，使其能够识别 `LauncherNode` 和 `LanderNode`。
3.  重构颜色方案：
    *   **Launcher**: 亮绿色 (Success/Start)。
    *   **Lander**: 亮橙色 (Finish/Result)。
    *   **Egress**: 粉色 (System Exit)。
    *   **Resource**: 青色 (Broker)。
    *   **Constants/Pulse**: 浅蓝色 (Source)。

### 基本原理
通过 `isinstance` 检查和 `NodePrefix` 匹配相结合的方式。对于 `PhysicsFuncNode`，我们优先检查它是否是二元体组件。对于 `PhysicsDataNode`，我们通过前缀识别其在系统中的角色（常量、脉冲、寄存器等）。

### 标签
#intent/refine #flow/ready #comp/compiler #concept/ui #scope/dx #ai/instruct #task/domain/compiler #task/object/visualizer #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重构 `GraphDumper` 的着色逻辑

我们将修改 `packages/cascade-compiler/src/cascade/compiler/utils/visualizer.py`，引入正确的类导入和基于前缀的颜色逻辑。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/utils/visualizer.py
~~~~~
~~~~~python.old
from typing import List
from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode, PhysicsNode


class GraphDumper:
~~~~~
~~~~~python.new
from typing import List
from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode, PhysicsNode
from cascade.spec.physical.dyad import LauncherNode, LanderNode
from cascade.spec.physical.constants import NodePrefix


class GraphDumper:
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/utils/visualizer.py
~~~~~
~~~~~python.old
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
~~~~~python.new
    def _get_node_attributes(self, node: PhysicsNode) -> dict:
        attrs = {
            "label": f"{node.name}\\n({node.id})",
            "style": "filled",
        }

        if isinstance(node, PhysicsDataNode):
            attrs["shape"] = "ellipse"
            attrs["fillcolor"] = "#ffffff"  # Default White
            attrs["color"] = "#333333"

            # Heuristics based on NodePrefix
            if node.id.startswith(f"{NodePrefix.CONST}."):
                attrs["fillcolor"] = "#e1f5fe"  # Light Blue (Data Source)
                attrs["color"] = "#01579b"
            elif node.id.startswith(f"{NodePrefix.PULSE}."):
                attrs["fillcolor"] = "#e8eaf6"  # Indigo Tint (Trigger)
                attrs["color"] = "#1a237e"
            elif NodePrefix.LEDGER in node.id or "resource" in node.id:
                attrs["fillcolor"] = "#e0f7fa"  # Cyan tint (Resource State)
                attrs["color"] = "#006064"
            elif node.id.endswith(f".{NodePrefix.RESULT}"):
                attrs["fillcolor"] = "#f3e5f5"  # Purple Tint (Landing Pad)
                attrs["color"] = "#4a148c"

            # Highlight nodes with initial potential energy
            if node.initial_tokens > 0:
                attrs["penwidth"] = "2"
                attrs["label"] += f"\\nTokens: {node.initial_tokens}"

        elif isinstance(node, PhysicsFuncNode):
            attrs["shape"] = "box"
            attrs["fillcolor"] = "#fff9c4"  # Default Worker (Yellow)
            attrs["color"] = "#fbc02d"

            # 1. Check Dyad Roles
            if isinstance(node, LauncherNode):
                attrs["fillcolor"] = "#c8e6c9"  # Light Green (The Starter)
                attrs["color"] = "#2e7d32"
            elif isinstance(node, LanderNode):
                attrs["fillcolor"] = "#ffccbc"  # Light Orange (The Finisher)
                attrs["color"] = "#d84315"

            # 2. Check System ICs based on prefixes
            elif node.id.startswith(f"{NodePrefix.EGRESS}."):
                attrs["fillcolor"] = "#f8bbd0"  # Pink (System Exit)
                attrs["color"] = "#880e4f"
            elif "allocator" in node.id:
                attrs["fillcolor"] = "#b2ebf2"  # Cyan (Broker)
                attrs["color"] = "#006064"
            elif "reclaimer" in node.id:
                attrs["fillcolor"] = "#b2dfdb"  # Teal (Broker)
                attrs["color"] = "#004d40"
            elif "observer" in node.id:
                attrs["fillcolor"] = "#e1bee7"  # Purple (Observability)
                attrs["color"] = "#4a148c"
            elif "gate" in node.id:
                attrs["fillcolor"] = "#fff3e0"  # Orange Tint (Control)
                attrs["color"] = "#e65100"

        return attrs
~~~~~

### 下一步建议
我们已经同步了可视化工具的语义模型。接下来建议运行一个包含资源分配和二元体任务的完整编译流程，并导出 `.dot` 文件进行视觉检查，确保生成的图表拓扑清晰且符合颜色预期。
