好的，我们进入 **Phase 3.3 GREEN** 阶段。

正如预期，测试失败了，因为 `Backend` 还没有处理字面量。

我将执行以下操作：
1.  **Spec Update**: 在 `BipartiteGraph` 中添加 `initial_values: Dict[str, Any]` 字段。
2.  **Backend Implementation**: 在 `_TopologyBuilder` 中添加逻辑，扫描 `NodeIR` 的 `args` 和 `kwargs`。如果发现不是边（即不是来自其他节点的依赖），则将其视为字面量，创建常量 `DataNode`，并将其值存入 `initial_values`。

## [WIP] feat: 实现字面量编译和 BipartiteGraph.initial_values

### 用户需求
使 `Backend` 能够正确编译字面量参数，并将它们存储在 `BipartiteGraph` 的 `initial_values` 中，同时确保扇出依赖正确共享数据节点。

### 评论
通过在 `BipartiteGraph` 中引入 `initial_values`，我们有效地将图的“静态结构”与“初始状态”结合在了一起。这非常符合物理引擎的隐喻：我们在构建反应堆的同时，也装载了初始燃料（常量）。

### 目标
1.  更新 `packages/cascade-spec/src/cascade/spec/topology.py`。
2.  更新 `packages/cascade-compiler/src/cascade/compiler/backend.py`。

### 基本原理
**字面量处理逻辑**:
对于每个 `NodeIR`，遍历其 `args` 和 `kwargs`。如果某个参数没有对应的 `EdgeIR` 指向它，那么它就是一个字面量。
1.  生成一个唯一的哈希（基于值的哈希）。
2.  创建一个 `PhysicsDataNode`，标记为 `producer="const"`。
3.  将该 `DataNode` 的哈希作为输入连接到 `PhysicsFuncNode`。
4.  将字面量值存入 `initial_values[data_hash]`。

### 标签
#intent/build #flow/ready #priority/high #comp/compiler #concept/state #scope/core #ai/instruct #task/domain/compiler #task/object/backend #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 更新 Spec 添加 initial_values

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class BipartiteGraph:
    """
    The static, physical blueprint of the computation network, output by the compiler.
    """
    func_nodes: Dict[str, PhysicsFuncNode]
    data_nodes: Dict[str, PhysicsDataNode]
    channels: List[ChannelDef]
~~~~~
~~~~~python.new
from typing import Any

@dataclass(frozen=True)
class BipartiteGraph:
    """
    The static, physical blueprint of the computation network, output by the compiler.
    """
    func_nodes: Dict[str, PhysicsFuncNode]
    data_nodes: Dict[str, PhysicsDataNode]
    channels: List[ChannelDef]
    # Map data_slot_hash -> literal value for constant inputs
    initial_values: Dict[str, Any] = field(default_factory=dict)
~~~~~

#### Acts 2: 更新 Backend 实现字面量处理

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
    def build(self) -> BipartiteGraph:
        self._initial_values = {}
        
        # Pass 1: Instantiate Nodes (Func & Data) and Output Channels
        # Also process literal inputs in this pass
        for node_ir in self._graph.nodes:
            self._process_node(node_ir)

        # Pass 2: Wire Inputs based on Edges (Dependencies)
        # This will OVERWRITE any literal inputs if an edge exists for the same arg
        # (Though IR shouldn't have both literal and edge for same arg)
        self._process_edges()

        return BipartiteGraph(
            func_nodes=self._func_nodes,
            data_nodes=self._data_nodes,
            channels=self._channels,
            initial_values=self._initial_values,
        )

    def _process_node(self, node_ir):
        func_hash = node_ir.current_node_instance_hash
        
        # 1. Create PhysicsFuncNode
        f_node = PhysicsFuncNode(
            current_node_instance_hash=func_hash,
            name=node_ir.definition.name,
            inputs={} 
        )
        self._func_nodes[func_hash] = f_node

        # 1.5 Process Literals (args/kwargs)
        # Convert args to position-based names ("0", "1", ...)
        for i, val in enumerate(node_ir.args):
            self._process_literal(f_node, str(i), val)
        
        for k, val in node_ir.kwargs.items():
            self._process_literal(f_node, k, val)

        # 2. Create Default Output DataNode (Slot)
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
            tag_filter="default" 
        )
        self._channels.append(channel)

    def _process_literal(self, f_node, arg_name, value):
        # Create a Constant DataNode for this value
        # Hash based on value repr to allow deduplication of same constants
        const_hash = self._compute_const_hash(value)
        
        if const_hash not in self._data_nodes:
            d_node = PhysicsDataNode(
                current_data_slot_hash=const_hash,
                name=f"const_{const_hash[:8]}",
                producer_node_instance_hash="const"
            )
            self._data_nodes[const_hash] = d_node
            self._initial_values[const_hash] = value
            
        # Wire it up
        f_node.inputs[arg_name] = const_hash

    def _process_edges(self):
        for edge in self._graph.edges:
            # Source of the edge is a FuncNode (in IR)
            source_func_hash = edge.source_node_instance_hash
            target_func_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg

            # Find the DataNode produced by the source FuncNode
            source_data_hash = self._func_output_map.get(source_func_hash)
            
            if not source_data_hash:
                raise RuntimeError(f"Source node {source_func_hash} not found in output map")

            # Link: Target FuncNode input 'arg_name' <- Source DataNode
            target_func_node = self._func_nodes.get(target_func_hash)
            if target_func_node:
                target_func_node.inputs[arg_name] = source_data_hash

    def _compute_const_hash(self, value: Any) -> str:
        # Simple content hashing for literals
        # Warning: repr() isn't stable for all types, but good enough for primitives
        # In production, use a better serializer
        raw = f"const:{repr(value)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _compute_data_slot_hash(self, producer_hash: str, port: str) -> str:
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
import hashlib
from typing import List, Dict

from cascade.spec.ir.models import GraphIR
~~~~~
~~~~~python.new
import hashlib
from typing import List, Dict, Any

from cascade.spec.ir.models import GraphIR
~~~~~

### 下一步建议
我们已经完成了 **Phase 3.3**。
Backend 现在支持基本的线性拓扑、扇出拓扑以及字面量注入。

接下来的步骤是 **阶段 3.4：[TDD] 编译 TCO (Tail-Call Optimization) 循环**。
这将是本系列重构中最具挑战性也最激动人心的一步。我们将实现“物理层面的循环”，即通过反馈通道（Feedback Channel）来实现零开销 TCO。

我将创建一个新的测试文件 `packages/cascade-compiler/tests/unit/test_backend_tco.py`，专门用于驱动这一特性的实现。
