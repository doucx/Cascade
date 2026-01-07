好的，我将开始实施“架构演进提案：资源调度的‘拓扑门控’模型”。

这是一个重要的架构升级，旨在用一个事件驱动的、零开销的拓扑结构，取代当前资源分配器中存在的“忙等待”自旋循环。这将显著提升系统在资源竞争激烈时的效率和可观测性。

我将分阶段进行：
1.  **扩展物理层规范**：在 `cascade-spec` 中为新的信息流（如 `req_parked`, `signal_out`）添加端口定义。
2.  **修改标准库（Stdlib）**：更新 `discrete_allocator` 和 `discrete_reclaimer` 的实现，使其支持新的端口和逻辑。
3.  **实现门控逻辑**：创建一个新的 `gate` 内核函数，作为唤醒机制的核心。
4.  **重构编译器**：修改 `DiscreteResourcePrism`，在物理图中构建新的“停车场”拓扑，并移除旧的循环。
5.  **更新链接器**：让链接器识别并链接新的 `F_gate` 节点。

以下是详细的实施计划。

## [WIP] feat(compiler): 实现资源调度的“拓扑门控”模型

### 用户需求
根据《架构演进提案：资源调度的“拓扑门控”模型》，需要重构当前的资源调度机制。核心目标是消除 `F_allocator` 在资源不足时产生的“忙等待”循环，代之以一个事件驱动的、零资源消耗的“停车场”拓扑。

### 评论
这是一个卓越的架构改进。将隐式的、算法性的调度逻辑（自旋重试）转化为显式的、物理化的拓扑结构（门控节点），完美契合了 Cascade “拓扑即计算”的核心哲学。

此变更将带来三大好处：
1.  **效率**: 在资源等待期间，系统能耗将趋近于零。
2.  **可观测性**: 阻塞状态（`D_parked`）和唤醒事件（`D_signal`）将成为图中可度量的物理实体。
3.  **解耦**: `F_allocator`、`F_reclaimer` 和 `F_gate` 的职责更加单一，易于独立演化和测试。

### 目标
1.  为 `cascade-spec` 添加新的物理端口名称 `REQ_PARKED` 和 `SIGNAL_OUT`。
2.  修改 `discrete_allocator` 和 `discrete_reclaimer` 的内核函数，使其支持新的“停泊请求”和“释放信号”逻辑。
3.  实现一个新的内核函数 `gate_passthrough`，用于 `F_gate` 节点。
4.  在 `DiscreteResourcePrism` 中，拆除旧的请求循环拓扑，并构建新的“停车场”和“唤醒总线”拓扑。
5.  更新 `Linker`，使其能够识别并链接新的 `F_gate` 节点。

### 基本原理
我们将通过修改 `cascade-compiler` 中的 `DiscreteResourcePrism` 来从根本上改变资源管理的物理信息流。

1.  **拒绝流程**: 当 `F_allocator` 拒绝一个请求时，它将不再通过 `REQ_OUT` 将令牌送回请求缓冲区，而是通过新的 `REQ_PARKED` 端口发送到一个专用的 `D_parked`（停泊区）数据节点。
2.  **释放流程**: 当 `F_reclaimer` 回收一个资源时，除了更新账本，它还将通过新的 `SIGNAL_OUT` 端口向一个专用的 `D_signal`（唤醒总线）数据节点发射一个“脉冲”令牌。
3.  **唤醒流程**: 新增一个 `F_gate`（门控）函数节点，它被设计为只有在同时从 `D_parked` 和 `D_signal` 接收到令牌时才会被激发。一旦激发，它会将请求令牌从 `D_parked` 移回主请求缓冲区 `D_req`，使其重新进入分配流程。

这个设计彻底切断了高频的“请求-拒绝”循环，将系统转变为一个高效的、事件驱动的状态机。

### 标签
#intent/architect #flow/ready #priority/high #comp/compiler #comp/std #comp/spec #comp/vm #concept/resource-management #scope/core #ai/instruct #task/domain/architecture #task/object/resource-scheduling #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 在 `cascade-spec` 中定义新的物理端口

首先，我们需要在端口规范中添加新的端口名称，为后续的编译器和标准库修改提供依据。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/ports.py
~~~~~
~~~~~python.old
    GNT = "gnt_out"
    REQ_OUT = "req_out"  # For recirculation
    LEDGER_IN = "ledger_in"
    LEDGER_OUT = "ledger_out"
~~~~~
~~~~~python.new
    GNT = "gnt_out"
    REQ_OUT = "req_out"  # For recirculation
    REQ_PARKED = "req_parked"  # For parking rejected requests
    SIGNAL_OUT = "signal_out"  # For wake-up signals
    LEDGER_IN = "ledger_in"
    LEDGER_OUT = "ledger_out"
~~~~~

#### Acts 2: 更新 `cascade-std` 中资源管理内核函数的实现

接下来，我们修改 `discrete_allocator` 和 `discrete_reclaimer` 的具体实现，让它们使用新的端口逻辑。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
from typing import Dict, Any, Union
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.physical.object import Ref
~~~~~
~~~~~python.new
from typing import Dict, Any, Union
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.physical.object import Ref
from cascade.spec.physical.ports import PortName
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
    else:
        # Reject & Recirculate
        outputs["req_out"] = req_token
~~~~~
~~~~~python.new
    else:
        # Reject & Park
        outputs[PortName.REQ_PARKED] = req_token
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
    # Replenish
    ledger.available = min(ledger.total, ledger.available + release_amount)

    return {"ledger_out": Token(payload=ledger)}
~~~~~
~~~~~python.new
    # Replenish
    ledger.available = min(ledger.total, ledger.available + release_amount)

    outputs = {"ledger_out": Token(payload=ledger)}
    # Emit wake-up signal
    outputs[PortName.SIGNAL_OUT] = Token(payload=None, trace=rel_token.trace)

    return outputs
~~~~~

#### Acts 3: 添加新的 `gate` 内核函数

我们需要一个新的、简单的内核函数来实现 `F_gate` 的逻辑：当收到两个输入时，将其中一个（请求）传递下去。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/system/gate.py
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode


def gate_passthrough(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    """
    A simple gate that requires two inputs (a request and a signal)
    and passes the request token through.
    """
    # We expect 'req_in' and 'signal_in' ports
    req_token = inputs.get("req_in")
    signal_token = inputs.get("signal_in")

    if req_token and signal_token:
        # The gate is open, pass the request token through
        return {"req_out": req_token}

    # Should not happen if wired correctly, but return empty if not fully triggered
    return {}
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/__init__.py
~~~~~
~~~~~python.old
# System Control ICs for graph lifecycle management (Sovereignty).
~~~~~
~~~~~python.new
# System Control ICs for graph lifecycle management (Sovereignty).
from .gate import gate_passthrough

__all__ = ["gate_passthrough"]
~~~~~

#### Acts 4: 重构编译器中的 `DiscreteResourcePrism`

这是核心步骤。我们将修改 `ensure_globals` 方法，构建新的拓扑结构。

首先，更新 `F_allocator` 和 `F_reclaimer` 的节点定义。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/wiring/prisms/discrete.py
~~~~~
~~~~~python.old
            output_ports={
                PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
            },
        )
        ctx.wire.add_node(f_reclaimer)

        # F_allocator
        f_allocator = PhysicsFuncNode(
            id=allocator_id,
            name=f"Allocator({res_def.name})",
            input_ports={
                PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                PortName.REQ: PortDef(PortName.REQ, PortRole.DATA),
            },
            output_ports={
                PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                PortName.GNT: PortDef(PortName.GNT, PortRole.RESOURCE),
                PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA),
            },
        )
~~~~~
~~~~~python.new
            output_ports={
                PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                PortName.SIGNAL_OUT: PortDef(PortName.SIGNAL_OUT, PortRole.SIGNAL),
            },
        )
        ctx.wire.add_node(f_reclaimer)

        # F_allocator
        f_allocator = PhysicsFuncNode(
            id=allocator_id,
            name=f"Allocator({res_def.name})",
            input_ports={
                PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                PortName.REQ: PortDef(PortName.REQ, PortRole.DATA),
            },
            output_ports={
                PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                PortName.GNT: PortDef(PortName.GNT, PortRole.RESOURCE),
                PortName.REQ_PARKED: PortDef(PortName.REQ_PARKED, PortRole.DATA),
            },
        )
~~~~~

然后，用新的“停车场”拓扑替换旧的请求缓冲和再循环逻辑。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/wiring/prisms/discrete.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
        # Request Buffer
        d_req_buffer_id = f"buffer.req.{res_def.name}"
        d_req_buffer = PhysicsDataNode(
            id=d_req_buffer_id, name=f"ReqBuffer({res_def.name})", capacity=1000
        )
        ctx.wire.add_node(d_req_buffer)

        # Buffer -> Allocator
        ctx.wire.connect(d_req_buffer_id, "out", allocator_id, PortName.REQ)

        # --- Parking & Wake-up Mechanism ---
        # 1. New Nodes
        d_parked_id = f"parked.req.{res_def.name}"
        d_parked = PhysicsDataNode(id=d_parked_id, name=f"Parked({res_def.name})")
        ctx.wire.add_node(d_parked)

        d_signal_id = f"signal.wakeup.{res_def.name}"
        d_signal = PhysicsDataNode(id=d_signal_id, name=f"Signal({res_def.name})")
        ctx.wire.add_node(d_signal)

        f_gate_id = f"gate.wakeup.{res_def.name}"
        f_gate = PhysicsFuncNode(
            id=f_gate_id,
            name=f"Gate({res_def.name})",
            input_ports={
                "req_in": PortDef("req_in", PortRole.DATA),
                "signal_in": PortDef("signal_in", PortRole.SIGNAL),
            },
            output_ports={"req_out": PortDef("req_out", PortRole.DATA)},
        )
        ctx.wire.add_node(f_gate)

        # 2. New Wiring
        # Allocator parks rejected requests
        ctx.wire.connect(allocator_id, PortName.REQ_PARKED, d_parked_id, "in")
        # Reclaimer sends wake-up signal
        ctx.wire.connect(reclaimer_id, PortName.SIGNAL_OUT, d_signal_id, "in")
        # Gate is triggered by parked request and signal
        ctx.wire.connect(d_parked_id, "out", f_gate_id, "req_in")
        ctx.wire.connect(d_signal_id, "out", f_gate_id, "signal_in")
        # Gate sends request back to the main buffer for retry
        ctx.wire.connect(f_gate_id, "req_out", d_req_buffer_id, "in")

        # Release Buffer
        rel_buffer_id = f"buffer.rel.{res_def.name}"
~~~~~

#### Acts 5: 更新 `Linker`

最后，确保 `Linker` 知道如何处理我们新创建的 `F_gate` 节点。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/linker.py
~~~~~
~~~~~python.old
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.system.egress import standard_egress
~~~~~
~~~~~python.new
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.system.egress import standard_egress
from cascade.std.system.gate import gate_passthrough
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/linker.py
~~~~~
~~~~~python.old
        if "reclaimer" in node_id:
            return discrete_reclaimer
        if node_id.startswith("req."):
            return resource_requestor

        # System / Egress
        if node_id.startswith("egress."):
~~~~~
~~~~~python.new
        if "reclaimer" in node_id:
            return discrete_reclaimer
        if node_id.startswith("req."):
            return resource_requestor
        if "gate.wakeup" in node_id:
            return gate_passthrough

        # System / Egress
        if node_id.startswith("egress."):
~~~~~

### 下一步建议
我们已经完成了对“拓扑门控”模型的静态实现。下一步至关重要，是**验证其动态行为**。

我建议创建一个新的集成测试，专门用于模拟资源竞争激烈的场景：
1.  定义一个容量为1的离散资源。
2.  同时启动两个需要该资源的任务。
3.  **断言**：
    *   `F_allocator` 的 `req_parked` 端口被调用了一次。
    *   `D_parked` 节点中曾持有一个令牌。
    *   当第一个任务完成后，`F_reclaimer` 的 `signal_out` 端口被调用。
    *   `F_gate` 节点被成功激发。
    *   最终两个任务都成功完成。

这将为我们提供坚实的信心，确保新的事件驱动模型在实际运行中是正确且高效的。如果你同意，我将生成创建此测试的计划。
