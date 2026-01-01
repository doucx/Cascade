简要回答
我们将首先在 `cascade-spec` 中定义 `NodeIR`，然后在 `cascade-compiler` 中实现 `Expander`，它负责将单个逻辑节点展开为物理三连体（Bleacher -> Worker -> Stainer）及其内部连接。

## [WIP] feat(compiler): 实现 Expander 及三连体展开逻辑

### 用户需求
实现编译器后端的 `Expander` 组件，负责将高层的逻辑节点 (`NodeIR`) 展开为底层的物理节点三连体 ($F_{pre}, F_{worker}, F_{post}$) 及其内部的拓扑结构。

### 评论
这是 "Cascade 3.0" 编译器的核心转换步骤。通过将逻辑节点“炸开”为微观的三连体，我们为实现细粒度的控制（如漂白、染色）和可观测性（旁路）奠定了物理基础。这也遵循了“全对称计算物理场”的理念，即控制逻辑被物化为拓扑结构。

### 目标
1.  在 `cascade-spec` 中补充 `NodeIR` 的定义。
2.  在 `cascade-compiler` 中实现 `SubGraph` 和 `Expander` 类。
3.  实现三连体的生成逻辑，包括：
    *   生成 `BleachNode` ($F_{pre}$)
    *   生成 `PhysicsDataNode` ($D_{worker\_in}$)
    *   生成 `WorkerNode` ($F_{worker}$)
    *   生成 `PhysicsDataNode` ($D_{worker\_out}$)
    *   生成 `PhysicsDataNode` ($D_{trace}$) —— 用于传递上下文
    *   生成 `StainNode` ($F_{post}$)
    *   生成上述节点之间的内部 `Channel`。

### 基本原理
*   **IR 定义**: 编译器需要一个明确的输入契约。
*   **物理展开**: 根据白皮书，任务执行不仅仅是调用函数，还涉及上下文提取（Bleach）和结果封装（Stain）。这些步骤必须被物化为独立的物理节点，以便运行时引擎（Reactor）可以像处理其他节点一样调度它们，而无需特殊逻辑。
*   **内部连线**: 三连体内部是紧密耦合的，Expander 负责建立这些固定的内部连接，对外暴露 Bleacher 的输入端口和 Stainer 的输出端口。

### 标签
#intent/build #flow/draft #priority/high #comp/compiler #concept/topology #scope/core #task/domain/compiler #task/object/expander #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 定义 IR 模型

首先，我们需要定义编译器后端的输入：`NodeIR`。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from cascade.spec.fingerprint import Fingerprint


class ArgumentKind(str, Enum):
    POSITIONAL_ONLY = "POSITIONAL_ONLY"
    POSITIONAL_OR_KEYWORD = "POSITIONAL_OR_KEYWORD"
    VAR_POSITIONAL = "VAR_POSITIONAL"  # *args
    KEYWORD_ONLY = "KEYWORD_ONLY"
    VAR_KEYWORD = "VAR_KEYWORD"  # **kwargs


@dataclass(frozen=True)
class ArgumentDef:
    name: str
    kind: ArgumentKind
    annotation: Optional[str] = None
    default_value_repr: Optional[str] = None


@dataclass(frozen=True)
class TaskDef:
    name: str
    args: List[ArgumentDef]
    # The stable semantic identity of this task definition.
    # Must contain keys like 'canonical_code_structure_hash'.
    fingerprint: Fingerprint
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    # Execution mode (e.g. "blocking", "compute") derived from the task definition
    mode: str = "blocking"


@dataclass(frozen=True)
class NodeIR:
    """
    Intermediate Representation of a Task instantiation in the logical graph.
    This is the input to the Compiler Backend.
    """
    id: str
    """Unique identifier for this node instance (e.g. current_instance_hash)."""
    
    name: str
    """Human-readable name."""
    
    task: TaskDef
    """The definition of the task being invoked."""
    
    inputs: Dict[str, Any] = field(default_factory=dict)
    """
    Mapping of argument names to values. 
    Values can be literals or references to other NodeIR IDs.
    """

@dataclass(frozen=True)
class GraphIR:
    """
    A collection of NodeIRs representing the full logical workflow.
    """
    nodes: List[NodeIR] = field(default_factory=list)
~~~~~

#### Acts 2: 初始化 Backend 包

创建 `cascade-compiler` 的 backend 包结构。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/__init__.py
~~~~~
~~~~~python
# Backend package for Cascade Compiler
# Responsible for converting IR into Physical Bipartite Graphs.
~~~~~

#### Acts 3: 实现 Expander

实现核心的 `Expander` 类，它负责生成 `SubGraph`。我们将严格遵循白皮书中的三连体结构，并加入 $D_{trace}$ 用于元数据传递。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Dict

from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsNode, PhysicsDataNode
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.topology import Channel


@dataclass
class SubGraph:
    """
    A collection of physical nodes and channels that represent a single logical unit
    (e.g., a Triad).
    """
    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    channels: List[Channel] = field(default_factory=list)
    
    # Interface pointers
    bleacher: BleachNode = None
    stainer: StainNode = None


class Expander:
    """
    The 'Big Bang' engine. 
    It expands a single logical NodeIR into a physical Triad SubGraph.
    
    Triad Structure:
        F_pre (Bleacher) --> D_worker_in --> F_worker --> D_worker_out --> F_post (Stainer)
               |                                                              ^
               +---------------------> D_trace -------------------------------+
    """
    
    def expand_node(self, node_ir: NodeIR) -> SubGraph:
        """
        Expands a NodeIR into a physical Triad.
        """
        subgraph = SubGraph()
        
        # 1. Generate IDs for all physical entities
        # We use the logical node ID as a prefix to ensure uniqueness.
        base_id = node_ir.id
        
        f_pre_id = f"{base_id}_bleach"
        d_worker_in_id = f"{base_id}_worker_in"
        f_worker_id = f"{base_id}_worker"
        d_worker_out_id = f"{base_id}_worker_out"
        d_trace_id = f"{base_id}_trace"
        f_post_id = f"{base_id}_stain"
        
        # 2. Create Nodes
        
        # F_pre: The Bleacher
        # It needs input ports matching the Task definition args.
        bleacher_inputs = {arg.name: "Any" for arg in node_ir.task.args}
        f_pre = BleachNode(
            id=f_pre_id,
            name=f"Bleach({node_ir.name})",
            input_ports=bleacher_inputs,
            output_ports={
                "worker_input": "Dict", 
                "trace_output": "TraceCtx"
            }
        )
        
        # D_worker_in: Holds the pure kwargs for the worker
        d_worker_in = PhysicsDataNode(
            id=d_worker_in_id,
            name=f"In({node_ir.name})"
        )
        
        # F_worker: The actual execution logic
        # It conceptually takes *args/**kwargs, but physically takes one 'worker_input' dict
        f_worker = WorkerNode(
            id=f_worker_id,
            name=f"Exec({node_ir.name})",
            input_ports={"worker_input": "Dict"},
            output_ports={"worker_result": "Any"}
        )
        
        # D_worker_out: Holds the raw result
        d_worker_out = PhysicsDataNode(
            id=d_worker_out_id,
            name=f"Out({node_ir.name})"
        )
        
        # D_trace: The wormhole for metadata (start_ts, trace_id)
        d_trace = PhysicsDataNode(
            id=d_trace_id,
            name=f"Trace({node_ir.name})"
        )
        
        # F_post: The Stainer
        f_post = StainNode(
            id=f_post_id,
            name=f"Stain({node_ir.name})",
            input_ports={
                "worker_result": "Any",
                "trace_input": "TraceCtx"
            },
            output_ports={
                "output": "Token"
            }
        )
        
        # Register nodes
        subgraph.nodes = {
            n.id: n for n in [
                f_pre, d_worker_in, f_worker, d_worker_out, d_trace, f_post
            ]
        }
        subgraph.bleacher = f_pre
        subgraph.stainer = f_post
        
        # 3. Create Internal Wiring (Channels)
        
        channels = []
        
        # Path 1: Execution Flow
        # F_pre -> D_worker_in
        channels.append(Channel(f_pre_id, "worker_input", d_worker_in_id))
        # D_worker_in -> F_worker
        channels.append(Channel(d_worker_in_id, "out", f_worker_id)) # Implicit 'out' for DataNode source
        # F_worker -> D_worker_out
        channels.append(Channel(f_worker_id, "worker_result", d_worker_out_id))
        # D_worker_out -> F_post
        channels.append(Channel(d_worker_out_id, "out", f_post_id))
        
        # Path 2: Trace Bypass
        # F_pre -> D_trace
        channels.append(Channel(f_pre_id, "trace_output", d_trace_id))
        # D_trace -> F_post
        channels.append(Channel(d_trace_id, "out", f_post_id))
        
        subgraph.channels = channels
        
        return subgraph
~~~~~

#### Acts 4: 单元测试

编写测试用例验证 `Expander` 是否正确生成了包含 6 个节点和 6 条边的子图。

~~~~~act
write_file
packages/cascade-compiler/tests/unit/backend/test_expander.py
~~~~~
~~~~~python
import pytest
from cascade.spec.ir.models import NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.compiler.backend.expander import Expander
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.physics import PhysicsDataNode

def test_expander_creates_triad_structure():
    # 1. Setup IR
    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(
        name="my_task",
        args=[ArgumentDef("x", ArgumentKind.POSITIONAL_OR_KEYWORD)],
        fingerprint=fp
    )
    node_ir = NodeIR(
        id="node_1",
        name="MyNode",
        task=task_def
    )
    
    # 2. Expand
    expander = Expander()
    subgraph = expander.expand_node(node_ir)
    
    # 3. Assert Nodes
    # We expect 6 nodes: Bleach, Worker, Stain, D_in, D_out, D_trace
    assert len(subgraph.nodes) == 6
    
    bleacher = subgraph.bleacher
    stainer = subgraph.stainer
    
    assert isinstance(bleacher, BleachNode)
    assert isinstance(stainer, StainNode)
    assert bleacher.id == "node_1_bleach"
    assert stainer.id == "node_1_stain"
    
    # Check intermediate nodes
    worker = subgraph.nodes["node_1_worker"]
    assert isinstance(worker, WorkerNode)
    
    d_trace = subgraph.nodes["node_1_trace"]
    assert isinstance(d_trace, PhysicsDataNode)

    # 4. Assert Channels
    # We expect 6 internal channels
    assert len(subgraph.channels) == 6
    
    # Verify connections
    # Bleach -> Trace
    trace_channel = next(c for c in subgraph.channels if c.source_node_id == bleacher.id and c.target_node_id == d_trace.id)
    assert trace_channel.source_port == "trace_output"
    
    # Trace -> Stain
    trace_in_channel = next(c for c in subgraph.channels if c.source_node_id == d_trace.id and c.target_node_id == stainer.id)
    assert trace_in_channel.source_port == "out" # implicit port for data node
~~~~~

### 下一步建议
我们已经完成了单个节点的物理展开。根据路线图，下一步是 **任务 3.2：实现连线逻辑 (Wiring)**。这需要实现 `builder.py` 或 `wiring.py`，负责处理 `GraphIR`，调用 `Expander` 生成多个子图，并根据 IR 中的依赖关系，将上一个三连体的 `Stainer` 连接到下一个三连体的 `Bleacher`。此外，还需要实现旁路观测 ($D_{life}$) 的连接。
