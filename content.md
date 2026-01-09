简要回答
我们将在 `cascade-std` 包中创建 `specs` 模块，并基于 `PhysicsSpec` 实现 Resource、Triad 和 System 三类集成电路 (IC) 的标准物理契约，显式化现有的隐式端口定义。

## [WIP] feat: 实施 PIDL 阶段二 - 标准化物理契约

### 用户需求
在 `cascade-std` 包中标准化现有的物理节点契约。具体包括：
1.  创建 `cascade.std.specs` 包结构。
2.  **Resource Specs**: 定义 `DiscreteAllocatorSpec` 和 `DiscreteReclaimerSpec`。
3.  **Triad Specs**: 定义 `BleacherSpec`, `WorkerSpec`, `StainerSpec`。
4.  **System Specs**: 定义 `EgressSpec`, `GateSpec`, `SleepSpec`。

### 评论
这是将 PIDL 付诸实践的第一步。通过这些 Spec 类，我们不仅记录了当前 Kernel 函数的输入输出接口，还为后续的 Kernel 重构（使用 `@implements(Spec)`）和 Compiler 连线策略（引用 `Spec.port.name`）提供了唯一的真理来源 (SSoT)。这也解决了 Python 关键字冲突的问题（如 Egress 的输入端口名为 `in`，但在 Spec 类中可以绑定到 `input_token` 属性）。

### 目标
在 `packages/cascade-std/src/cascade/std/specs/` 目录下完成 `resource.py`, `triad.py`, `system.py` 和 `__init__.py` 的创建。

### 基本原理
我们将使用阶段一定义的 `cascade.spec.physics` 原语。
*   **属性命名与端口命名分离**: 利用 `PortDef` 的特性，类属性名（如 `input_token`）用于代码引用，而传递给 `Port.Input("in")` 的字符串才是物理层实际使用的端口名。这优雅地处理了 `in` 等保留字问题。
*   **类型提示**: 虽然 Python 运行时不强制类型，但在 Spec 中明确 `type=PortType.Ledger` 等信息，为未来的静态分析和可视化提供了语义基础。

### 标签
#intent/build #flow/ready #priority/high #comp/std #comp/interfaces #concept/spec #scope/core #ai/instruct #task/domain/core #task/object/std-specs #task/action/standardization #task/state/continue

---

### Script

#### Acts 1: 创建 Specs 目录

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-std/src/cascade/std/specs
~~~~~

#### Acts 2: 定义资源类契约 (Resource Specs)

创建 `resource.py`，定义离散资源分配器和回收器的端口契约。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/specs/resource.py
~~~~~
~~~~~python
from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType


class DiscreteAllocatorSpec(PhysicsSpec):
    """
    Contract for a Discrete Resource Allocator.
    Manages the distribution of countable resource units from a ledger.
    """
    # Inputs
    ledger_in = Port.Input("ledger_in", role=PortRole.DATA, type=PortType.Ledger)
    req_in = Port.Input("req_in", role=PortRole.DATA, type=PortType.Token)

    # Outputs
    ledger_out = Port.Output("ledger_out", role=PortRole.DATA, type=PortType.Ledger)
    # Note: The main grant output. Dynamic dedicated ports (gnt_for_X) may also exist.
    gnt_out = Port.Output("gnt_out", role=PortRole.RESOURCE, type=PortType.Token)
    # Output for requests that cannot be satisfied immediately
    req_parked = Port.Output("req_parked", role=PortRole.DATA, type=PortType.Token)


class DiscreteReclaimerSpec(PhysicsSpec):
    """
    Contract for a Discrete Resource Reclaimer.
    Handles the return of resource units to the ledger.
    """
    # Inputs
    ledger_in = Port.Input("ledger_in", role=PortRole.DATA, type=PortType.Ledger)
    rel_in = Port.Input("rel_in", role=PortRole.DATA, type=PortType.Token)

    # Outputs
    ledger_out = Port.Output("ledger_out", role=PortRole.DATA, type=PortType.Ledger)
    # Signal emitted to wake up parked requests
    signal_out = Port.Output("signal_out", role=PortRole.SIGNAL, type=PortType.Token)
~~~~~

#### Acts 3: 定义三连体契约 (Triad Specs)

创建 `triad.py`，定义 Bleacher, Worker 和 Stainer 的契约。注意 Bleacher 的输入端口是动态生成的，因此 Spec 主要定义其固定的输出接口。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/specs/triad.py
~~~~~
~~~~~python
from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType


class BleacherSpec(PhysicsSpec):
    """
    Contract for the Pre-process Node (F_pre).
    Inputs are dynamic (based on Task arguments), so they are not exhaustively listed here.
    """
    # Outputs
    worker_input = Port.Output("worker_input", role=PortRole.DATA, type="Dict")
    trace_output = Port.Output("trace_output", role=PortRole.DATA, type="TraceCtx")
    context_output = Port.Output("context_output", role=PortRole.DATA, type="Dict")
    obs_output = Port.Output("obs_output", role=PortRole.OBSERVABILITY, type="Event")


class WorkerSpec(PhysicsSpec):
    """
    Contract for the Execution Node (F_exec).
    Pure business logic execution.
    """
    # Inputs
    worker_input = Port.Input("worker_input", role=PortRole.DATA, type="Dict")

    # Outputs
    worker_result = Port.Output("worker_result", role=PortRole.DATA, type=PortType.Any)


class StainerSpec(PhysicsSpec):
    """
    Contract for the Post-process Node (F_post).
    Wraps results and handles routing.
    """
    # Inputs
    worker_result = Port.Input("worker_result", role=PortRole.DATA, type=PortType.Any)
    trace_input = Port.Input("trace_input", role=PortRole.DATA, type="TraceCtx")
    context_input = Port.Input("context_input", role=PortRole.DATA, type="Dict")

    # Outputs
    output_default = Port.Output("output_default", role=PortRole.DATA, type=PortType.Token)
    output_error = Port.Output("output_error", role=PortRole.DATA, type=PortType.Token)
    obs_output = Port.Output("obs_output", role=PortRole.OBSERVABILITY, type="Event")
    # Resource returns are dynamic
~~~~~

#### Acts 4: 定义系统类契约 (System Specs)

创建 `system.py`，定义 Egress, Gate 和 Sleep 等控制节点的契约。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/specs/system.py
~~~~~
~~~~~python
from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType


class EgressSpec(PhysicsSpec):
    """
    Contract for the Egress Node.
    Acts as a sink for graph results.
    """
    # The physical port name is "in" (reserved keyword in Python).
    # We map it to the attribute 'input_token'.
    input_token = Port.Input("in", role=PortRole.DATA, type=PortType.Token)


class GateSpec(PhysicsSpec):
    """
    Contract for a Control Gate.
    Passes req_in to req_out only when signal_in receives a token.
    """
    req_in = Port.Input("req_in", role=PortRole.DATA)
    signal_in = Port.Input("signal_in", role=PortRole.SIGNAL)
    
    req_out = Port.Output("req_out", role=PortRole.DATA)


class SleepSpec(PhysicsSpec):
    """
    Contract for the Time Delay Node.
    """
    delay_in = Port.Input("delay_in", role=PortRole.DATA, type="float")
    data_in = Port.Input("data_in", role=PortRole.DATA, type=PortType.Token)
    # No outputs (Void) - flow resumes via ChronosService injection
~~~~~

#### Acts 5: 导出所有 Specs

~~~~~act
write_file
packages/cascade-std/src/cascade/std/specs/__init__.py
~~~~~
~~~~~python
from .resource import DiscreteAllocatorSpec, DiscreteReclaimerSpec
from .triad import BleacherSpec, WorkerSpec, StainerSpec
from .system import EgressSpec, GateSpec, SleepSpec

__all__ = [
    "DiscreteAllocatorSpec",
    "DiscreteReclaimerSpec",
    "BleacherSpec",
    "WorkerSpec",
    "StainerSpec",
    "EgressSpec",
    "GateSpec",
    "SleepSpec",
]
~~~~~

### 下一步建议
我们已经完成了 Spec 的定义。接下来的 **阶段三：Kernel 实现重构 (The Implementation)** 是最具挑战性的部分。我们需要：
1.  在 `cascade.std` 中引入装饰器（如 `@implements` 或简单的类型检查工具）。
2.  修改 Kernel 函数，使其签名与我们刚刚定义的 Spec 保持一致（或通过装饰器适配）。
3.  确保修改后的 Kernel 依然能通过现有的测试。

建议先从最简单的 `Egress` 或 `Gate` 开始进行重构试点。
