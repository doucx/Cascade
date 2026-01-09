这是一个分阶段的重构计划。我们将首先完善 `cascade-std` 中的 Specs 定义，然后分批次重构 Wiring Policies。

本计划 (Batch 1) 聚焦于：
1.  **完善 Specs**: 更新 `BleacherSpec` 以显式包含 `pulse` 和 `condition` 端口；新增 `ObservabilitySpec`。
2.  **重构 Pulse 连线**: 使 `PulseWiringPolicy` 依赖 `BleacherSpec`。
3.  **重构 Observability 连线**: 使 `ObservabilityWiringPolicy` 依赖 `ObservabilitySpec`, `BleacherSpec` 和 `StainerSpec`。

## [WIP] refactor(compiler): 实施 PIDL 阶段四 - Batch 1 (Pulse & Observability)

### 用户需求
将 Compiler 的连线逻辑从依赖硬编码字符串 (`PortName`, 字面量) 迁移到依赖 `cascade.std.specs` 中的强类型 Spec 定义。
本批次涵盖：
- `BleacherSpec` 的完善。
- `ObservabilitySpec` 的创建。
- `PulseWiringPolicy` 的重构。
- `ObservabilityWiringPolicy` 的重构。

### 评论
这是 PIDL 路线图的关键一步，标志着 Compiler 开始真正“理解”物理层的契约，而不是仅仅“拼凑”字符串。

### 目标
1.  在 `cascade-std` 中定义 `ObservabilitySpec` 并更新 `BleacherSpec`。
2.  消除 `PulseWiringPolicy` 中对 `PortName.PULSE` 的引用。
3.  消除 `ObservabilityWiringPolicy` 中对 `"obs_output"` 和 `"event_token"` 的字面量引用。

### 基本原理
通过让 Compiler 和 Kernel 共享同一套 Spec 定义 (SSoT)，我们消除了“协议漂移”的风险。Spec 变更将自动传播到连线逻辑，或者在静态分析阶段暴露问题。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #comp/std #scope/core #task/domain/compiler #task/object/wiring-policy #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 完善 Standard Specs
我们需要更新 `BleacherSpec` 以包含之前隐式使用的端口，并为 Observer Node 创建新的契约。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/specs/triad.py
~~~~~
~~~~~python.old
class BleacherSpec(PhysicsSpec):
    """
    Contract for the Pre-process Node (F_pre).
    Inputs are dynamic (based on Task arguments), so they are not exhaustively listed here.
    """
    # Inputs (Dynamic)
    # Collects all inputs not matched by other static input definitions.
    args = Port.MapInput(role=PortRole.DATA)

    # Outputs
    worker_input = Port.Output("worker_input", role=PortRole.DATA, type="Dict")
    trace_output = Port.Output("trace_output", role=PortRole.DATA, type="TraceCtx")
    context_output = Port.Output("context_output", role=PortRole.DATA, type="Dict")
    obs_output = Port.Output("obs_output", role=PortRole.OBSERVABILITY, type="Event")
~~~~~
~~~~~python.new
class BleacherSpec(PhysicsSpec):
    """
    Contract for the Pre-process Node (F_pre).
    Inputs are dynamic (based on Task arguments), so they are not exhaustively listed here.
    """
    # Inputs (Dynamic)
    # Collects all inputs not matched by other static input definitions.
    args = Port.MapInput(role=PortRole.DATA)
    
    # Conditional Execution
    condition = Port.Input("condition", role=PortRole.SIGNAL, type="Bool")
    # Startup Pulse
    pulse = Port.Input("__pulse__", role=PortRole.SIGNAL)

    # Outputs
    worker_input = Port.Output("worker_input", role=PortRole.DATA, type="Dict")
    trace_output = Port.Output("trace_output", role=PortRole.DATA, type="TraceCtx")
    context_output = Port.Output("context_output", role=PortRole.DATA, type="Dict")
    obs_output = Port.Output("obs_output", role=PortRole.OBSERVABILITY, type="Event")


class ObservabilitySpec(PhysicsSpec):
    """
    Contract for the Sidecar Observer (F_obs).
    """
    event_token = Port.Input("event_token", role=PortRole.OBSERVABILITY, type="Event")
~~~~~

#### Acts 2: 重构 PulseWiringPolicy
不再引用 `PortName.PULSE`，改为引用 `BleacherSpec.pulse.name`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/pulse.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.ports import PortName
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.std.specs import BleacherSpec
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/pulse.py
~~~~~
~~~~~python.old
                capacity=1,
                initial_tokens=1,
            )
            ctx.wire.add_node(d_pulse)
            ctx.wire.connect(d_pulse_id, "out", subgraph.bleacher.id, PortName.PULSE)
~~~~~
~~~~~python.new
                capacity=1,
                initial_tokens=1,
            )
            ctx.wire.add_node(d_pulse)
            ctx.wire.connect(d_pulse_id, "out", subgraph.bleacher.id, BleacherSpec.pulse.name)
~~~~~

#### Acts 3: 重构 ObservabilityWiringPolicy
使用 `ObservabilitySpec`, `BleacherSpec`, `StainerSpec` 替换字符串字面量。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/observability.py
~~~~~
~~~~~python.old
import sys
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.triad import ObservabilityNode
from cascade.spec.physical.ports import PortRole, PortDef
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy


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
~~~~~python.new
import sys
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.triad import ObservabilityNode
from cascade.spec.physical.ports import PortRole, PortDef
from cascade.std.specs import ObservabilitySpec, BleacherSpec, StainerSpec
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy


class ObservabilityWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:
        d_life_id = PhysicalIdGenerator.observability_bus()
        f_obs_id = PhysicalIdGenerator.observability_observer()

        # Capacity set to maxsize to prevent backpressure from observability
        d_life = PhysicsDataNode(
            id=d_life_id, name="LifecycleBus", capacity=sys.maxsize
        )
        
        # Use Spec to define ports
        spec = ObservabilitySpec
        f_obs = ObservabilityNode(
            id=f_obs_id,
            name="LifecycleObserver",
            input_ports={
                spec.event_token.name: PortDef(spec.event_token.name, PortRole.OBSERVABILITY, "Event")
            },
            output_ports={},  # Observer emits to the outside world, not back into the graph
        )
        ctx.wire.add_node(d_life)
        ctx.wire.add_node(f_obs)

        ctx.wire.connect(d_life_id, "out", f_obs_id, spec.event_token.name)

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None
        assert subgraph.stainer is not None

        d_life_id = PhysicalIdGenerator.observability_bus()

        # Wire task observability TO the sidecar bus
        ctx.wire.connect(subgraph.bleacher.id, BleacherSpec.obs_output.name, d_life_id, "in")
        ctx.wire.connect(subgraph.stainer.id, StainerSpec.obs_output.name, d_life_id, "in")
~~~~~

### 下一步建议
Batch 1 完成后，我们将继续实施 Batch 2：重构 Control Flow 和 Parameter 连线，处理 `condition` 和 `wait_for` 依赖。
