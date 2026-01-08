遵循“少即是多”和“消除魔法字符串”的原则，我们将首先建立物理层原子节点的命名规范。

这个计划将创建一个新的常量定义文件，并重构 ID 生成器和编译器后端，使其依赖于这些权威的常量，而不是分散的字符串字面量。

我们将引入 `cascade.spec.physical.constants` 模块来定义 `NodePrefix` 等核心常量，并重构 `PhysicalIdGenerator` 和编译器策略以完全遵循此规范。

## [WIP] refactor(spec): 标准化物理层原子节点命名与常量

### 用户需求
1.  消除物理层代码中关于节点 ID（如 `"const."`, `"pulse."`）的硬编码字符串。
2.  统一物理层原子节点（`D_const`, `D_pulse`, `D_ledger` 等）的命名规范。

### 评论
这是迈向“确定性构建”的关键一步。通过将这些协议级的字符串提升为类型安全的常量，我们消除了拼写错误导致的隐性 Bug，并为未来的重构（如更改 ID 结构）提供了中心化的修改点。这也让代码的意图更加清晰——我们是在检查“这是一个常量节点吗”，而不是“这个字符串是以 c 开头的吗”。

### 目标
1.  创建 `cascade-spec/src/cascade/spec/physical/constants.py`，定义 `NodePrefix` 枚举。
2.  重构 `cascade-reflection` 中的 `PhysicalIdGenerator`，使其成为这些常量的唯一组装工厂。
3.  重构 `cascade-compiler` 中的 `Builder` 和相关 `Policy`，将硬编码字符串替换为对 `NodePrefix` 的引用。

### 基本原理
目前的 ID 生成逻辑分散在 `naming.py` 和编译器的各个策略中，且存在直接使用字符串字面量进行判断（`startswith`）的情况。这种“魔法字符串”是维护的噩梦。通过引入 `NodePrefix`，我们在 Spec 层面确立了物理世界的本体论分类。

### 标签
#intent/refine #flow/ready #priority/high #comp/interfaces #comp/compiler #scope/core #task/domain/physics #task/object/primitives #task/action/standardize #task/state/begin

---

### Script

#### Acts 1: 定义物理层常量

我们首先在 Spec 包中创建一个新的常量文件，定义所有标准的节点前缀。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/physical/constants.py
~~~~~
~~~~~python
from enum import StrEnum


class NodePrefix(StrEnum):
    """
    Standard prefixes for Physical Node IDs.
    These define the 'Atomic Type' of the node in the physical topology.
    """

    # Data Nodes (Places)
    CONST = "const"  # Constant value holder
    PULSE = "pulse"  # Event trigger (0 tokens, infinite capacity)
    LEDGER = "ledger"  # Resource state holder
    BUFFER = "buffer"  # Queue for resources or data
    PARKED = "parked"  # Parking lot for pending requests
    SIGNAL = "signal"  # Signaling channel
    EGRESS = "egress"  # Exit point
    INGRESS = "ingress"  # Entry point (reserved)

    # Function Nodes (Transitions)
    BLEACH = "bleach"  # Triad: Pre-process
    WORKER = "worker"  # Triad: Execution
    STAIN = "stain"    # Triad: Post-process
    REQ = "req"        # Resource Requestor
    GATE = "gate"      # Control Gate
    PROBE = "probe"    # Introspection Probe

    # Global/System
    GLOBAL = "global"  # Global singleton
    CANONICAL = "canonical"  # Canonical resource broker
~~~~~

#### Acts 2: 更新 PhysicalIdGenerator

接着，我们修改 ID 生成器，使其严格使用上述常量。

~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/naming.py
~~~~~
~~~~~python.old
    @staticmethod
    def bleach_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.bleach"

    @staticmethod
    def worker_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.worker"

    @staticmethod
    def stain_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.stain"

    @staticmethod
    def worker_in_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.in"

    @staticmethod
    def worker_out_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.out"

    @staticmethod
    def trace_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.trace"

    @staticmethod
    def context_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.context"

    @staticmethod
    def global_resource(resource_name: str) -> str:
        # Legacy: Keeping it for D_res if needed, but we are moving to brokers
        return f"canonical.resource.{resource_name}"

    @staticmethod
    def global_allocator(resource_name: str) -> str:
        return f"canonical.resource.allocator.{resource_name}"

    @staticmethod
    def global_reclaimer(resource_name: str) -> str:
        return f"canonical.resource.reclaimer.{resource_name}"

    @staticmethod
    def global_ledger(resource_name: str) -> str:
        return f"canonical.resource.ledger.{resource_name}"

    @staticmethod
    def requestor(target_node_id: str, resource_name: str) -> str:
        return f"req.{target_node_id}.{resource_name}"

    @staticmethod
    def probe_const(target_node_id: str, arg_name: str) -> str:
        return f"probe.const.{target_node_id}.{arg_name}"

    @staticmethod
    def constant(target_node_id: str, arg_name: str) -> str:
        # The DataNode holding the constant value
        return f"const.{target_node_id}.{arg_name}"

    @staticmethod
    def observability_bus() -> str:
        return "global.observability.bus"

    @staticmethod
    def observability_observer() -> str:
        return "global.observability.observer"

    @staticmethod
    def pulse_source(logical_node_id: str) -> str:
        return f"pulse.source.{logical_node_id}"
~~~~~
~~~~~python.new
    @staticmethod
    def bleach_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.BLEACH}"

    @staticmethod
    def worker_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.WORKER}"

    @staticmethod
    def stain_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.STAIN}"

    @staticmethod
    def worker_in_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.in"

    @staticmethod
    def worker_out_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.out"

    @staticmethod
    def trace_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.trace"

    @staticmethod
    def context_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.context"

    @staticmethod
    def global_resource(resource_name: str) -> str:
        # Legacy: Keeping it for D_res if needed, but we are moving to brokers
        return f"{NodePrefix.CANONICAL}.resource.{resource_name}"

    @staticmethod
    def global_allocator(resource_name: str) -> str:
        return f"{NodePrefix.CANONICAL}.resource.allocator.{resource_name}"

    @staticmethod
    def global_reclaimer(resource_name: str) -> str:
        return f"{NodePrefix.CANONICAL}.resource.reclaimer.{resource_name}"

    @staticmethod
    def global_ledger(resource_name: str) -> str:
        return f"{NodePrefix.CANONICAL}.resource.{NodePrefix.LEDGER}.{resource_name}"

    @staticmethod
    def requestor(target_node_id: str, resource_name: str) -> str:
        return f"{NodePrefix.REQ}.{target_node_id}.{resource_name}"

    @staticmethod
    def probe_const(target_node_id: str, arg_name: str) -> str:
        return f"{NodePrefix.PROBE}.{NodePrefix.CONST}.{target_node_id}.{arg_name}"

    @staticmethod
    def constant(target_node_id: str, arg_name: str) -> str:
        # The DataNode holding the constant value
        return f"{NodePrefix.CONST}.{target_node_id}.{arg_name}"

    @staticmethod
    def observability_bus() -> str:
        return f"{NodePrefix.GLOBAL}.observability.bus"

    @staticmethod
    def observability_observer() -> str:
        return f"{NodePrefix.GLOBAL}.observability.observer"

    @staticmethod
    def pulse_source(logical_node_id: str) -> str:
        return f"{NodePrefix.PULSE}.source.{logical_node_id}"
~~~~~

#### Acts 3: 导入依赖

我们需要在 `naming.py` 头部导入新定义的 `NodePrefix`。

~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/naming.py
~~~~~
~~~~~python.old
class PhysicalIdGenerator:
    @staticmethod
~~~~~
~~~~~python.new
from cascade.spec.physical.constants import NodePrefix


class PhysicalIdGenerator:
    @staticmethod
~~~~~

#### Acts 4: 更新 Compiler Builder 的入口扫描逻辑

现在，我们将替换编译器中用于识别 Entry Point 和 Exit Point 的硬编码字符串。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
from cascade.compiler.wiring.policies.pulse import PulseWiringPolicy


class Builder:
    def __init__(self):
~~~~~
~~~~~python.new
from cascade.compiler.wiring.policies.pulse import PulseWiringPolicy
from cascade.spec.physical.constants import NodePrefix


class Builder:
    def __init__(self):
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
        entry_points = [
            node_id
            for node_id, node in physical_graph.nodes.items()
            if isinstance(node, PhysicsDataNode)
            and (node_id.startswith("const.") or node_id.startswith("pulse."))
        ]
        exit_points = {
            node.id.split(".")[1]: node.id
            for node in physical_graph.nodes.values()
            if isinstance(node, PhysicsDataNode) and node.id.startswith("egress.")
        }
~~~~~
~~~~~python.new
        entry_points = [
            node_id
            for node_id, node in physical_graph.nodes.items()
            if isinstance(node, PhysicsDataNode)
            and (
                node_id.startswith(f"{NodePrefix.CONST}.")
                or node_id.startswith(f"{NodePrefix.PULSE}.")
            )
        ]
        exit_points = {
            node.id.split(".")[1]: node.id
            for node in physical_graph.nodes.values()
            if isinstance(node, PhysicsDataNode)
            and node.id.startswith(f"{NodePrefix.EGRESS}.")
        }
~~~~~

#### Acts 5: 更新 Control Wiring Policy

替换 `control.py` 中 `egress` 相关的硬编码。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/wiring/policies/control.py
~~~~~
~~~~~python.old
from cascade.compiler.wiring.protocol import WiringPolicy


class ControlFlowWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
~~~~~
~~~~~python.new
from cascade.compiler.wiring.protocol import WiringPolicy
from cascade.spec.physical.constants import NodePrefix


class ControlFlowWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/wiring/policies/control.py
~~~~~
~~~~~python.old
        # 4.4 Egress for Root Nodes
        if node_ir.logical_id in ctx.graph_ir.root_logical_ids:
            assert subgraph.stainer is not None
            # Create a dedicated, addressable exit point for this graph root
            d_egress_id = f"egress.{node_ir.logical_id}"
            d_egress = PhysicsDataNode(id=d_egress_id, name=f"Egress({node_ir.name})")
            ctx.wire.add_node(d_egress)

            # Connect the stainer's default output to this egress node
            ctx.wire.connect(subgraph.stainer.id, "output_default", d_egress_id, "in")
~~~~~
~~~~~python.new
        # 4.4 Egress for Root Nodes
        if node_ir.logical_id in ctx.graph_ir.root_logical_ids:
            assert subgraph.stainer is not None
            # Create a dedicated, addressable exit point for this graph root
            d_egress_id = f"{NodePrefix.EGRESS}.{node_ir.logical_id}"
            d_egress = PhysicsDataNode(id=d_egress_id, name=f"Egress({node_ir.name})")
            ctx.wire.add_node(d_egress)

            # Connect the stainer's default output to this egress node
            ctx.wire.connect(subgraph.stainer.id, "output_default", d_egress_id, "in")
~~~~~

#### Acts 6: 更新 Linker

最后，更新 `Linker` 中的硬编码匹配逻辑。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/linker.py
~~~~~
~~~~~python.old
from cascade.std.system.gate import gate_passthrough


class LinkerError(RuntimeError):
    pass
~~~~~
~~~~~python.new
from cascade.std.system.gate import gate_passthrough
from cascade.spec.physical.constants import NodePrefix


class LinkerError(RuntimeError):
    pass
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/linker.py
~~~~~
~~~~~python.old
    def _resolve_stdlib(self, node_id: str) -> Optional[Callable]:
        # Triad
        if node_id.endswith(".bleach"):
            return standard_bleacher
        if node_id.endswith(".stain"):
            return standard_stainer

        # Observability
        if node_id == PhysicalIdGenerator.observability_observer():
            return standard_observer

        # Resources
        if "allocator" in node_id:
            return discrete_allocator
        if "reclaimer" in node_id:
            return discrete_reclaimer
        if node_id.startswith("req."):
            return resource_requestor
        if "gate.wakeup" in node_id:
            return gate_passthrough

        # System / Egress
        if node_id.startswith("egress."):
            return standard_egress

        return None
~~~~~
~~~~~python.new
    def _resolve_stdlib(self, node_id: str) -> Optional[Callable]:
        # Triad
        if node_id.endswith(f".{NodePrefix.BLEACH}"):
            return standard_bleacher
        if node_id.endswith(f".{NodePrefix.STAIN}"):
            return standard_stainer

        # Observability
        if node_id == PhysicalIdGenerator.observability_observer():
            return standard_observer

        # Resources
        if "allocator" in node_id:
            return discrete_allocator
        if "reclaimer" in node_id:
            return discrete_reclaimer
        if node_id.startswith(f"{NodePrefix.REQ}."):
            return resource_requestor
        if f"{NodePrefix.GATE}.wakeup" in node_id:
            return gate_passthrough

        # System / Egress
        if node_id.startswith(f"{NodePrefix.EGRESS}."):
            return standard_egress

        return None
~~~~~

### 下一步建议
我们已经建立了物理节点的命名规范，下一步可以开始引入 `ChronosService`。这涉及：
1.  在 `cascade.vm` 中创建 `services/chronos.py`。
2.  定义 `DelayRequest` 数据结构。
3.  将服务集成到 `Machine` 循环中。
