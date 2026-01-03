好的，收到指令。

你发现的问题非常敏锐，这正是我们期望在 TDD 流程中看到的。测试 `test_builder_expands_and_wires_nodes` 的失败并非回归，而是**我们成功的标志**——它证明了我们上一轮的“脉冲引入”重构确实改变了 `Builder` 的行为，为源节点 `node_a` 增加了一个额外的 `Pulse` 节点。

现在，我们将遵循 TDD 的下一步：进入 “GREEN” 状态。我将生成一个计划，该计划不仅会修复这个因我们的改进而过时的测试，还会添加一个全新的、专门的测试用例来明确验证“分布式脉冲模型”是否按预期工作。

## [WIP] test: 验证脉冲模型并修复过时测试

### 用户需求
1.  修复 `packages/cascade-compiler/tests/unit/backend/test_builder.py` 中因“脉冲模型”重构而导致的断言失败。
2.  为“分布式脉冲模型”编写一个新的单元测试，确保编译器能为源节点正确生成和连接脉冲节点。

### 评论
这是一个标准的、健康的 TDD 流程。在重构（Refactor）之后，更新测试套件以反映新的、正确的行为是至关重要的一步。修复过时的测试可以确保我们的安全网依然有效，而为新功能（脉冲模型）添加专门的测试则可以明确地将新架构的行为契约固定下来，防止未来的回归。

### 目标
1.  **修复**：在 `test_builder.py` 中，将 `test_builder_expands_and_wires_nodes` 的节点数断言从 `15` 更新为 `16`，通道数断言从 `19` 更新为 `20`，并更新注释以解释新增的 `Pulse` 节点。
2.  **新增**：在 `test_builder.py` 中，添加一个新的测试用例 `test_builder_creates_pulse_for_source_node`。
3.  **验证**：新测试将断言对于一个真正的源节点（无任何输入），`Builder` 会：
    *   创建一个 ID 正确的 `Pulse` 数据节点。
    *   为该 `Pulse` 节点设置 `initial_tokens=1`。
    *   将该 `Pulse` 节点正确连接到源任务 `BleachNode` 的 `__pulse__` 端口。

### 基本原理
旧测试的失败是因为 `sample_graph_ir` 中的 `node_a` 是一个真正的源节点，我们的重构为其自动添加了一个 `Pulse` 节点，导致总节点数从 15 增加到 16，总通道数从 19 增加到 20。修复断言即可。

新测试则直接聚焦于脉冲模型的正确性。通过构造一个最纯粹的源节点场景，我们可以精确验证 `Builder` 是否遵循了我们在上一步中实现的脉冲生成和布线逻辑，从而为这一核心架构特性提供坚实的测试保障。

### 标签
#intent/tooling #flow/ready #priority/high #comp/compiler #comp/tests #task/domain/testing #task/object/pulse-model #task/action/verification #task/state/continue

---

### Script

#### Acts 1: 更新测试文件以验证脉冲模型

我们将使用 `write_file` 一次性完成对 `test_builder.py` 的修复和增强。

~~~~~act
write_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python
import pytest
from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.compiler.backend.builder import Builder
from cascade.spec.environment import EnvironmentDef
from cascade.compiler.utils.naming import PhysicalIdGenerator
from cascade.spec.physics import PhysicsDataNode
from cascade.spec.ports import PortName


@pytest.fixture
def sample_graph_ir():
    fp = Fingerprint.from_dict({"canonical_code_structure_hash": "abc"})
    task_a_def = TaskDef(name="task_a", args=[], fingerprint=fp)
    task_b_def = TaskDef(
        name="task_b",
        args=[ArgumentDef("data", ArgumentKind.POSITIONAL_OR_KEYWORD)],
        fingerprint=fp,
    )

    node_a = NodeIR(id="node_a", name="NodeA", task=task_a_def)
    node_b = NodeIR(
        id="node_b",
        name="NodeB",
        task=task_b_def,
        inputs={"data": "node_a"},  # task_b.data comes from node_a
    )

    return GraphIR(nodes=[node_a, node_b])


@pytest.fixture
def source_only_graph_ir():
    fp = Fingerprint.from_dict({"canonical_code_structure_hash": "xyz"})
    task_def = TaskDef(name="source_task", args=[], fingerprint=fp)
    node = NodeIR(id="source_node", name="Source", task=task_def)
    return GraphIR(nodes=[node])


def test_builder_expands_and_wires_nodes(sample_graph_ir):
    builder = Builder()
    graph = builder.build(sample_graph_ir, environment=EnvironmentDef())

    # Assert nodes: 2 triads (6*2=12) + 1 D_life + 1 F_obs + 1 D_dep + 1 D_pulse = 16 nodes
    assert len(graph.nodes) == 16
    assert "global.observability.bus" in graph.nodes
    assert "global.observability.observer" in graph.nodes
    assert "node_a.stain" in graph.nodes
    assert "node_b.bleach" in graph.nodes
    assert "dep.node_a.to.node_b.data" in graph.nodes
    assert "pulse.source.node_a" in graph.nodes  # The new pulse node

    # Assert channels
    # 2 triads (6 internal * 2) = 12
    # 1 data dependency = 2 (F->D, D->F)
    # 2 triads * 2 obs channels to D_life = 4
    # 1 D_life -> F_obs channel = 1
    # 1 D_pulse -> F_bleach channel = 1
    # Total = 12 + 2 + 4 + 1 + 1 = 20
    assert len(graph.channels) == 20

    # 1. Test data dependency wiring (F -> D -> F)
    stain_to_dep = next(
        c
        for c in graph.channels
        if c.source_node_id == "node_a.stain"
        and c.target_node_id == "dep.node_a.to.node_b.data"
    )
    assert stain_to_dep is not None

    dep_to_bleach = next(
        c
        for c in graph.channels
        if c.source_node_id == "dep.node_a.to.node_b.data"
        and c.target_node_id == "node_b.bleach"
    )
    assert dep_to_bleach is not None
    assert dep_to_bleach.target_port == "data"

    # 2. Test observability wiring
    d_life_id = "global.observability.bus"
    obs_channels = [c for c in graph.channels if c.target_node_id == d_life_id]

    assert len(obs_channels) == 4  # 2 starts, 2 ends

    source_ids = {c.source_node_id for c in obs_channels}
    assert "node_a.bleach" in source_ids
    assert "node_a.stain" in source_ids
    assert "node_b.bleach" in source_ids
    assert "node_b.stain" in source_ids


def test_builder_creates_pulse_for_source_node(source_only_graph_ir):
    builder = Builder()
    graph = builder.build(source_only_graph_ir, environment=EnvironmentDef())

    # 1. Assert Pulse node creation
    pulse_id = PhysicalIdGenerator.pulse_source("source_node")
    assert pulse_id in graph.nodes

    pulse_node = graph.nodes[pulse_id]
    assert isinstance(pulse_node, PhysicsDataNode)
    assert pulse_node.initial_tokens == 1

    # 2. Assert Bleacher port definition
    bleacher_id = "source_node.bleach"
    bleacher_node = graph.nodes[bleacher_id]
    assert PortName.PULSE in bleacher_node.input_ports

    # 3. Assert Connection: D_pulse -> F_bleach
    pulse_channel = next(
        c
        for c in graph.channels
        if c.source_node_id == pulse_id and c.target_node_id == bleacher_id
    )
    assert pulse_channel is not None
    assert pulse_channel.target_port == PortName.PULSE
~~~~~

### 下一步建议
我们已经完成了对编译器核心逻辑的重构，并为这些变更添加了单元测试保障。现在，整个物理图的生成机制（包括资源、探测器和脉冲）已经达到了一个稳定且符合架构原则的状态。

下一步，我建议我们进行一次端到端的集成测试，使用 `EventDrivenRunner` 来实际运行一个由新版 `Builder` 编译出的、包含源任务的物理图，并断言该任务确实被成功执行。这将验证从编译到执行的整个链路是通畅的。
