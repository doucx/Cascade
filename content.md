简要回答
你的分析是正确的。VM 执行超时（Timeout）的根本原因是物理图中的 **Egress（出口）** 节点被错误地创建为了 `DataNode`，而不是 `FuncNode`。

在当前的架构中，Egress 的工作机制是：
1.  `Stainer` 产生结果 Token。
2.  Token 流入 Egress Buffer (`DataNode`)。
3.  Egress Actor (`FuncNode`) 消耗 Buffer 中的 Token。
4.  Egress Actor (`standard_egress`) 执行，并将结果放入 `system.egress_queue`。
5.  `VMExecutionStrategy` 从队列中读取结果并返回。

然而，`ControlFlowExpansionPolicy` 当前的实现只创建了一个 `DataNode` 作为 Egress。这意味着 Token 会停留在该 DataNode 中，永远不会触发 `standard_egress` 函数执行，导致 `egress_queue` 永远为空，最终导致测试超时。

此外，`Builder` 生成 Manifest 的逻辑也需要更新，以便正确识别新的 Egress FuncNode 作为退出点。

## [WIP] fix: 修复 VM Egress 节点类型错误导致的执行死锁

### 错误分析
测试超时是因为 VM 的 Egress 机制失效。
1.  **Expansion 错误**: `ControlFlowExpansionPolicy` 将 Egress 节点创建为 `PhysicsDataNode`。但在 Cascade v3.1 物理层中，只有 `PhysicsFuncNode` 才能执行内核函数（如 `standard_egress`）。`DataNode` 只是被动存储 Token，无法触发副作用（如推送到队列）。
2.  **Manifest 错误**: `Builder` 在生成 `exit_points` 时，仅扫描 `PhysicsDataNode`。即使修复了 Expansion，如果 Manifest 不指向新的 FuncNode，运行时也无法正确映射结果。

### 用户需求
修复 VM 集成测试中的超时问题，确保 Egress 机制能正确地将结果传回给 Runtime Strategy。

### 评论
这是一个关键的架构修复。它不仅解决了死锁，还纠正了 Egress 作为一个“主动执行者”（FuncNode）而非“被动容器”（DataNode）的语义。

### 目标
1.  修改 `ControlFlowExpansionPolicy`：为每个 Root Logical Node 创建一个 `Egress Buffer` (DataNode) 和一个 `Egress Actor` (FuncNode)。
2.  修改 `Builder`：更新 `exit_points` 的扫描逻辑，使其能够识别 Egress FuncNode。

### 基本原理
遵循 Cascade 的二分图（Bipartite Graph）原则：数据必须流经 `DataNode` -> `FuncNode`。Stainer（Func）输出到 Egress Buffer（Data），Egress Buffer 输出到 Egress Actor（Func）。Egress Actor 执行时调用 `standard_egress` IC，将结果推送到系统队列。

### 标签
#intent/fix #flow/ready #priority/critical #comp/compiler #concept/executor #scope/core #ai/instruct #task/domain/compiler #task/object/egress-policy #task/action/fix

---

### Script

#### Acts 1: 修复 ControlFlowExpansionPolicy

我们将修改扩展策略，使其能够正确地构建 `Stainer -> Buffer -> Egress(Func)` 的拓扑结构。这需要引入新的导入 (`PhysicsFuncNode`, `EgressSpec` 等) 并重写 `expand` 方法中的 Egress 创建逻辑。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/control.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.constants import NodePrefix
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.expansion.context import ExpansionContext
from cascade.compiler.backend.expansion.protocol import ExpansionPolicy
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.std.specs import EgressSpec
from cascade.spec.physical.constants import NodePrefix
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.expansion.context import ExpansionContext
from cascade.compiler.backend.expansion.protocol import ExpansionPolicy
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/control.py
~~~~~
~~~~~python.old
        # 3. Egress for Root Nodes
        if node_ir.logical_id in ctx.graph_ir.root_logical_ids:
            d_egress_id = f"{NodePrefix.EGRESS}.{node_ir.logical_id}"
            d_egress = PhysicsDataNode(id=d_egress_id, name=f"Egress({node_ir.name})")
            ctx.wire.add_node(d_egress)
            subgraph.nodes[d_egress.id] = d_egress
            subgraph.controls[f"egress_for_{node_ir.logical_id}"] = d_egress
~~~~~
~~~~~python.new
        # 3. Egress for Root Nodes
        if node_ir.logical_id in ctx.graph_ir.root_logical_ids:
            # 3.1 D_buffer (The waiting room)
            d_buffer_id = f"buffer.egress.{node_ir.logical_id}"
            d_buffer = PhysicsDataNode(
                id=d_buffer_id, name=f"BufEgress({node_ir.name})"
            )
            ctx.wire.add_node(d_buffer)
            subgraph.nodes[d_buffer.id] = d_buffer

            # 3.2 F_egress (The active exporter)
            f_egress_id = f"{NodePrefix.EGRESS}.{node_ir.logical_id}"
            f_egress = PhysicsFuncNode(
                id=f_egress_id,
                name=f"Egress({node_ir.name})",
                input_ports={
                    EgressSpec.input_token.name: PortDef(
                        EgressSpec.input_token.name, PortRole.DATA
                    )
                },
            )
            ctx.wire.add_node(f_egress)
            subgraph.nodes[f_egress.id] = f_egress

            # 3.3 Wire Buffer -> F_egress
            ctx.wire.connect(
                d_buffer_id, "out", f_egress_id, EgressSpec.input_token.name
            )

            # 3.4 Expose Buffer for Wiring (Stainer -> Buffer)
            # The Wiring Policy connects the Stainer output to this node.
            subgraph.controls[f"egress_for_{node_ir.logical_id}"] = d_buffer
~~~~~

#### Acts 2: 修复 Builder 的 Manifest 生成逻辑

现在 Egress 是一个 `PhysicsFuncNode`，我们需要更新 `Builder` 以便正确识别它并将其 ID 添加到 `manifest.exit_points` 中。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import GraphIR
from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.environment import EnvironmentDef
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.assembly import (
    Assembly,
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import GraphIR
from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.environment import EnvironmentDef
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.assembly import (
    Assembly,
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
        exit_points = {
            node.id.split(".")[1]: node.id
            for node in physical_graph.nodes.values()
            if isinstance(node, PhysicsDataNode)
            and node.id.startswith(f"{NodePrefix.EGRESS}.")
        }
~~~~~
~~~~~python.new
        exit_points = {
            node.id.split(".")[1]: node.id
            for node in physical_graph.nodes.values()
            if isinstance(node, PhysicsFuncNode)
            and node.id.startswith(f"{NodePrefix.EGRESS}.")
        }
~~~~~

### 下一步建议

修复完成后，应立即运行 integration 测试 `packages/cascade-runtime/tests/integration/test_vm_e2e.py` 来验证修复是否生效。如果测试通过，说明 Egress 管道已打通，VM 能够正确返回执行结果。
