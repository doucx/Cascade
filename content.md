好的，我们继续执行路线图 `3.2`。

此计划将处理最核心的资源实现——离散资源棱镜 (`DiscreteResourcePrism`)。我们将把其中混杂的节点创建和连线逻辑进行外科手术式的拆分，使其符合新的 `ResourcePrism` 协议。

## [WIP] refactor(compiler): 升级 DiscreteResourcePrism 以适配两阶段协议

### 用户需求

根据架构路线图 3.2，需要修改 `packages/cascade-compiler/src/cascade/compiler/backend/wiring/prisms/discrete.py` 文件。
目标是实现新的 `ResourcePrism` 协议方法：
1.  实现 `expand_task`: 创建 `D_amt`, `F_req`, `D_gnt` 节点，并将它们注册到 `SubGraph` 的 `resources` 字典中。
2.  实现 `wire_task`: 从 `SubGraph` 中获取上述节点，并建立它们与 `Allocator` 及 Task Triad 之间的连接。
3.  删除旧的 `connect_task` 方法。

### 评论

这是资源子系统重构中最繁重的一步。`DiscreteResourcePrism` 包含了复杂的拓扑逻辑（如请求链、授权连线、释放回路）。在重构过程中，我们要特别小心地维护这些逻辑的正确性。特别是 `D_gnt` 节点，它是连接全局分配器和局部任务的关键枢纽，它的创建属于 `Expansion` 阶段，但它的连接（特别是动态端口名）属于 `Wiring` 阶段。

### 目标

1.  修改 `packages/cascade-compiler/src/cascade/compiler/backend/wiring/prisms/discrete.py`。
2.  引入 `ExpansionContext` 的导入。
3.  将原 `connect_task` 中的逻辑拆分为 `expand_task` 和 `wire_task`。
4.  在 `expand_task` 中，将创建的一组节点（`d_amt`, `f_req`, `d_gnt`）作为一个列表存储在 `subgraph.resources[res_name]` 中。
5.  在 `wire_task` 中，按顺序解包这些节点并进行连接。

### 基本原理

当前的 `connect_task` 方法是一个长达 60 行的庞然大物，它混合了创建节点、计算动态端口名和建立连接。

通过本次重构：
-   **`expand_task`** 负责生产：它创建“金额常量”(`D_amt`)、“请求器”(`F_req`) 和“授权接收器”(`D_gnt`)。它负责确立这些组件的存在性和唯一 ID。
-   **`wire_task`** 负责组网：它处理复杂的连接逻辑，比如计算 `Allocator` 上的 `gnt_for_...` 动态端口，并将这些组件接入全局网络。

这种拆分使得“节点 ID 是怎么生成的”和“节点是怎么连的”这两个关注点被物理隔离，极大地提高了代码的可读性。

### 标签

#intent/refine #flow/ready #priority/high #task/domain/compiler #task/object/resource-prism #task/action/refactor #task/state/continue #scope/core #ai/instruct

---

### Script

#### Acts 1: 重写 `discrete.py` 以适配新协议

我们将使用 `write_file` 完整重写 `discrete.py`。 `ensure_globals` 方法保持不变，重点在于将 `connect_task` 拆解。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prisms/discrete.py
~~~~~
~~~~~python
from typing import Any

from cascade.spec.physical.environment import ResourceDef
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.std.specs import (
    DiscreteAllocatorSpec,
    DiscreteReclaimerSpec,
    ResourceRequestorSpec,
    GateSpec,
)
from cascade.std.resource.discrete import DiscreteLedger
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.expansion.context import ExpansionContext
from cascade.compiler.backend.wiring.prism import ResourcePrism


class DiscreteResourcePrism(ResourcePrism):
    def ensure_globals(self, ctx: WiringContext, res_def: ResourceDef) -> None:
        allocator_id = PhysicalIdGenerator.global_allocator(res_def.name)
        reclaimer_id = PhysicalIdGenerator.global_reclaimer(res_def.name)
        ledger_id = PhysicalIdGenerator.global_ledger(res_def.name)

        # Specs shortcuts
        alloc = DiscreteAllocatorSpec
        reclaim = DiscreteReclaimerSpec
        gate = GateSpec

        # D_ledger
        initial_ledger = DiscreteLedger(
            total=res_def.capacity, available=res_def.capacity
        )
        d_ledger = PhysicsDataNode(
            id=ledger_id,
            name=f"Ledger({res_def.name})",
            capacity=1,
            initial_tokens=1,
            initial_payload=initial_ledger,
        )
        ctx.wire.add_node(d_ledger)

        # F_reclaimer
        f_reclaimer = PhysicsFuncNode(
            id=reclaimer_id,
            name=f"Reclaimer({res_def.name})",
            input_ports={
                reclaim.ledger_in.name: PortDef(reclaim.ledger_in.name, PortRole.DATA),
                reclaim.rel_in.name: PortDef(reclaim.rel_in.name, PortRole.DATA),
            },
            output_ports={
                reclaim.ledger_out.name: PortDef(
                    reclaim.ledger_out.name, PortRole.DATA
                ),
                reclaim.signal_out.name: PortDef(
                    reclaim.signal_out.name, PortRole.SIGNAL
                ),
            },
        )
        ctx.wire.add_node(f_reclaimer)

        # F_allocator
        f_allocator = PhysicsFuncNode(
            id=allocator_id,
            name=f"Allocator({res_def.name})",
            input_ports={
                alloc.ledger_in.name: PortDef(alloc.ledger_in.name, PortRole.DATA),
                alloc.req_in.name: PortDef(alloc.req_in.name, PortRole.DATA),
            },
            output_ports={
                alloc.ledger_out.name: PortDef(alloc.ledger_out.name, PortRole.DATA),
                alloc.gnt_out.name: PortDef(alloc.gnt_out.name, PortRole.RESOURCE),
                alloc.req_parked.name: PortDef(alloc.req_parked.name, PortRole.DATA),
            },
        )
        ctx.wire.add_node(f_allocator)

        # Wiring: Ledger <-> Allocator
        ctx.wire.connect(ledger_id, "out", allocator_id, alloc.ledger_in.name)
        ctx.wire.connect(allocator_id, alloc.ledger_out.name, ledger_id, "in")

        # Wiring: Ledger <-> Reclaimer
        ctx.wire.connect(ledger_id, "out", reclaimer_id, reclaim.ledger_in.name)
        ctx.wire.connect(reclaimer_id, reclaim.ledger_out.name, ledger_id, "in")

        # Request Buffer
        d_req_buffer_id = f"buffer.req.{res_def.name}"
        d_req_buffer = PhysicsDataNode(
            id=d_req_buffer_id, name=f"ReqBuffer({res_def.name})", capacity=1000
        )
        ctx.wire.add_node(d_req_buffer)

        # Buffer -> Allocator
        ctx.wire.connect(d_req_buffer_id, "out", allocator_id, alloc.req_in.name)

        # --- Parking & Wake-up Mechanism ---
        # 1. New Nodes
        d_parked_id = f"parked.req.{res_def.name}"
        d_parked = PhysicsDataNode(
            id=d_parked_id, name=f"Parked({res_def.name})", capacity=1000
        )
        ctx.wire.add_node(d_parked)

        d_signal_id = f"signal.wakeup.{res_def.name}"
        d_signal = PhysicsDataNode(
            id=d_signal_id, name=f"Signal({res_def.name})", capacity=1000
        )
        ctx.wire.add_node(d_signal)

        f_gate_id = f"gate.wakeup.{res_def.name}"
        f_gate = PhysicsFuncNode(
            id=f_gate_id,
            name=f"Gate({res_def.name})",
            input_ports={
                gate.req_in.name: PortDef(gate.req_in.name, PortRole.DATA),
                gate.signal_in.name: PortDef(gate.signal_in.name, PortRole.SIGNAL),
            },
            output_ports={gate.req_out.name: PortDef(gate.req_out.name, PortRole.DATA)},
        )
        ctx.wire.add_node(f_gate)

        # 2. New Wiring
        # Allocator parks rejected requests
        ctx.wire.connect(allocator_id, alloc.req_parked.name, d_parked_id, "in")
        # Reclaimer sends wake-up signal
        ctx.wire.connect(reclaimer_id, reclaim.signal_out.name, d_signal_id, "in")
        # Gate is triggered by parked request and signal
        ctx.wire.connect(d_parked_id, "out", f_gate_id, gate.req_in.name)
        ctx.wire.connect(d_signal_id, "out", f_gate_id, gate.signal_in.name)
        # Gate sends request back to the main buffer for retry
        ctx.wire.connect(f_gate_id, gate.req_out.name, d_req_buffer_id, "in")

        # Release Buffer
        rel_buffer_id = f"buffer.rel.{res_def.name}"
        d_rel_buffer = PhysicsDataNode(
            id=rel_buffer_id, name=f"RelBuffer({res_def.name})", capacity=1000
        )
        ctx.wire.add_node(d_rel_buffer)

        # Buffer -> Reclaimer
        ctx.wire.connect(rel_buffer_id, "out", reclaimer_id, reclaim.rel_in.name)

    def expand_task(
        self,
        ctx: ExpansionContext,
        node_ir: NodeIR,
        subgraph: SubGraph,
        res_name: str,
        amount: Any,
    ) -> None:
        # Spec shortcuts
        req = ResourceRequestorSpec

        # 1. D_const (Amount)
        d_amt_id = PhysicalIdGenerator.constant(
            node_ir.current_node_instance_hash, f"req_amt_{res_name}"
        )
        d_amt = PhysicsDataNode(
            id=d_amt_id,
            name=f"Amt({res_name})",
            capacity=1,
            initial_tokens=1,
            initial_payload=amount,
        )
        ctx.wire.add_node(d_amt)

        # 2. F_req (Requestor)
        f_req_id = PhysicalIdGenerator.requestor(
            node_ir.current_node_instance_hash, res_name
        )
        f_req = PhysicsFuncNode(
            id=f_req_id,
            name=f"Req({res_name})",
            input_ports={req.amount.name: PortDef(req.amount.name, PortRole.DATA)},
            output_ports={req.req_out.name: PortDef(req.req_out.name, PortRole.DATA)},
        )
        ctx.wire.add_node(f_req)

        # 3. D_gnt (Grant Recipient)
        d_gnt_id = f"gnt.to.{node_ir.current_node_instance_hash}.{res_name}"
        d_gnt = PhysicsDataNode(id=d_gnt_id, name=f"Gnt({res_name}->{node_ir.name})")
        ctx.wire.add_node(d_gnt)

        # Register components in SubGraph
        # We store them as a list: [D_amt, F_req, D_gnt]
        subgraph.resources[res_name] = [d_amt, f_req, d_gnt]
        subgraph.nodes[d_amt_id] = d_amt
        subgraph.nodes[f_req_id] = f_req
        subgraph.nodes[d_gnt_id] = d_gnt

    def wire_task(
        self,
        ctx: WiringContext,
        node_ir: NodeIR,
        subgraph: SubGraph,
        res_name: str,
        amount: Any,
    ) -> None:
        allocator_id = PhysicalIdGenerator.global_allocator(res_name)
        req_buffer_id = f"buffer.req.{res_name}"
        rel_buffer_id = f"buffer.rel.{res_name}"

        # Spec shortcuts
        req = ResourceRequestorSpec

        # Retrieve components from SubGraph
        d_amt, f_req, d_gnt = subgraph.resources[res_name]
        d_amt_id = d_amt.id
        f_req_id = f_req.id
        d_gnt_id = d_gnt.id

        # --- A. Request Chain ---
        # D_amt -> F_req (Direct connection)
        ctx.wire.connect(d_amt_id, "out", f_req_id, req.amount.name)

        # F_req -> D_req_buffer
        ctx.wire.connect(f_req_id, req.req_out.name, req_buffer_id, "in")

        # --- B. Grant Wiring (Sovereign Ports) ---
        # Use prefix from Spec for dynamic port name
        spec = DiscreteAllocatorSpec
        gnt_port_name = f"{spec.grants.prefix}{f_req_id}"

        # Add this port to the Allocator definition
        # Note: In a pure HFEA approach, ports should ideally be defined in Expansion phase too,
        # but dynamic ports on global nodes are tricky. We allow this modification in Wiring phase for now.
        allocator_node = ctx.physical_graph.nodes[allocator_id]
        assert isinstance(allocator_node, PhysicsFuncNode)
        allocator_node.output_ports[gnt_port_name] = PortDef(
            gnt_port_name, PortRole.RESOURCE
        )

        # Allocator -> Dedicated DataNode
        ctx.wire.connect(allocator_id, gnt_port_name, d_gnt_id, "in")

        # Dedicated DataNode -> Bleacher
        assert subgraph.bleacher is not None
        bleacher_port_name = f"res_{res_name}"
        ctx.wire.connect(d_gnt_id, "out", subgraph.bleacher.id, bleacher_port_name)

        # --- C. Release Wiring ---
        # Stainer -> RelBuffer
        assert subgraph.stainer is not None
        release_port_name = f"res_{res_name}"
        ctx.wire.connect(
            subgraph.stainer.id,
            release_port_name,
            rel_buffer_id,
            "in",
        )
~~~~~

### 下一步建议

我们已经成功升级了 `DiscreteResourcePrism`，使其完全适配新的协议。

路线图的下一步 (`3.3`) 是**拆分 `ResourceWiringPolicy`**。我们需要创建 `ResourceExpansionPolicy` 来调用 `prism.expand_task`，并更新 `ResourceWiringPolicy` 来调用 `prism.wire_task`。完成这一步后，我们将完成所有策略的迁移工作。

如果你同意，我将开始制定拆分 `ResourceWiringPolicy` 的计划。
