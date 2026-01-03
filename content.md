## [WIP] feat(compiler): 实施 Phase 1 基础定律验证

### 用户需求
实施 GraphValidator Phase 1：基础定律验证。
核心目标是确保生成的物理图在拓扑上绝对符合“全对称计算物理场”的公理：二分图规则和端口连接性规则。这将作为调试当前死锁问题的第一道防线。

### 评论
“先保真，后加速”原则的延伸。验证器就是“保真”的自动化守护者。通过静态分析物理图，我们可以立即捕获到 `Builder` 中可能存在的、微妙的布线错误，而无需等待运行时 `KeyError`。

### 目标
1.  创建 `cascade-compiler/src/cascade/compiler/backend/validator.py`。
2.  定义 `GraphValidationError` 异常。
3.  实现 `GraphValidator` 类及其核心方法：
    *   `validate(graph, graph_ir)`: 入口点。
    *   `_check_bipartite_rule(graph)`: 确保 Func <-> Data 连接。
    *   `_check_port_connectivity(graph)`: 确保所有连线指向的端口是真实存在的。
4.  在 `Builder.build` 方法末尾集成验证器。

### 基本原理
*   **二分图公理**: `type(source) != type(target)`。
*   **接口契约**: 物理节点在声明时定义了 `input_ports` 和 `output_ports`。连线必须严格遵守此契约。

### 标签
#intent/build #flow/ready #priority/high #comp/compiler #concept/validation #scope/core #ai/instruct #task/domain/compiler #task/object/validator #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建 Validator

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/validator.py
~~~~~
~~~~~python
from typing import Dict
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode, PhysicsFuncNode, PhysicsNode
from cascade.spec.ir.models import GraphIR


class GraphValidationError(ValueError):
    pass


class GraphValidator:
    def validate(self, graph: BipartiteGraph, graph_ir: GraphIR) -> None:
        """
        Runs all registered checks. Raises GraphValidationError on failure.
        """
        self._check_node_integrity(graph)
        self._check_bipartite_rule(graph)
        self._check_port_connectivity(graph)

    def _check_node_integrity(self, graph: BipartiteGraph) -> None:
        """Ensure all nodes referenced in channels actually exist."""
        for i, channel in enumerate(graph.channels):
            if channel.source_node_id not in graph.nodes:
                raise GraphValidationError(
                    f"Channel #{i} references missing source node '{channel.source_node_id}'"
                )
            if channel.target_node_id not in graph.nodes:
                raise GraphValidationError(
                    f"Channel #{i} references missing target node '{channel.target_node_id}'"
                )

    def _check_bipartite_rule(self, graph: BipartiteGraph) -> None:
        """
        Enforce the Bipartite Graph Rule:
        Channels must only connect DataNode <-> FuncNode.
        DataNode -> DataNode and FuncNode -> FuncNode are FORBIDDEN.
        """
        for i, channel in enumerate(graph.channels):
            src = graph.nodes[channel.source_node_id]
            tgt = graph.nodes[channel.target_node_id]

            src_is_data = isinstance(src, PhysicsDataNode)
            tgt_is_data = isinstance(tgt, PhysicsDataNode)

            if src_is_data == tgt_is_data:
                node_type = "DataNode" if src_is_data else "FuncNode"
                raise GraphValidationError(
                    f"Bipartite rule violated in Channel #{i}: "
                    f"{node_type}('{src.id}') -> {node_type}('{tgt.id}'). "
                    "Connections must be between distinct node types."
                )

    def _check_port_connectivity(self, graph: BipartiteGraph) -> None:
        """
        Ensure all channels connect to valid ports defined on the nodes.
        """
        for i, channel in enumerate(graph.channels):
            src = graph.nodes[channel.source_node_id]
            tgt = graph.nodes[channel.target_node_id]

            # 1. Check Source Port
            if isinstance(src, PhysicsFuncNode):
                if channel.source_port not in src.output_ports:
                    raise GraphValidationError(
                        f"Channel #{i}: Output port '{channel.source_port}' not found "
                        f"on FuncNode '{src.id}'. Available: {list(src.output_ports.keys())}"
                    )
            elif isinstance(src, PhysicsDataNode):
                # DataNodes typically have a generic 'out' behavior,
                # but we can enforce 'out' convention if strictness is desired.
                # For now, we assume any output from DataNode is valid (it's just taking a token).
                pass

            # 2. Check Target Port
            if isinstance(tgt, PhysicsFuncNode):
                if channel.target_port not in tgt.input_ports:
                    raise GraphValidationError(
                        f"Channel #{i}: Input port '{channel.target_port}' not found "
                        f"on FuncNode '{tgt.id}'. Available: {list(tgt.input_ports.keys())}"
                    )
            elif isinstance(tgt, PhysicsDataNode):
                # DataNodes typically receive on 'in'.
                if channel.target_port != "in":
                    raise GraphValidationError(
                        f"Channel #{i}: DataNode '{tgt.id}' expects input on port 'in', "
                        f"got '{channel.target_port}'."
                    )
~~~~~

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/validator.stitcher.yaml
~~~~~
~~~~~yaml
"GraphValidator": |-
  Validates the physical integrity of a generated BipartiteGraph.
  Ensures compliance with physical laws (Bipartite Rule) and structural correctness (Port Connectivity).
"GraphValidator.validate": |-
  Main entry point. Runs all checks.
"GraphValidationError": |-
  Raised when the graph violates physical laws or structural rules.
~~~~~

#### Acts 2: 集成到 Builder

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
from cascade.spec.ports import PortDef, PortRole, PortName
from cascade.std.resource.discrete import DiscreteLedger
from .expander import Expander, SubGraph
from cascade.compiler.utils.naming import PhysicalIdGenerator


class Builder:
    def __init__(self):
        self._expander = Expander()

    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> BipartiteGraph:
        physical_graph = BipartiteGraph()
~~~~~
~~~~~python.new
from cascade.spec.ports import PortDef, PortRole, PortName
from cascade.std.resource.discrete import DiscreteLedger
from .expander import Expander, SubGraph
from .validator import GraphValidator
from cascade.compiler.utils.naming import PhysicalIdGenerator


class Builder:
    def __init__(self):
        self._expander = Expander()
        self._validator = GraphValidator()

    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> BipartiteGraph:
        physical_graph = BipartiteGraph()
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
                # Stainer -> RelBuffer
                physical_graph.channels.append(
                    Channel(
                        source_node_id=subgraph.stainer.id,
                        source_port=port_name,
                        target_node_id=rel_buffer_id,
                        target_port="in",
                    )
                )

        return physical_graph
~~~~~
~~~~~python.new
                # Stainer -> RelBuffer
                physical_graph.channels.append(
                    Channel(
                        source_node_id=subgraph.stainer.id,
                        source_port=port_name,
                        target_node_id=rel_buffer_id,
                        target_port="in",
                    )
                )

        # Final Validation Step
        self._validator.validate(physical_graph, graph_ir)

        return physical_graph
~~~~~

### 下一步建议
运行测试 `test_resource_backpressure.py`。
我非常有信心，Validator 会立刻抛出一个 `GraphValidationError`，指出我们之前重构中忽略的某个端口名称不匹配或连接错误，而正是这个错误导致了死锁。
