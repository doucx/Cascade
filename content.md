好的，我们开始执行路线图的第一步。

这是实施 `1.1 重构 SubGraph 容器` 的计划。此计划将 `SubGraph` 从一个简单的三联体包装器重构为一个全面的组件容器，为后续的策略迁移奠定数据结构基础。

## [WIP] refactor(compiler): 将 SubGraph 重构为组件容器

### 用户需求

根据架构重构路线图 1.1，需要重构 `cascade/compiler/backend/expander.py` 文件中的 `SubGraph` 数据类。目标是将其扩展为一个结构化的容器，以便能够分类存储除核心三联体之外的所有辅助物理节点（如常量、资源和控制流节点）。

### 评论

这是整个重构工作的关键第一步。通过预先定义好一个能够容纳所有权的、结构清晰的 `SubGraph`，我们为后续从 `WiringPolicy` 剥离出来的 `ExpansionPolicy` 提供了明确的“交付目标”。此举直接解决了审计报告中指出的“物理身份割裂”的核心问题，确保了一个逻辑任务所对应的所有物理节点都能被统一追踪和管理。

### 目标

1.  修改 `packages/cascade-compiler/src/cascade/compiler/backend/expander.py` 文件。
2.  重构 `SubGraph` dataclass 的字段定义和顺序，使其逻辑更清晰。
3.  新增 `constants`, `resources`, 和 `controls` 字典字段，用于分别存储参数、资源和控制流相关的辅助节点。
4.  将核心三联体（`bleacher`, `worker`, `stainer`）的定义放在类的最前面，以突显其核心地位。

### 基本原理

当前的 `SubGraph` 是一个“贫血”模型，只知道核心三联体。所有由 `WiringPolicy` 创建的辅助节点都直接散落在全局物理图中，导致 `SubGraph` 对象在策略执行后立即变得“不完整”和“过时”。

本次重构将 `SubGraph` 提升为一个“富集”模型。它将成为一个逻辑任务其物理形态的**完整清单**。`Expander` 的职责将变为填充这个清单，而 `WiringPolicy` 则利用这个清单进行连接。这种所有权的明确化是实现“关注点分离”和保证架构长期健康的基础。

### 标签

#intent/refine #flow/ready #priority/high #task/domain/compiler #task/object/subgraph #task/action/refactor #task/state/begin #scope/core #ai/instruct

---

### Script

#### Acts 1: 重写 `expander.py` 以更新 `SubGraph` 定义

我们将使用 `write_file` 完整覆盖 `expander.py` 文件，以引入新的 `SubGraph` 结构。除了 `SubGraph` 的定义外，文件的其余部分保持不变。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsNode, PhysicsDataNode
from cascade.spec.physical.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.physical.topology import Channel
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.std.specs import BleacherSpec
from cascade.reflection import PhysicalIdGenerator


@dataclass
class SubGraph:
    # Interface pointers to the core triad
    bleacher: Optional[BleachNode] = None
    worker: Optional[WorkerNode] = None
    stainer: Optional[StainNode] = None

    # Component storage for managed identity
    constants: Dict[str, PhysicsDataNode] = field(default_factory=dict)
    resources: Dict[str, List[PhysicsNode]] = field(default_factory=dict)
    controls: Dict[str, PhysicsNode] = field(default_factory=dict)

    # Global index of all nodes and channels within this subgraph
    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    channels: List[Channel] = field(default_factory=list)


class Expander:
    def expand_node(self, node_ir: NodeIR) -> SubGraph:
        subgraph = SubGraph()

        # 1. Generate IDs for all physical entities
        # We use the logical node ID as a prefix to ensure uniqueness.
        base_id = node_ir.current_node_instance_hash

        f_pre_id = PhysicalIdGenerator.bleach_node(base_id)
        d_worker_in_id = PhysicalIdGenerator.worker_in_data(base_id)
        f_worker_id = PhysicalIdGenerator.worker_node(base_id)
        d_worker_out_id = PhysicalIdGenerator.worker_out_data(base_id)
        d_trace_id = PhysicalIdGenerator.trace_data(base_id)
        f_post_id = PhysicalIdGenerator.stain_node(base_id)

        # 2. Create Nodes

        # F_pre: The Bleacher
        # Inputs = Task Args + Resource Constraints
        bleacher_inputs = {
            arg.name: PortDef(arg.name, PortRole.DATA, "Any")
            for arg in node_ir.task.args
        }
        # Add ports for resources
        for res_name in node_ir.constraints.keys():
            port_name = f"res_{res_name}"
            bleacher_inputs[port_name] = PortDef(
                port_name, PortRole.RESOURCE, "ResourceSlot"
            )

        # Add ports for implicit dependencies (SIGNAL)
        for dep_id in node_ir.dependencies:
            # We use a naming convention for dependency ports
            port_name = f"wait_for_{dep_id}"
            bleacher_inputs[port_name] = PortDef(port_name, PortRole.SIGNAL, "Token")

        # Add port for condition (SIGNAL/DATA)
        if node_ir.condition:
            port_name = "condition"
            bleacher_inputs[port_name] = PortDef(port_name, PortRole.SIGNAL, "Bool")

        # If after all that, there are no inputs, it's a source node that needs a pulse.
        if not bleacher_inputs:
            bleacher_inputs[BleacherSpec.pulse.name] = PortDef(
                BleacherSpec.pulse.name, PortRole.SIGNAL
            )

        f_pre = BleachNode(
            id=f_pre_id,
            name=f"Bleach({node_ir.name})",
            input_ports=bleacher_inputs,
            output_ports={
                "worker_input": PortDef("worker_input", PortRole.DATA, "Dict"),
                "trace_output": PortDef("trace_output", PortRole.DATA, "TraceCtx"),
                "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event"),
            },
        )

        # D_worker_in: Holds the pure kwargs for the worker
        d_worker_in = PhysicsDataNode(id=d_worker_in_id, name=f"In({node_ir.name})")

        # F_worker: The actual execution logic
        # It conceptually takes *args/**kwargs, but physically takes one 'worker_input' dict
        canonical_hash = node_ir.task.fingerprint["canonical_code_structure_hash"]
        f_worker = WorkerNode(
            id=f_worker_id,
            name=f"Exec({node_ir.name})",
            canonical_code_structure_hash=canonical_hash,
            input_ports={
                "worker_input": PortDef("worker_input", PortRole.DATA, "Dict")
            },
            output_ports={
                "worker_result": PortDef("worker_result", PortRole.DATA, "Any")
            },
        )

        # D_worker_out: Holds the raw result
        d_worker_out = PhysicsDataNode(id=d_worker_out_id, name=f"Out({node_ir.name})")

        # D_trace: The wormhole for metadata (start_ts, trace_id)
        d_trace = PhysicsDataNode(id=d_trace_id, name=f"Trace({node_ir.name})")

        # F_post: The Stainer
        # Outputs = Result + Resource Returns
        # Sovereign Ports: Explicitly define default and error paths
        stainer_outputs = {
            "output_default": PortDef("output_default", PortRole.DATA, "Token"),
            "output_error": PortDef("output_error", PortRole.DATA, "Token"),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event"),
        }
        for res_name in node_ir.constraints.keys():
            port_name = f"res_{res_name}"
            stainer_outputs[port_name] = PortDef(
                port_name, PortRole.RESOURCE, "ResourceSlot"
            )

        f_post = StainNode(
            id=f_post_id,
            name=f"Stain({node_ir.name})",
            input_ports={
                "worker_result": PortDef("worker_result", PortRole.DATA, "Any"),
                "trace_input": PortDef("trace_input", PortRole.DATA, "TraceCtx"),
            },
            output_ports=stainer_outputs,
        )

        # Register nodes
        subgraph.nodes = {
            n.id: n
            for n in [f_pre, d_worker_in, f_worker, d_worker_out, d_trace, f_post]
        }
        subgraph.bleacher = f_pre
        subgraph.worker = f_worker
        subgraph.stainer = f_post

        # 3. Create Internal Wiring (Channels)

        channels = []

        # Path 1: Execution Flow
        # F_pre -> D_worker_in
        channels.append(
            Channel(
                source_node_id=f_pre_id,
                source_port="worker_input",
                target_node_id=d_worker_in_id,
                target_port="in",
            )
        )
        # D_worker_in -> F_worker
        channels.append(
            Channel(
                source_node_id=d_worker_in_id,
                source_port="out",
                target_node_id=f_worker_id,
                target_port="worker_input",
            )
        )
        # F_worker -> D_worker_out
        channels.append(
            Channel(
                source_node_id=f_worker_id,
                source_port="worker_result",
                target_node_id=d_worker_out_id,
                target_port="in",
            )
        )
        # D_worker_out -> F_post
        channels.append(
            Channel(
                source_node_id=d_worker_out_id,
                source_port="out",
                target_node_id=f_post_id,
                target_port="worker_result",
            )
        )

        # Path 2: Trace Bypass
        # F_pre -> D_trace
        channels.append(
            Channel(
                source_node_id=f_pre_id,
                source_port="trace_output",
                target_node_id=d_trace_id,
                target_port="in",
            )
        )
        # D_trace -> F_post
        channels.append(
            Channel(
                source_node_id=d_trace_id,
                source_port="out",
                target_node_id=f_post_id,
                target_port="trace_input",
            )
        )

        subgraph.channels = channels

        return subgraph
~~~~~

### 下一步建议

我们已经成功地建立了新的 `SubGraph` 数据结构。现在，`SubGraph` 已经准备好接收并管理由不同策略生成的辅助节点了。

路线图的下一步 (`1.2`) 是**定义 `ExpansionPolicy` 协议**。这个协议将作为所有“节点创建”逻辑的统一接口，为我们后续从 `WiringPolicy` 中迁移代码提供一个清晰的契约。

如果你同意，我将开始创建定义该协议的计划。
