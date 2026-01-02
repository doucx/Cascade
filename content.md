简要回答
执行阶段 1：重构 `Expander` 和 `Builder` 以生成 `PortDef` 对象，并同步更新相关的编译器单元测试。

## [WIP] feat(compiler): implement Precision Ports (Phase 1)

### 用户需求
推进 "Cascade 3.1 路线图：精密端口" 至阶段 1。消除 `pyright` 报错，使编译器后端能正确生成包含 `PortDef` 和 `PortRole` 的物理节点。

### 评论
这是使得代码库重新变绿的关键步骤。通过在 `Expander` 中显式指定端口角色（如将 `res_` 端口标记为 `RESOURCE`），我们将物理层的语义固化在图结构中，为后续 VM 移除“排除法”逻辑打下基础。

### 目标
1.  重构 `Expander`，在生成 `BleachNode`, `WorkerNode`, `StainNode` 时使用 `PortDef`。
2.  重构 `Builder`，在生成 `ObservabilityNode` 时使用 `PortDef`。
3.  更新编译器单元测试 (`test_expander.py`, `test_builder.py`) 以匹配新的对象结构。

### 基本原理
编译器的职责是将逻辑 IR 转换为物理真理。端口角色是物理真理的一部分。

*   **资源端口**: 标记为 `PortRole.RESOURCE`。
*   **观测端口** (`obs_output`, `event_token`): 标记为 `PortRole.OBSERVABILITY`。
*   **数据端口** (Args, Worker Input/Output, Trace): 标记为 `PortRole.DATA`。

### 标签
#intent/refactor #flow/ready #priority/high #comp/compiler #scope/core #ai/instruct #task/domain/core #task/object/compiler #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 重构 Expander (`cascade-compiler`)

我们修改 `Expander`，使其在构建节点时实例化 `PortDef`。特别注意对资源约束的处理，将其显式标记为 `RESOURCE` 角色。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsNode, PhysicsDataNode
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.topology import Channel
from cascade.compiler.utils.naming import PhysicalIdGenerator
~~~~~
~~~~~python.new
from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsNode, PhysicsDataNode
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.topology import Channel
from cascade.spec.ports import PortDef, PortRole
from cascade.compiler.utils.naming import PhysicalIdGenerator
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # F_pre: The Bleacher
        # Inputs = Task Args + Resource Constraints
        bleacher_inputs = {arg.name: "Any" for arg in node_ir.task.args}
        # Add ports for resources
        for res_name in node_ir.constraints.keys():
            bleacher_inputs[f"res_{res_name}"] = "ResourceSlot"

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
~~~~~python.new
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
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # F_worker: The actual execution logic
        # It conceptually takes *args/**kwargs, but physically takes one 'worker_input' dict
        f_worker = WorkerNode(
            id=f_worker_id,
            name=f"Exec({node_ir.name})",
            input_ports={"worker_input": "Dict"},
            output_ports={"worker_result": "Any"},
        )
~~~~~
~~~~~python.new
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
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # F_post: The Stainer
        # Outputs = Result + Resource Returns
        stainer_outputs = {
            "output": "Token",
            "obs_output": "Event",
        }
        for res_name in node_ir.constraints.keys():
            stainer_outputs[f"res_{res_name}"] = "ResourceSlot"

        f_post = StainNode(
            id=f_post_id,
            name=f"Stain({node_ir.name})",
            input_ports={"worker_result": "Any", "trace_input": "TraceCtx"},
            output_ports=stainer_outputs,
        )
~~~~~
~~~~~python.new
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

最后，更新那些验证 `Expander` 和 `Builder` 输出的单元测试，确保它们检查的是 `PortDef` 对象而不是字符串。

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
