这是一个 **GREEN** 步骤。

为了实现编译器的重构，我需要执行以下操作：

1.  **增强 Spec**: 修改 `cascade.spec.topology.PhysicsFuncNode`，为其添加 `inputs` 字段。这是表达数据流依赖（即二分图中的 D -> F 连接）所必需的。为了不破坏现有测试，我们将提供一个默认值。
2.  **重写 Backend**: 完全重写 `cascade.compiler.backend`。移除旧的指令生成逻辑，替换为拓扑构建逻辑。

## [WIP] feat: 实现 Backend 拓扑生成器

### 用户需求
将 `Backend` 从指令集生成器重构为物理拓扑生成器。

### 评论
我在 `PhysicsFuncNode` 中添加了一个 `inputs` 字段。虽然目前的测试用例没有显式断言这一点，但这对于构建一个连通的图是逻辑上必须的。通过使用 `default_factory=dict`，我们保持了向后兼容性，不会破坏 Phase 3.1 的 Schema 测试。

### 目标
1.  修改 `packages/cascade-spec/src/cascade/spec/topology.py`。
2.  重写 `packages/cascade-compiler/src/cascade/compiler/backend.py`。

### 基本原理
**Backend 逻辑**:
1.  **节点映射**: 遍历 `GraphIR` 的节点。对于每个节点，生成一个对应的 `PhysicsFuncNode` 和一个默认的输出 `PhysicsDataNode`。
2.  **通道创建**: 为每个节点创建一条从 `FuncNode` 到其输出 `DataNode` 的 `ChannelDef`。
3.  **输入连线**: 遍历 `GraphIR` 的边。对于每条边 `A -> B (arg)`，找到 A 对应的输出 `DataNode`，并将其哈希记录在 B 的 `inputs` 字典中。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #concept/topology #scope/core #ai/instruct #task/domain/compiler #task/object/backend #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 增强 Spec 以支持输入连线

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class PhysicsFuncNode:
    """
    Represents a computational instance in the physical bipartite graph.
    This is the "Verb" or the transformer.
    """
    current_node_instance_hash: str
    name: str


@dataclass(frozen=True)
class PhysicsDataNode:
~~~~~
~~~~~python.new
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class PhysicsFuncNode:
    """
    Represents a computational instance in the physical bipartite graph.
    This is the "Verb" or the transformer.
    """
    current_node_instance_hash: str
    name: str
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PhysicsDataNode:
~~~~~

#### Acts 2: 重写 Backend 实现拓扑构建

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python
import hashlib
from typing import List, Dict

from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import (
    BipartiteGraph,
    PhysicsFuncNode,
    PhysicsDataNode,
    ChannelDef,
)


class Backend:
    """
    Compiler Backend: Transforms GraphIR into a static BipartiteGraph topology.
    """

    @staticmethod
    def compile(graph: GraphIR) -> BipartiteGraph:
        builder = _TopologyBuilder(graph)
        return builder.build()


class _TopologyBuilder:
    def __init__(self, graph: GraphIR):
        self._graph = graph
        self._func_nodes: Dict[str, PhysicsFuncNode] = {}
        self._data_nodes: Dict[str, PhysicsDataNode] = {}
        self._channels: List[ChannelDef] = []
        
        # Helper map: FuncNode Hash -> Default Output DataNode Hash
        self._func_output_map: Dict[str, str] = {}

    def build(self) -> BipartiteGraph:
        # Pass 1: Instantiate Nodes (Func & Data) and Output Channels
        for node_ir in self._graph.nodes:
            self._process_node(node_ir)

        # Pass 2: Wire Inputs based on Edges
        self._process_edges()

        return BipartiteGraph(
            func_nodes=self._func_nodes,
            data_nodes=self._data_nodes,
            channels=self._channels,
        )

    def _process_node(self, node_ir):
        func_hash = node_ir.current_node_instance_hash
        
        # 1. Create PhysicsFuncNode
        # Inputs will be populated in Pass 2
        f_node = PhysicsFuncNode(
            current_node_instance_hash=func_hash,
            name=node_ir.definition.name,
            inputs={} 
        )
        self._func_nodes[func_hash] = f_node

        # 2. Create Default Output DataNode (Slot)
        # We assume a single output port named "result" for now.
        # The data slot hash is deterministically derived from the producer + port.
        data_slot_hash = self._compute_data_slot_hash(func_hash, "result")
        self._func_output_map[func_hash] = data_slot_hash

        d_node = PhysicsDataNode(
            current_data_slot_hash=data_slot_hash,
            name=f"{node_ir.definition.name}.output",
            producer_node_instance_hash=func_hash
        )
        self._data_nodes[data_slot_hash] = d_node

        # 3. Create Output Channel (Func -> Data)
        channel = ChannelDef(
            source_node_instance_hash=func_hash,
            target_data_slot_hash=data_slot_hash,
            port_name="result",
            tag_filter="default" # Default filter
        )
        self._channels.append(channel)

    def _process_edges(self):
        for edge in self._graph.edges:
            # Source of the edge is a FuncNode (in IR)
            source_func_hash = edge.source_node_instance_hash
            target_func_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg

            # Find the DataNode produced by the source FuncNode
            # In IR, edges are direct Func->Func. 
            # In Topology, we must route through the DataNode.
            source_data_hash = self._func_output_map.get(source_func_hash)
            
            if not source_data_hash:
                # Should not happen in valid IR
                raise RuntimeError(f"Source node {source_func_hash} not found in output map")

            # Link: Target FuncNode input 'arg_name' <- Source DataNode
            target_func_node = self._func_nodes.get(target_func_hash)
            if target_func_node:
                # Note: PhysicsFuncNode is frozen, but we are in construction phase.
                # Since dataclasses are frozen=True, we technically cannot mutate 'inputs'.
                # However, 'inputs' is a mutable dict (default_factory), so we CAN mutate its content
                # unless we made it immutable/frozen too. Standard dataclass behavior allows 
                # mutating the mutable content of a frozen field.
                target_func_node.inputs[arg_name] = source_data_hash

    def _compute_data_slot_hash(self, producer_hash: str, port: str) -> str:
        raw = f"{producer_hash}:{port}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
~~~~~

### 下一步建议
我们已经完成了后端的基础重构。现在它能够生成二分图结构。

接下来的步骤是 **阶段 3.3：[TDD] 编译字面量与扇出依赖**。
我们需要处理一种特殊情况：字面量输入（Literal Inputs）。
在二分图模型中，字面量也必须存在于 `DataNode` 中才能被 `FuncNode` 消费。这意味着编译器必须为字面量“预创建”并“预填充”数据节点。

我将修改测试 `test_backend_topology.py`，添加关于字面量处理的用例，这将再次使测试变红。
