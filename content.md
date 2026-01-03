简要回答

好的，我们进入第三阶段。我们将实施“主权端口”原则，首先将所有节点的默认输出端口从含糊的 `output` 迁移到明确的 `output_default`，并引入 `output_error` 端口，从而确立多路输出的物理基础。

## [WIP] refactor(compiler): 实施通用布线算法第三阶段 - 主权端口与复杂路由

### 用户需求
1.  重构 `Stainer` 和 `Expander` 以支持主权端口（Sovereign Ports）模型。
2.  废弃单一的 `output` 端口，替换为语义明确的 `output_default` 和 `output_error`。
3.  更新所有布线策略以适配新的端口命名。
4.  添加测试用例验证多端口路由的基础设施。

### 评论
这是迈向“逻辑即拓扑”的关键一步。通过区分 `default` 和 `error` 输出，我们消除了对 `Token.tag` 进行光谱过滤的需求。虽然目前的逻辑图（NodeIR）尚未完全利用多分支能力，但物理层必须先行一步，提供支持多路流形（Manifold）的基础设施。

### 目标
1.  修改 `cascade-std` 中的 `standard_stainer`，使其默认向 `output_default` 发射数据。
2.  修改 `cascade-compiler` 中的 `Expander`，为每个节点生成 `output_default` 和 `output_error` 端口。
3.  修改 `ParameterWiringPolicy` 和 `ControlFlowWiringPolicy`，使其连接上游的 `output_default` 端口。
4.  添加单元测试验证 Expander 的端口生成，以及集成测试验证端到端的流转。

### 基本原理
*   **主权原则**: 节点（Stainer）决定数据去向，而不是通道。
*   **显式优于隐式**: `output_default` 明确表示这是成功路径的输出。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #comp/std #scope/core #task/domain/compiler #task/object/sovereign-ports #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新标准 Stainer 实现

首先，我们修改 `standard_stainer`，使其符合主权端口规范。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
    # 3. Create output tokens
    outputs = {}

    # 3.1 The main result
    # In the future (Phase 2), we will route to 'output_error' if exception.
    # For now, we emit to 'output' regardless, but without a tag.
    outputs["output"] = Token(payload=result_payload, trace=trace_payload)

    # 4.2 Observability Event
~~~~~
~~~~~python.new
    # 3. Create output tokens
    outputs = {}

    # 3.1 The main result
    # Sovereign Routing: We explicitly choose the 'output_default' port for success.
    # In the future, if result_payload is an Exception or Jump, we would route to
    # 'output_error' or other dynamic ports.
    outputs["output_default"] = Token(payload=result_payload, trace=trace_payload)

    # 4.2 Observability Event
~~~~~

#### Acts 2: 更新 Expander 生成逻辑

接着，更新编译器后端，使其生成新的端口定义。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # F_post: The Stainer
        # Outputs = Result + Resource Returns
        stainer_outputs = {
            "output": PortDef("output", PortRole.DATA, "Token"),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event"),
        }
        for res_name in node_ir.constraints.keys():
~~~~~
~~~~~python.new
        # F_post: The Stainer
        # Outputs = Result + Resource Returns
        # Sovereign Ports: Explicitly define default and error paths
        stainer_outputs = {
            "output_default": PortDef("output_default", PortRole.DATA, "Token"),
            "output_error": PortDef("output_error", PortRole.DATA, "Token"),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event"),
        }
        for res_name in node_ir.constraints.keys():
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # D_worker_out -> F_post
        channels.append(
            Channel(
                source_node_id=d_worker_out_id,
                source_port="out",
                target_node_id=f_post_id,
                target_port="worker_result",
            )
        )
~~~~~
~~~~~python.new
        # D_worker_out -> F_post
        channels.append(
            Channel(
                source_node_id=d_worker_out_id,
                source_port="out",
                target_node_id=f_post_id,
                target_port="worker_result",
            )
        )
~~~~~

#### Acts 3: 更新布线策略

现在必须更新所有引用了旧 `output` 端口的布线策略。

**3.1 ParameterWiringPolicy**

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/wiring/policies/parameter.py
~~~~~
~~~~~python.old
                d_dep = PhysicsDataNode(id=d_dep_id, name=f"Dep({arg_name})")
                ctx.wire.add_node(d_dep)

                # Source Stainer -> D_dep
                ctx.wire.connect(source_subgraph.stainer.id, "output", d_dep_id, "in")

                # D_dep -> Target Bleacher
                ctx.wire.connect(d_dep_id, "out", subgraph.bleacher.id, arg_name)
~~~~~
~~~~~python.new
                d_dep = PhysicsDataNode(id=d_dep_id, name=f"Dep({arg_name})")
                ctx.wire.add_node(d_dep)

                # Source Stainer -> D_dep (Connect from output_default)
                ctx.wire.connect(source_subgraph.stainer.id, "output_default", d_dep_id, "in")

                # D_dep -> Target Bleacher
                ctx.wire.connect(d_dep_id, "out", subgraph.bleacher.id, arg_name)
~~~~~

**3.2 ControlFlowWiringPolicy**

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/wiring/policies/control.py
~~~~~
~~~~~python.old
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
~~~~~python.new
                d_seq = PhysicsDataNode(id=d_seq_id, name=f"Seq({dep_id})")
                ctx.wire.add_node(d_seq)

                ctx.wire.connect(source_subgraph.stainer.id, "output_default", d_seq_id, "in")
                ctx.wire.connect(d_seq_id, "out", subgraph.bleacher.id, port_name)

        # 4.3 Condition (.run_if())
        if node_ir.condition and node_ir.condition in ctx.subgraphs:
            source_subgraph = ctx.get_subgraph(node_ir.condition)
            assert source_subgraph.stainer is not None

            # Violation Fix: Insert D_cond
            d_cond_id = f"cond.{node_ir.condition}.to.{node_ir.id}"
            d_cond = PhysicsDataNode(id=d_cond_id, name=f"Cond({node_ir.condition})")
            ctx.wire.add_node(d_cond)

            ctx.wire.connect(source_subgraph.stainer.id, "output_default", d_cond_id, "in")
            ctx.wire.connect(d_cond_id, "out", subgraph.bleacher.id, "condition")
~~~~~

#### Acts 4: 添加验证测试

我们添加两个测试：
1.  **单元测试**: 验证 Expander 是否生成了正确的端口。
2.  **集成测试**: 验证数据能否通过 `output_default` 正确流转。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/test_sovereignty.py
~~~~~
~~~~~python
from cascade.spec.ir.models import NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.ports import PortRole
from cascade.compiler.backend.expander import Expander


def test_expander_generates_sovereign_ports():
    # 1. Setup IR
    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(name="my_task", args=[], fingerprint=fp)
    node_ir = NodeIR(id="node_sov", name="SovereignNode", task=task_def)

    # 2. Expand
    expander = Expander()
    subgraph = expander.expand_node(node_ir)
    stainer = subgraph.stainer

    # 3. Assert Ports
    assert "output_default" in stainer.output_ports
    assert "output_error" in stainer.output_ports
    
    # Check roles
    assert stainer.output_ports["output_default"].role == PortRole.DATA
    assert stainer.output_ports["output_error"].role == PortRole.DATA

    # Ensure legacy 'output' is gone
    assert "output" not in stainer.output_ports
~~~~~

~~~~~act
write_file
packages/cascade-compiler/tests/integration/test_sovereign_wiring.py
~~~~~
~~~~~python
import pytest
from cascade.spec.task import task
from cascade.compiler.frontend.generator import IRGenerator
from cascade.compiler.backend.builder import Builder
from cascade.spec.environment import EnvironmentDef
from cascade.compiler.utils.inspector import GraphInspector


@task
def producer():
    return "Hello"


@task
def consumer(msg):
    return f"Received: {msg}"


def test_sovereign_wiring_flow():
    """
    Verifies that the new 'output_default' based wiring actually works
    and connects the producer's Stainer to the consumer's Bleacher.
    """
    # 1. Generate Logical Graph
    t1 = producer()
    t2 = consumer(t1)
    
    ir_generator = IRGenerator()
    graph_ir = ir_generator.generate(t2)

    # 2. Build Physical Graph
    builder = Builder()
    physical_graph = builder.build(graph_ir, EnvironmentDef())

    # 3. Inspect Topology
    inspector = GraphInspector(physical_graph)
    
    # Get nodes
    nodes = {n.name: n for n in graph_ir.nodes}
    t1_id = nodes["producer"].id
    t2_id = nodes["consumer"].id

    t1_stainer_id = f"{t1_id}.stain"
    
    # Check that t1.stain has the sovereign port
    inspector.assert_port_exists(t1_stainer_id, "output_default")

    # Find channels from t1.stain
    channels = inspector.find_channels_from(t1_stainer_id, "output_default")
    assert len(channels) == 1
    
    # It should go to a dependency buffer (D_dep)
    d_dep_id = channels[0].target_node_id
    assert "dep." in d_dep_id
    
    # That buffer should go to t2.bleach
    t2_bleacher_id = f"{t2_id}.bleach"
    inspector.assert_connection(d_dep_id, t2_bleacher_id, target_port="msg")
~~~~~

### 下一步建议
第三阶段完成。我们已经成功建立了主权端口的基础设施。
目前的实现只涵盖了 `output_default`。对于 `output_error`，目前它作为一个预留端口存在，但在 `standard_stainer` 中尚未激活异常路由逻辑。

接下来的建议方向：
1.  **完善异常处理**: 修改 `standard_stainer`，使其捕获 `worker_result` 中的异常对象，并将其路由到 `output_error`。
2.  **通用性验证**: 执行第四阶段的通用性验证，尝试引入一个连续资源（如 `Memory`），验证我们的 Prism 架构是否真能处理非标准的资源拓扑。
