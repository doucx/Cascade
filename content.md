好的，我们已采纳新战略。

现在开始执行修正后的 **阶段 5.A.1：在 IR 和拓扑中建立信令原语**。

此计划将为我们的静态拓扑引入“通道极化”的概念，在 `cascade-spec` 中定义 `DATA` 和 `SIGNAL` 两种通道类型，并更新 `cascade-compiler` 后端，使其能够根据前端 IR 生成带有正确极化属性的物理通道。

## [WIP] feat(spec): 引入 DATA 和 SIGNAL 通道极化

### 用户需求
根据我们刚刚确定的新战略，执行“路线图：全对称物理引擎与编译器重构”中修正后的阶段 5.A.1。核心任务是在静态拓扑规范中引入通道极化（`ChannelKind`），并使编译器后端能够生成带有正确极化类型的通道。

### 评论
这是实现“全对称架构”一个至关重要的基础步骤。通过在静态拓扑层（`ChannelDef`）就明确区分“物质传递”（DATA）和“时序触发”（SIGNAL），我们为后续物理引擎（`Reactor`）实现更精确、更解耦的“双势垒”激活模型提供了不可或缺的静态信息。这从根本上避免了语义耦合，为构建一个真正健壮的物理模拟器奠定了基础。

### 目标
1.  在 `cascade-spec` 中，更新 `ChannelDef` 数据类，增加一个 `kind: ChannelKind` 字段，用于区分 `DATA` 和 `SIGNAL` 通道。
2.  重构 `cascade-compiler` 的 `Backend`，使其在将 `GraphIR` 编译为 `BipartiteGraph` 时：
    *   将 `EdgeKind.DATA` 和 `EdgeKind.JUMP` 的边所对应的通道，其 `ChannelDef.kind` 设为 `ChannelKind.DATA`。
    *   **新增逻辑**来处理 `EdgeKind.CONTROL` 的边，并将其对应的通道 `ChannelDef.kind` 设为 `ChannelKind.SIGNAL`。

### 基本原理
我们首先修改 `cascade-spec` 中的 `topology.py`，因为它是定义静态数据结构的“纲”。通过在这里引入 `ChannelKind`，我们确立了整个系统都必须遵守的契约。

随后，我们使用 `write_file` 更新 `cascade-compiler` 的 `backend.py`。选用 `write_file` 是因为修改点分散在文件的多个位置（新增 `import`、修改两个现有方法、增加一个新方法并更新 `build` 调用流程），一次性写入能更清晰、更原子化地完成重构。这个重构将使编译器后端完全适配新的通道极化规范，确保生成的物理蓝图是完备和正确的。

### 标签
#intent/architect #intent/build #flow/ready #priority/high #comp/compiler #comp/interfaces #concept/state #scope/api #ai/instruct #task/domain/compiler #task/object/channel-polarity #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: [Spec] 在 ChannelDef 中定义通道类型

首先，我们修改 `cascade-spec` 包，为 `ChannelDef` 引入 `ChannelKind` 枚举和 `kind` 字段，这是所有后续工作的基础。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
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
    """
    Represents a data storage slot in the physical bipartite graph.
    This is the "Noun" or the container. It tracks its origin.
    """
    current_data_slot_hash: str
    name: str
    producer_node_instance_hash: str


@dataclass(frozen=True)
class PhysicsTerminatorNode:
    """
    A special Functional Node that, when fired, triggers the shutdown of the Reactor.
    It represents the "End of Time" for a run.
    """
    current_node_instance_hash: str
    name: str
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PhysicsEmitterNode:
    """
    A specialized node that projects internal tokens to the external world.
    It acts as a boundary bridge.
    """
    current_node_instance_hash: str
    name: str
    sink_id: str  # Identifier for the external sink (e.g. "client_response")
    inputs: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ChannelDef:
    """
    Defines a static, directed connection from a FuncNode's output port
    to a DataNode's input slot, with routing logic.
    """
    source_node_instance_hash: str
    target_data_slot_hash: str
    port_name: str
    tag_filter: str = "default"


from typing import Any

@dataclass(frozen=True)
class BipartiteGraph:
~~~~~
~~~~~python.new
from dataclasses import dataclass, field
from enum import Enum
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
    """
    Represents a data storage slot in the physical bipartite graph.
    This is the "Noun" or the container. It tracks its origin.
    """
    current_data_slot_hash: str
    name: str
    producer_node_instance_hash: str


@dataclass(frozen=True)
class PhysicsTerminatorNode:
    """
    A special Functional Node that, when fired, triggers the shutdown of the Reactor.
    It represents the "End of Time" for a run.
    """
    current_node_instance_hash: str
    name: str
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PhysicsEmitterNode:
    """
    A specialized node that projects internal tokens to the external world.
    It acts as a boundary bridge.
    """
    current_node_instance_hash: str
    name: str
    sink_id: str  # Identifier for the external sink (e.g. "client_response")
    inputs: Dict[str, str] = field(default_factory=dict)


class ChannelKind(str, Enum):
    """
    Defines the physical nature of a channel, separating data flow from control flow.
    """
    DATA = "DATA"      # Transports a payload. Contributes to 'data potential'.
    SIGNAL = "SIGNAL"  # Transports only an activation signal. Contributes to 'control potential'.


@dataclass(frozen=True)
class ChannelDef:
    """
    Defines a static, directed connection from a FuncNode's output port
    to a DataNode's input slot, with routing logic.
    """
    source_node_instance_hash: str
    target_data_slot_hash: str
    port_name: str
    tag_filter: str = "default"
    kind: ChannelKind = ChannelKind.DATA


from typing import Any

@dataclass(frozen=True)
class BipartiteGraph:
~~~~~

#### Acts 2: [Compiler] 使后端支持生成极化通道

现在，我们重构编译器后端，使其能够根据 IR 中边的类型（`EdgeKind`）生成具有正确极化（`ChannelKind`）的 `ChannelDef`。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python
import hashlib
from typing import List, Dict, Any

from cascade.spec.ir.models import GraphIR, EdgeKind
from cascade.spec.topology import (
    BipartiteGraph,
    PhysicsFuncNode,
    PhysicsDataNode,
    ChannelDef,
    ChannelKind,
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
        self._initial_values = {}
        
        # Pass 1: Instantiate Nodes (Func & Data) and Output Channels
        for node_ir in self._graph.nodes:
            self._process_node(node_ir)

        # Pass 2: Wire Inputs based on standard data Edges
        self._process_data_edges()
        
        # Pass 3: Wire Control Edges (e.g., from .run_if) as SIGNAL channels
        self._process_control_edges()

        # Pass 4: Wire Jumps (Feedback Loops) as DATA channels
        self._process_jumps()

        return BipartiteGraph(
            func_nodes=self._func_nodes,
            data_nodes=self._data_nodes,
            channels=self._channels,
            initial_values=self._initial_values,
        )

    def _process_node(self, node_ir):
        func_hash = node_ir.current_node_instance_hash
        
        f_node = PhysicsFuncNode(
            current_node_instance_hash=func_hash,
            name=node_ir.definition.name,
            inputs={} 
        )
        self._func_nodes[func_hash] = f_node

        for i, val in enumerate(node_ir.args):
            self._process_literal(f_node, str(i), val)
        
        for k, val in node_ir.kwargs.items():
            self._process_literal(f_node, k, val)

        data_slot_hash = self._compute_data_slot_hash(func_hash, "result")
        self._func_output_map[func_hash] = data_slot_hash

        d_node = PhysicsDataNode(
            current_data_slot_hash=data_slot_hash,
            name=f"{node_ir.definition.name}.output",
            producer_node_instance_hash=func_hash
        )
        self._data_nodes[data_slot_hash] = d_node

        channel = ChannelDef(
            source_node_instance_hash=func_hash,
            target_data_slot_hash=data_slot_hash,
            port_name="result",
            tag_filter="default",
            kind=ChannelKind.DATA  # Explicitly a DATA channel
        )
        self._channels.append(channel)

    def _process_literal(self, f_node, arg_name, value):
        const_hash = self._compute_const_hash(value)
        
        if const_hash not in self._data_nodes:
            d_node = PhysicsDataNode(
                current_data_slot_hash=const_hash,
                name=f"const_{const_hash[:8]}",
                producer_node_instance_hash="const"
            )
            self._data_nodes[const_hash] = d_node
            self._initial_values[const_hash] = value
            
        f_node.inputs[arg_name] = const_hash

    def _process_data_edges(self):
        for edge in self._graph.edges:
            if edge.kind != EdgeKind.DATA:
                continue

            source_func_hash = edge.source_node_instance_hash
            target_func_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg

            source_data_hash = self._func_output_map.get(source_func_hash)
            
            if not source_data_hash:
                raise RuntimeError(f"Source node {source_func_hash} not found in output map")

            target_func_node = self._func_nodes.get(target_func_hash)
            if target_func_node:
                target_func_node.inputs[arg_name] = source_data_hash

    def _process_control_edges(self):
        self._create_signal_channels(EdgeKind.CONTROL, ChannelKind.SIGNAL)

    def _process_jumps(self):
        # Jumps are data-carrying control flow, so they use DATA channels.
        self._create_signal_channels(EdgeKind.JUMP, ChannelKind.DATA)

    def _create_signal_channels(self, edge_kind: EdgeKind, channel_kind: ChannelKind):
        for edge in self._graph.edges:
            if edge.kind != edge_kind:
                continue

            source_func_hash = edge.source_node_instance_hash
            target_func_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg
            
            target_func_node = self._func_nodes.get(target_func_hash)
            if not target_func_node:
                raise RuntimeError(f"Target node {target_func_hash} for {edge_kind.name} edge not found")

            # A control/jump edge needs a dedicated input slot on the target.
            # If one already exists (from a literal or other edge), we reuse it.
            # Otherwise, we create one.
            if arg_name in target_func_node.inputs:
                target_data_hash = target_func_node.inputs[arg_name]
            else:
                target_data_hash = self._compute_data_slot_hash(target_func_hash, f"input_{arg_name}")
                if target_data_hash not in self._data_nodes:
                    d_node = PhysicsDataNode(
                        current_data_slot_hash=target_data_hash,
                        name=f"{target_func_node.name}.in.{arg_name}",
                        producer_node_instance_hash="external"
                    )
                    self._data_nodes[target_data_hash] = d_node
                target_func_node.inputs[arg_name] = target_data_hash

            # Create the Channel
            tag = edge.case_key or "default"
            channel = ChannelDef(
                source_node_instance_hash=source_func_hash,
                target_data_slot_hash=target_data_hash,
                port_name="result", # Signals/Jumps use the default output port
                tag_filter=tag,
                kind=channel_kind
            )
            self._channels.append(channel)

    def _compute_const_hash(self, value: Any) -> str:
        raw = f"const:{repr(value)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _compute_data_slot_hash(self, producer_hash: str, port: str) -> str:
        raw = f"{producer_hash}:{port}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
~~~~~

### 下一步建议
我们已经成功地在静态拓扑层面引入了通道极化的概念。这是实现我们宏大物理模型的第一块基石。

下一步，我们将进入 **阶段 5.A.2**：**在 `cascade-vm` 中使 `Reactor` 能够理解并执行新的双势垒物理规则**。这将是让我们的物理引擎“活”起来的关键一步。
