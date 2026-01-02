你完全正确，感谢提供这个关键的 `AttributeError` Traceback。

这正是 TDD 流程的价值所在：静态类型检查 (`pyright`) 暴露了类型不匹配，而单元测试 (`pytest`) 在运行时精确地捕获了错误的对象状态。我的上一个计划在修正 `Expander` 时显然是有缺陷的。

错误分析：
`AttributeError: 'str' object has no attribute 'role'` 清楚地表明，`Expander` 在创建 `BleachNode` 时，其 `input_ports` 字典的值仍然是字符串 (`"Any"`)，而不是我意图创建的 `PortDef` 对象。

为了确保这次修复的原子性和正确性，我将采用更稳健的策略：使用 `write_file` 完整地重写 `expander.py`，而不是依赖多个可能失败的 `patch_file` 操作。这符合我们对于结构性重构的规范。

这是修正后的计划。

## [WIP] feat(compiler): implement Precision Ports (Phase 1 Fix)

### 错误分析
`test_expander.py` 测试失败，抛出 `AttributeError`，原因是 `Expander` 模块未能正确地将端口定义从 `str` 升级为 `PortDef` 对象，导致下游代码在访问 `.role` 属性时失败。上一个计划中的 `patch_file` 指令未能正确应用或存在逻辑错误。

### 用户需求
推进 "Cascade 3.1 路线图：精密端口" 至阶段 1。消除 `pyright` 报错和 `pytest` 运行时错误，使编译器后端能正确生成包含 `PortDef` 和 `PortRole` 的物理节点。

### 评论
这是一个纠正性的计划。通过使用 `write_file` 来替换整个 `expander.py` 文件，我们可以保证修改的原子性，避免因 `patch_file` 上下文不匹配而导致的局部失败。此计划将使编译器与其依赖的 `cascade-spec` 规范完全对齐。

### 目标
1.  使用 `write_file` 彻底重构 `expander.py`，使其在所有节点创建时都使用 `PortDef`。
2.  重构 `Builder`，在生成 `ObservabilityNode` 时使用 `PortDef`。
3.  更新编译器单元测试 (`test_expander.py`)，断言新生成的 `PortDef` 对象的 `role` 属性，确保正确性。

### 基本原理
编译器的职责是将逻辑 IR 转换为物理真理。端口角色是物理真理的一部分。

*   **资源端口**: 标记为 `PortRole.RESOURCE`。
*   **观测端口** (`obs_output`, `event_token`): 标记为 `PortRole.OBSERVABILITY`。
*   **数据端口** (Args, Worker Input/Output, Trace): 标记为 `PortRole.DATA`。

### 标签
#intent/fix #flow/ready #priority/high #comp/compiler #scope/core #ai/instruct #task/domain/core #task/object/compiler #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 重构 Expander (`cascade-compiler`)

我们将使用 `write_file` 完整替换 `expander.py` 的内容，以确保所有 `PhysicsFuncNode` 的实例化都使用新的 `PortDef` 结构。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsNode, PhysicsDataNode
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.topology import Channel
from cascade.spec.ports import PortDef, PortRole
from cascade.compiler.utils.naming import PhysicalIdGenerator


@dataclass
class SubGraph:
    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    channels: List[Channel] = field(default_factory=list)

    # Interface pointers
    bleacher: Optional[BleachNode] = None
    stainer: Optional[StainNode] = None


class Expander:
    def expand_node(self, node_ir: NodeIR) -> SubGraph:
        subgraph = SubGraph()

        # 1. Generate IDs for all physical entities
        # We use the logical node ID as a prefix to ensure uniqueness.
        base_id = node_ir.id

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
        f_worker = WorkerNode(
            id=f_worker_id,
            name=f"Exec({node_ir.name})",
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
        stainer_outputs = {
            "output": PortDef("output", PortRole.DATA, "Token"),
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

#### Acts 2: 重构 Builder (`cascade-compiler`)

修改 `Builder` 以正确构建全局观测节点。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode
from cascade.spec.triad import ObservabilityNode
from cascade.spec.environment import EnvironmentDef
from .expander import Expander, SubGraph
from cascade.compiler.utils.naming import PhysicalIdGenerator
~~~~~
~~~~~python.new
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode
from cascade.spec.triad import ObservabilityNode
from cascade.spec.environment import EnvironmentDef
from cascade.spec.ports import PortDef, PortRole
from .expander import Expander, SubGraph
from cascade.compiler.utils.naming import PhysicalIdGenerator
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
        f_obs = ObservabilityNode(
            id=f_obs_id,
            name="LifecycleObserver",
            input_ports={"event_token": "Event"},
            output_ports={},  # Observer emits to the outside world, not back into the graph
        )
~~~~~
~~~~~python.new
        f_obs = ObservabilityNode(
            id=f_obs_id,
            name="LifecycleObserver",
            input_ports={
                "event_token": PortDef("event_token", PortRole.OBSERVABILITY, "Event")
            },
            output_ports={},  # Observer emits to the outside world, not back into the graph
        )
~~~~~

#### Acts 3: 更新编译器单元测试

最后，更新 `test_expander.py` 的测试断言，以验证 `PortDef` 对象的正确性。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_expander.py
~~~~~
~~~~~python.old
from cascade.spec.ir.models import NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.compiler.backend.expander import Expander
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.physics import PhysicsDataNode
~~~~~
~~~~~python.new
from cascade.spec.ir.models import NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.ports import PortRole
from cascade.compiler.backend.expander import Expander
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.physics import PhysicsDataNode
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_expander.py
~~~~~
~~~~~python.old
    # Verify connections
    # Bleach -> Trace
    trace_channel = next(
        c
        for c in subgraph.channels
        if c.source_node_id == bleacher.id and c.target_node_id == d_trace.id
    )
    assert trace_channel.source_port == "trace_output"

    # Trace -> Stain
    trace_in_channel = next(
        c
        for c in subgraph.channels
        if c.source_node_id == d_trace.id and c.target_node_id == stainer.id
    )
    assert trace_in_channel.source_port == "out"  # implicit port for data node
~~~~~
~~~~~python.new
    # Verify connections
    # Bleach -> Trace
    trace_channel = next(
        c
        for c in subgraph.channels
        if c.source_node_id == bleacher.id and c.target_node_id == d_trace.id
    )
    assert trace_channel.source_port == "trace_output"

    # Verify Port Definitions
    assert "x" in bleacher.input_ports
    assert bleacher.input_ports["x"].role == PortRole.DATA
    assert bleacher.output_ports["trace_output"].role == PortRole.DATA
    assert bleacher.output_ports["obs_output"].role == PortRole.OBSERVABILITY

    assert stainer.input_ports["worker_result"].role == PortRole.DATA
    assert stainer.output_ports["output"].role == PortRole.DATA

    # Trace -> Stain
    trace_in_channel = next(
        c
        for c in subgraph.channels
        if c.source_node_id == d_trace.id and c.target_node_id == stainer.id
    )
    assert trace_in_channel.source_port == "out"  # implicit port for data node
~~~~~

### 下一步建议
阶段 1 完成后，`pyright` 应该不再报错，所有测试应该恢复为 **GREEN**。
接下来进入 **阶段 2：执行 - 强化虚拟机指令**，我们将修改 `bleacher.py` 和 `stainer.py`，彻底移除基于字符串的“排除法”逻辑，转而使用 `PortDef.role`。
