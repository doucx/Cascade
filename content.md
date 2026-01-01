好的，我们继续执行路线图。现在，我们将构建 `Builder`，它负责将 `Expander` 生成的多个三连体子图，根据逻辑依赖关系，组装成一个完整、可执行的物理二分图，并为每个子图注入标准的观测旁路。

## [WIP] feat(compiler): 实现 Builder 用于连接三连体与观测旁路

### 用户需求
根据路线图 **任务 3.2** 和 **任务 3.3**，实现一个 `Builder` 类，负责：
1.  将 `GraphIR` 中定义的逻辑依赖关系，转换为物理 `Channel`，连接相应的 `Stainer` 和 `Bleacher` 节点。
2.  为每个任务三连体自动创建到全局生命周期数据节点 (`D_life`) 的旁路连接，以实现可观测性。

### 评论
这是将“微观物理”与“宏观逻辑”连接起来的关键一步。`Expander` 创造了独立的“粒子”（三连体），而 `Builder` 则根据蓝图将这些粒子编织成宇宙的“力场”（最终的拓扑图）。旁路插桩的自动化是 “Cascade 3.0” 全息可观测性承诺的核心，确保了观测行为的零侵入性和一致性。

### 目标
1.  **修改 `Expander`**: 为 `BleachNode` 和 `StainNode` 增加专门的 `obs_output` 端口，用于发射生命周期事件。
2.  **创建 `Builder` 类**: 在 `cascade-compiler/src/cascade/compiler/backend/builder.py` 中实现。
3.  **实现数据流布线**: `Builder` 必须能解析 `NodeIR.inputs` 中的节点间引用，并创建从源节点 `Stainer` 到目标节点 `Bleacher` 的 `Channel`。
4.  **实现观测旁路布线**: `Builder` 必须创建一个全局的 `D_life` 节点，并将每个三连体的 `Bleacher` 和 `Stainer` 的 `obs_output` 端口连接到它。
5.  **编写集成测试**: 验证一个包含两个依赖节点的 `GraphIR` 能被正确地编译和连接。

### 基本原理
`Builder` 是编译器后端的总指挥。它首先委托 `Expander` 将所有逻辑节点物化为物理子图。然后，它作为一个“布线工程师”，遍历 `GraphIR` 中的依赖关系，在这些独立的子图之间架设桥梁（`Channel`）。同时，它还扮演着“仪表工程师”的角色，为每个子图强制安装标准化的监控探针，将它们的生命周期信号汇集到统一的 `D_life` 总线上。

### 标签
#intent/build #flow/ready #priority/high #comp/compiler #concept/topology #concept/observability #scope/core #task/domain/compiler #task/object/builder #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 为三连体节点添加观测端口

我们首先修改 `Expander`，为 `BleachNode` 和 `StainNode` 添加 `obs_output` 端口。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        f_pre = BleachNode(
            id=f_pre_id,
            name=f"Bleach({node_ir.name})",
            input_ports=bleacher_inputs,
            output_ports={
                "worker_input": "Dict", 
                "trace_output": "TraceCtx"
            }
        )
~~~~~
~~~~~python.new
        f_pre = BleachNode(
            id=f_pre_id,
            name=f"Bleach({node_ir.name})",
            input_ports=bleacher_inputs,
            output_ports={
                "worker_input": "Dict",
                "trace_output": "TraceCtx",
                "obs_output": "Event",  # Port for start event
            },
        )
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
        f_post = StainNode(
            id=f_post_id,
            name=f"Stain({node_ir.name})",
            input_ports={"worker_result": "Any", "trace_input": "TraceCtx"},
            output_ports={
                "output": "Token",
                "obs_output": "Event",  # Port for end event
            },
        )
~~~~~

#### Acts 2: 实现 Builder

现在，我们创建 `Builder` 类，它将负责整个图的构建和布线过程。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python
from typing import Dict

from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode
from .expander import Expander, SubGraph


class Builder:
    """
    The master assembler for the physical graph.
    It takes a logical GraphIR, expands each node into a Triad,
    and then wires them together along with observability sidecars.
    """

    def __init__(self):
        self._expander = Expander()

    def build(self, graph_ir: GraphIR) -> BipartiteGraph:
        physical_graph = BipartiteGraph()
        
        # 1. Create the global observability sidecar node (D_life)
        d_life = PhysicsDataNode(id="global_d_life", name="LifecycleBus")
        physical_graph.nodes[d_life.id] = d_life
        
        # 2. Expand all logical nodes into physical subgraphs
        subgraphs: Dict[str, SubGraph] = {}
        for node_ir in graph_ir.nodes:
            subgraph = self._expander.expand_node(node_ir)
            subgraphs[node_ir.id] = subgraph
            
            # Add all nodes from the subgraph to the main graph
            physical_graph.nodes.update(subgraph.nodes)
            # Add all internal channels from the subgraph
            physical_graph.channels.extend(subgraph.channels)
            
            # 3. Wire observability sidecars for each subgraph
            # F_pre (start) -> D_life
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.bleacher.id,
                    source_port="obs_output",
                    target_node_id=d_life.id,
                )
            )
            # F_post (end) -> D_life
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.stainer.id,
                    source_port="obs_output",
                    target_node_id=d_life.id,
                )
            )
            
        # 4. Wire data dependencies between subgraphs
        for node_ir in graph_ir.nodes:
            target_subgraph = subgraphs[node_ir.id]
            for arg_name, source_ref in node_ir.inputs.items():
                # We only handle inter-node references here. Literals are handled later.
                if isinstance(source_ref, str) and source_ref in subgraphs:
                    source_subgraph = subgraphs[source_ref]
                    
                    # Connect: Source.Stainer -> Target.Bleacher
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=target_subgraph.bleacher.id,
                            # Note: The target port is implicitly the 'arg_name',
                            # which the Bleacher is designed to handle.
                        )
                    )

        return physical_graph
~~~~~

#### Acts 3: 导出 Builder

将 `Builder` 添加到包的 `__init__.py` 中。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/__init__.py
~~~~~
~~~~~python.old
# Backend package for Cascade Compiler
# Responsible for converting IR into Physical Bipartite Graphs.
~~~~~
~~~~~python.new
from .builder import Builder

__all__ = ["Builder"]
~~~~~

#### Acts 4: 编写 Builder 的单元测试

最后，我们创建一个测试来验证 `Builder` 的布线逻辑是否正确。

~~~~~act
write_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python
import pytest
from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.compiler.backend.builder import Builder

@pytest.fixture
def sample_graph_ir():
    """
    Creates a GraphIR for a two-node workflow:
    task_a -> task_b
    """
    fp = Fingerprint.from_dict({"canonical_code_structure_hash": "abc"})
    task_a_def = TaskDef(name="task_a", args=[], fingerprint=fp)
    task_b_def = TaskDef(
        name="task_b",
        args=[ArgumentDef("data", ArgumentKind.POSITIONAL_OR_KEYWORD)],
        fingerprint=fp
    )
    
    node_a = NodeIR(id="node_a", name="NodeA", task=task_a_def)
    node_b = NodeIR(
        id="node_b",
        name="NodeB",
        task=task_b_def,
        inputs={"data": "node_a"} # task_b.data comes from node_a
    )
    
    return GraphIR(nodes=[node_a, node_b])


def test_builder_expands_and_wires_nodes(sample_graph_ir):
    builder = Builder()
    graph = builder.build(sample_graph_ir)
    
    # Assert nodes: 2 triads (6 nodes each) + 1 global D_life = 13 nodes
    assert len(graph.nodes) == 13
    assert "global_d_life" in graph.nodes
    assert "node_a_stain" in graph.nodes
    assert "node_b_bleach" in graph.nodes
    
    # Assert channels
    # 2 triads (6 channels each) = 12
    # 1 data dependency channel = 1
    # 2 triads * 2 obs channels each = 4
    # Total = 12 + 1 + 4 = 17
    assert len(graph.channels) == 17
    
    # 1. Test data dependency wiring
    data_channel = next(
        c for c in graph.channels 
        if c.source_node_id == "node_a_stain" and c.target_node_id == "node_b_bleach"
    )
    assert data_channel is not None
    assert data_channel.source_port == "output"
    
    # 2. Test observability wiring
    d_life_id = "global_d_life"
    obs_channels = [c for c in graph.channels if c.target_node_id == d_life_id]
    
    assert len(obs_channels) == 4 # 2 starts, 2 ends
    
    source_ids = {c.source_node_id for c in obs_channels}
    assert "node_a_bleach" in source_ids
    assert "node_a_stain" in source_ids
    assert "node_b_bleach" in source_ids
    assert "node_b_stain" in source_ids
~~~~~

### 下一步建议
我们已经成功地将一个高级的、逻辑上的 `GraphIR` 编译成了一个完整的、包含数据流和观测流的物理二分图。

根据路线图，下一步是 **阶段 4：控制流与资源 (Advanced Topology)**。我们将首先从 **任务 4.1：实现资源背压 ($D_{res}$)** 开始，修改 `Builder` 以支持自动连接到全局资源槽位，从而在拓扑层面实现并发控制。
