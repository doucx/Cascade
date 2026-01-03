简要回答

好的，我们将执行第一阶段重构。这将把 `Builder` 中单一的、庞大的构建过程拆解为基于策略模式的模块化结构，为未来的扩展打下坚实基础。

## [WIP] refactor(compiler): 实施通用布线算法第一阶段 - 基础设施解耦

### 用户需求
将 `cascade-compiler` 的后端 `Builder` 类重构为基于策略模式（Strategy Pattern）的架构，以解耦参数、控制流、资源和可观测性的布线逻辑。

### 评论
这是一个关键的架构升级。目前的 `Builder` 是一个包含了所有物理层构造逻辑的“上帝类”。通过引入 `WiringPolicy` 和 `WiringContext`，我们将布线逻辑标准化，使得每个关注点（如资源管理、参数绑定）都可以独立演进和测试，消除了“牵一发而动全身”的风险。

### 目标
1.  定义 `WiringContext` 和 `WiringPolicy` 协议。
2.  将现有的布线逻辑提取为独立的策略类：
    *   `ParameterWiringPolicy`: 处理参数输入 (`inputs`)。
    *   `ControlFlowWiringPolicy`: 处理依赖 (`dependencies`) 和条件 (`condition`)。
    *   `ResourceWiringPolicy`: 处理资源约束 (`constraints`) 和全局资源代理 (`Allocator/Reclaimer`)。
    *   `ObservabilityWiringPolicy`: 处理 Sidecar 观测设施。
    *   `PulseWiringPolicy`: 处理源节点的启动脉冲。
3.  重写 `Builder` 以使用策略链。

### 基本原理
我们遵循“组合优于继承”和“单一职责原则”。
*   **WiringContext**: 充当布线过程中的共享黑板，持有图、线束（Harness）和环境信息。
*   **WiringPolicy**: 定义了两个阶段的钩子：`setup_globals` (用于创建全局单例，如 Allocators) 和 `apply` (用于处理单个节点的布线)。
*   这不仅使代码更整洁，还为未来支持自定义扩展（如用户定义的资源类型）提供了接口。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #scope/core #task/domain/compiler #task/object/wiring-algorithm #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 定义布线上下文与协议

我们首先创建布线的基础设施：上下文对象和策略协议。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/wiring/context.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Dict

from cascade.spec.topology import BipartiteGraph
from cascade.spec.environment import EnvironmentDef
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring import WiringHarness


@dataclass
class WiringContext:
    """
    A shared context object passed through the wiring pipeline.
    It holds the state of the physical graph being built.
    """

    graph_ir: "GraphIR"  # Forward ref to avoid circular import if possible, or use Any
    environment: EnvironmentDef
    physical_graph: BipartiteGraph
    wire: WiringHarness
    subgraphs: Dict[str, SubGraph] = field(default_factory=dict)

    def register_subgraph(self, node_id: str, subgraph: SubGraph) -> None:
        self.subgraphs[node_id] = subgraph
        self.wire.add_subgraph(subgraph)

    def get_subgraph(self, node_id: str) -> SubGraph:
        if node_id not in self.subgraphs:
            raise KeyError(f"Subgraph for node '{node_id}' not found in context.")
        return self.subgraphs[node_id]
~~~~~

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/wiring/protocol.py
~~~~~
~~~~~python
from typing import Protocol
from cascade.spec.ir.models import NodeIR
from cascade.compiler.backend.expander import SubGraph
from .context import WiringContext


class WiringPolicy(Protocol):
    """
    Protocol for a wiring strategy.
    Each policy is responsible for a specific aspect of the physical graph construction.
    """

    def setup_globals(self, ctx: WiringContext) -> None:
        """
        Phase 0: Setup global infrastructure.
        Called once before processing any nodes.
        Used for creating global resource brokers, observability buses, etc.
        """
        ...

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        """
        Phase 1: Wire a specific node.
        Called for each node in the logical graph.
        Used for connecting the node's triad to inputs, outputs, resources, etc.
        """
        ...
~~~~~

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/wiring/__init__.py
~~~~~
~~~~~python
from .context import WiringContext
from .protocol import WiringPolicy

__all__ = ["WiringContext", "WiringPolicy"]
~~~~~

#### Acts 2: 提取各个布线策略

现在我们将 `Builder` 中的逻辑拆解到各个策略文件中。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-compiler/src/cascade/compiler/wiring/policies
touch packages/cascade-compiler/src/cascade/compiler/wiring/policies/__init__.py
~~~~~

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/wiring/policies/parameter.py
~~~~~
~~~~~python
from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.ports import PortDef, PortRole, PortName
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.utils.naming import PhysicalIdGenerator
from cascade.compiler.wiring.context import WiringContext
from cascade.compiler.wiring.protocol import WiringPolicy


class ParameterWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None

        for arg_name, source_ref in node_ir.inputs.items():
            # Case A: Reference to another node (Dependency)
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(source_ref)
                assert source_subgraph.stainer is not None

                # Violation Fix: Insert D_dep (Intermediate Data Node)
                d_dep_id = f"dep.{source_ref}.to.{node_ir.id}.{arg_name}"
                d_dep = PhysicsDataNode(id=d_dep_id, name=f"Dep({arg_name})")
                ctx.wire.add_node(d_dep)

                # Source Stainer -> D_dep
                ctx.wire.connect(source_subgraph.stainer.id, "output", d_dep_id, "in")

                # D_dep -> Target Bleacher
                ctx.wire.connect(d_dep_id, "out", subgraph.bleacher.id, arg_name)

            # Case B: Literal Value (Constant) - Use Probe Model
            else:
                # 1. D_const (DataNode holding the literal value)
                d_const_id = PhysicalIdGenerator.constant(node_ir.id, arg_name)
                d_const = PhysicsDataNode(
                    id=d_const_id,
                    name=f"Const({arg_name})",
                    capacity=1,
                    initial_tokens=1,
                    initial_payload=source_ref,
                )
                ctx.wire.add_node(d_const)

                # 2. F_probe (The probe node for constants)
                f_probe_id = PhysicalIdGenerator.probe_const(node_ir.id, arg_name)
                f_probe = PhysicsFuncNode(
                    id=f_probe_id,
                    name=f"Probe({arg_name})",
                    input_ports={"value": PortDef("value", PortRole.DATA)},
                    output_ports={"out": PortDef("out", PortRole.DATA)},
                )
                ctx.wire.add_node(f_probe)

                # 3. D_probed (Intermediate data node to connect to Bleacher)
                d_probed_id = f"{f_probe_id}.out"
                d_probed = PhysicsDataNode(id=d_probed_id, name=f"Probed({arg_name})")
                ctx.wire.add_node(d_probed)

                # 4. Wiring
                # D_const -> F_probe
                ctx.wire.connect(d_const_id, "out", f_probe_id, "value")
                # F_probe -> D_probed
                ctx.wire.connect(f_probe_id, "out", d_probed_id, "in")
                # D_probed -> Target Bleacher
                ctx.wire.connect(d_probed_id, "out", subgraph.bleacher.id, arg_name)
~~~~~

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/wiring/policies/control.py
~~~~~
~~~~~python
from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsDataNode
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.wiring.context import WiringContext
from cascade.compiler.wiring.protocol import WiringPolicy


class ControlFlowWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None

        # 4.2 Sequence Dependencies (.after())
        for dep_id in node_ir.dependencies:
            if dep_id in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(dep_id)
                assert source_subgraph.stainer is not None

                port_name = f"wait_for_{dep_id}"

                # Violation Fix: Insert D_seq
                d_seq_id = f"seq.{dep_id}.to.{node_ir.id}"
                d_seq = PhysicsDataNode(id=d_seq_id, name=f"Seq({dep_id})")
                ctx.wire.add_node(d_seq)

                ctx.wire.connect(source_subgraph.stainer.id, "output", d_seq_id, "in")
                ctx.wire.connect(d_seq_id, "out", subgraph.bleacher.id, port_name)

        # 4.3 Condition (.run_if())
        if node_ir.condition and node_ir.condition in ctx.subgraphs:
            source_subgraph = ctx.get_subgraph(node_ir.condition)
            assert source_subgraph.stainer is not None

            # Violation Fix: Insert D_cond
            d_cond_id = f"cond.{node_ir.condition}.to.{node_ir.id}"
            d_cond = PhysicsDataNode(id=d_cond_id, name=f"Cond({node_ir.condition})")
            ctx.wire.add_node(d_cond)

            ctx.wire.connect(source_subgraph.stainer.id, "output", d_cond_id, "in")
            ctx.wire.connect(d_cond_id, "out", subgraph.bleacher.id, "condition")
~~~~~

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/wiring/policies/pulse.py
~~~~~
~~~~~python
from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsDataNode
from cascade.spec.ports import PortName
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.utils.naming import PhysicalIdGenerator
from cascade.compiler.wiring.context import WiringContext
from cascade.compiler.wiring.protocol import WiringPolicy


class PulseWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None

        # Identify Source Nodes
        # A true source has no inputs, dependencies, conditions, or constraints.
        is_true_source = (
            not node_ir.inputs
            and not node_ir.dependencies
            and not node_ir.condition
            and not node_ir.constraints
        )

        if is_true_source:
            d_pulse_id = PhysicalIdGenerator.pulse_source(node_ir.id)
            d_pulse = PhysicsDataNode(
                id=d_pulse_id,
                name=f"Pulse({node_ir.id})",
                capacity=1,
                initial_tokens=1,
            )
            ctx.wire.add_node(d_pulse)
            ctx.wire.connect(d_pulse_id, "out", subgraph.bleacher.id, PortName.PULSE)
~~~~~

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/wiring/policies/observability.py
~~~~~
~~~~~python
import sys
from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsDataNode
from cascade.spec.triad import ObservabilityNode
from cascade.spec.ports import PortRole, PortDef
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.utils.naming import PhysicalIdGenerator
from cascade.compiler.wiring.context import WiringContext
from cascade.compiler.wiring.protocol import WiringPolicy


class ObservabilityWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:
        d_life_id = PhysicalIdGenerator.observability_bus()
        f_obs_id = PhysicalIdGenerator.observability_observer()

        # Capacity set to maxsize to prevent backpressure from observability
        d_life = PhysicsDataNode(
            id=d_life_id, name="LifecycleBus", capacity=sys.maxsize
        )
        f_obs = ObservabilityNode(
            id=f_obs_id,
            name="LifecycleObserver",
            input_ports={
                "event_token": PortDef("event_token", PortRole.OBSERVABILITY, "Event")
            },
            output_ports={},  # Observer emits to the outside world, not back into the graph
        )
        ctx.wire.add_node(d_life)
        ctx.wire.add_node(f_obs)

        ctx.wire.connect(d_life_id, "out", f_obs_id, "event_token")

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None
        assert subgraph.stainer is not None

        d_life_id = PhysicalIdGenerator.observability_bus()

        # Wire task observability TO the sidecar bus
        ctx.wire.connect(subgraph.bleacher.id, "obs_output", d_life_id, "in")
        ctx.wire.connect(subgraph.stainer.id, "obs_output", d_life_id, "in")
~~~~~

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/wiring/policies/resource.py
~~~~~
~~~~~python
from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.ports import PortDef, PortRole, PortName
from cascade.std.resource.discrete import DiscreteLedger
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.utils.naming import PhysicalIdGenerator
from cascade.compiler.wiring.context import WiringContext
from cascade.compiler.wiring.protocol import WiringPolicy


class ResourceWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:
        # Create Resource Brokers (Allocators + Reclaimers) for all resources in env
        for res_def in ctx.environment.resources:
            allocator_id = PhysicalIdGenerator.global_allocator(res_def.name)
            reclaimer_id = PhysicalIdGenerator.global_reclaimer(res_def.name)
            ledger_id = PhysicalIdGenerator.global_ledger(res_def.name)

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

            # F_reclaimer (Priority High: Must release before allocate to avoid starvation)
            f_reclaimer = PhysicsFuncNode(
                id=reclaimer_id,
                name=f"Reclaimer({res_def.name})",
                input_ports={
                    PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                    PortName.REL: PortDef(PortName.REL, PortRole.DATA),
                },
                output_ports={
                    PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                },
            )
            ctx.wire.add_node(f_reclaimer)

            # F_allocator (Priority Low)
            # NOTE: Dynamic grant ports (gnt_for_...) will be added during wiring phase
            f_allocator = PhysicsFuncNode(
                id=allocator_id,
                name=f"Allocator({res_def.name})",
                input_ports={
                    PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                    PortName.REQ: PortDef(PortName.REQ, PortRole.DATA),
                },
                output_ports={
                    PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                    # PortName.GNT is deprecated in favor of dynamic ports, but kept for fallback
                    PortName.GNT: PortDef(PortName.GNT, PortRole.RESOURCE),
                    PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA),
                },
            )
            ctx.wire.add_node(f_allocator)

            # Wiring: Ledger <-> Allocator
            ctx.wire.connect(ledger_id, "out", allocator_id, PortName.LEDGER_IN)
            ctx.wire.connect(allocator_id, PortName.LEDGER_OUT, ledger_id, "in")

            # Wiring: Ledger <-> Reclaimer
            ctx.wire.connect(ledger_id, "out", reclaimer_id, PortName.LEDGER_IN)
            ctx.wire.connect(reclaimer_id, PortName.LEDGER_OUT, ledger_id, "in")

            # Request Buffer
            d_req_buffer_id = f"buffer.req.{res_def.name}"
            d_req_buffer = PhysicsDataNode(
                id=d_req_buffer_id, name=f"ReqBuffer({res_def.name})", capacity=1000
            )
            ctx.wire.add_node(d_req_buffer)

            # Buffer -> Allocator
            ctx.wire.connect(d_req_buffer_id, "out", allocator_id, PortName.REQ)
            # Recirculation: Allocator -> Buffer
            ctx.wire.connect(allocator_id, PortName.REQ_OUT, d_req_buffer_id, "in")

            # Release Buffer
            rel_buffer_id = f"buffer.rel.{res_def.name}"
            d_rel_buffer = PhysicsDataNode(
                id=rel_buffer_id, name=f"RelBuffer({res_def.name})", capacity=1000
            )
            ctx.wire.add_node(d_rel_buffer)

            # Buffer -> Reclaimer
            ctx.wire.connect(rel_buffer_id, "out", reclaimer_id, PortName.REL)

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None
        assert subgraph.stainer is not None

        # Validate resource existence
        # Note: We can't rely on Builder.build's early validation loop anymore
        # because the logic is distributed. We validate here locally.
        env_resource_names = {r.name for r in ctx.environment.resources}
        for res_name in node_ir.constraints:
            if res_name not in env_resource_names:
                raise ValueError(
                    f"Resource '{res_name}' required by node '{node_ir.id}' is not defined"
                )

        for res_name, amount in node_ir.constraints.items():
            allocator_id = PhysicalIdGenerator.global_allocator(res_name)
            req_buffer_id = f"buffer.req.{res_name}"
            rel_buffer_id = f"buffer.rel.{res_name}"

            # --- A. Request Chain ---
            # 1. D_const (Amount)
            d_amt_id = PhysicalIdGenerator.constant(node_ir.id, f"req_amt_{res_name}")
            d_amt = PhysicsDataNode(
                id=d_amt_id,
                name=f"Amt({res_name})",
                capacity=1,
                initial_tokens=1,
                initial_payload=amount,
            )
            ctx.wire.add_node(d_amt)

            # 2. F_probe (ConstProbe)
            f_probe_id = PhysicalIdGenerator.probe_const(node_ir.id, res_name)
            f_probe = PhysicsFuncNode(
                id=f_probe_id,
                name=f"Probe({res_name})",
                input_ports={"value": PortDef("value", PortRole.DATA)},
                output_ports={"out": PortDef("out", PortRole.DATA)},
            )
            ctx.wire.add_node(f_probe)

            # 3. F_req (Requestor)
            f_req_id = PhysicalIdGenerator.requestor(node_ir.id, res_name)
            f_req = PhysicsFuncNode(
                id=f_req_id,
                name=f"Req({res_name})",
                input_ports={"amount": PortDef("amount", PortRole.DATA)},
                output_ports={
                    PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA)
                },
            )
            ctx.wire.add_node(f_req)

            # 4. Wiring
            # D_amt -> F_probe
            ctx.wire.connect(d_amt_id, "out", f_probe_id, "value")

            # F_probe -> D_probed
            d_probed_id = f"{f_probe_id}.out"
            d_probed = PhysicsDataNode(id=d_probed_id, name="ProbedVal")
            ctx.wire.add_node(d_probed)

            ctx.wire.connect(f_probe_id, "out", d_probed_id, "in")

            # D_probed -> F_req
            ctx.wire.connect(d_probed_id, "out", f_req_id, "amount")

            # F_req -> D_req_buffer (Global Buffer for the Allocator)
            ctx.wire.connect(f_req_id, PortName.REQ_OUT, req_buffer_id, "in")

            # --- B. Grant Wiring (Sovereign Ports) ---
            # 1. Define the dynamic port name on Allocator
            gnt_port_name = f"gnt_for_{f_req_id}"

            # 2. Add this port to the Allocator definition
            allocator_node = ctx.physical_graph.nodes[allocator_id]
            assert isinstance(allocator_node, PhysicsFuncNode)
            allocator_node.output_ports[gnt_port_name] = PortDef(
                gnt_port_name, PortRole.RESOURCE
            )

            # 3. Create a dedicated intermediate DataNode for this grant
            d_gnt_id = f"gnt.to.{node_ir.id}.{res_name}"
            d_gnt = PhysicsDataNode(
                id=d_gnt_id, name=f"Gnt({res_name}->{node_ir.name})"
            )
            ctx.wire.add_node(d_gnt)

            # 4. Allocator -> Dedicated DataNode
            ctx.wire.connect(allocator_id, gnt_port_name, d_gnt_id, "in")

            # 5. Dedicated DataNode -> Bleacher
            bleacher_port_name = f"res_{res_name}"
            ctx.wire.connect(
                d_gnt_id, "out", subgraph.bleacher.id, bleacher_port_name
            )

            # --- C. Release Wiring ---
            # Stainer -> RelBuffer
            release_port_name = f"res_{res_name}"
            ctx.wire.connect(
                subgraph.stainer.id,
                release_port_name,
                rel_buffer_id,
                "in",
            )
~~~~~

#### Acts 3: 重构 Builder 类

最后，我们替换 `Builder` 的实现，使其成为一个策略执行器。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python
from typing import List

from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import BipartiteGraph
from cascade.spec.environment import EnvironmentDef
from .expander import Expander
from .validator import GraphValidator
from .wiring import WiringHarness
from cascade.compiler.wiring.context import WiringContext
from cascade.compiler.wiring.protocol import WiringPolicy
from cascade.compiler.wiring.policies.parameter import ParameterWiringPolicy
from cascade.compiler.wiring.policies.control import ControlFlowWiringPolicy
from cascade.compiler.wiring.policies.observability import ObservabilityWiringPolicy
from cascade.compiler.wiring.policies.resource import ResourceWiringPolicy
from cascade.compiler.wiring.policies.pulse import PulseWiringPolicy


class Builder:
    def __init__(self):
        self._expander = Expander()
        self._validator = GraphValidator()
        self._policies: List[WiringPolicy] = [
            ResourceWiringPolicy(),
            ObservabilityWiringPolicy(),
            ParameterWiringPolicy(),
            ControlFlowWiringPolicy(),
            PulseWiringPolicy(),
        ]

    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> BipartiteGraph:
        # 1. Initialize Context
        physical_graph = BipartiteGraph()
        wire = WiringHarness(physical_graph)
        ctx = WiringContext(
            graph_ir=graph_ir,
            environment=environment,
            physical_graph=physical_graph,
            wire=wire,
        )

        # 2. Phase 0: Setup Global Infrastructure
        for policy in self._policies:
            policy.setup_globals(ctx)

        # 3. Phase 1: Expand and Wire Nodes
        for node_ir in graph_ir.nodes:
            # 3.1 Expand triad
            subgraph = self._expander.expand_node(node_ir)
            ctx.register_subgraph(node_ir.id, subgraph)

            # 3.2 Apply wiring policies
            for policy in self._policies:
                policy.apply(ctx, node_ir, subgraph)

        # 4. Final Validation
        self._validator.validate(physical_graph, graph_ir)

        return physical_graph
~~~~~

### 下一步建议
我们已经完成了第一阶段的基础设施解耦。现在代码结构已经清晰地反映了不同的布线关注点。
下一步，我们可以进入**第二阶段：资源系统的声明式重构**。我们将进一步把 `ResourceWiringPolicy` 中创建 Allocator/Requestor 的具体逻辑抽象到 `cascade-std` 的原语定义中，实现资源类型的真正可插拔。
