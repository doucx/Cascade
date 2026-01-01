这是 **Phase 4.5** 的第三步，也是最后一步。我们将再次遵循 TDD 流程。

## [WIP] feat(compiler): 补全观测环路 - TDD (RED)

### 用户需求

1.  **需求描述**: 在 `Builder` 构建的物理图中，为全局的 `D_life` 节点挂载一个标准的 `F_obs` (ObservabilityNode) 节点。
2.  **核心原因**: 目前的 `D_life` 节点是一个只进不出的黑洞。所有任务产生的生命周期事件（Start/End/Trace）都汇入其中，但没有出口将其发送到外部世界（Message Bus）。这不仅导致观测数据丢失，还会造成潜在的内存无限增长。
3.  **验证标准**: `test_builder.py` 必须能够断言物理图中存在一个 `F_obs` 节点，并且该节点正确连接到了 `D_life` 的输出端。

### 评论

这是“全息可观测性”拼图的最后一块。通过引入 `F_obs`，我们构建了一个完整的物理闭环：
`Task(F) -> Trace(D_trace) -> Stainer(F_stain) -> LifecycleBus(D_life) -> Observer(F_obs) -> External World`
这保证了物理场的运行状态能够被外部世界（UI、Logger、Metrics）实时感知，且不会对核心业务逻辑造成任何干扰。

### 目标

1.  在 `tests/unit/backend/test_builder_observability.py` 中创建新的测试用例，断言 `F_obs` 的存在及其连接关系。
2.  运行测试，确认其失败（RED）。

### 基本原理

我们创建一个全新的测试文件 `test_builder_observability.py`，专门用于验证观测系统的拓扑结构。这保持了测试的专注性和清晰度。

预期的拓扑结构：
*   存在一个 ID 为 `global_f_obs` 的 `ObservabilityNode`。
*   存在一条从 `global_d_life` 到 `global_f_obs` 的 Channel。
*   该 Channel 的目标端口应为 `event_token`（这是 `standard_observer` 预期的输入端口）。

### 标签

#intent/architect #flow/draft #priority/high #comp/compiler #comp/vm #concept/observability #scope/core #ai/instruct #task/domain/refactoring #task/object/observability #task/action/test #task/state/continue

---

### Script

#### Acts 1: 创建观测性拓扑测试 (RED)

编写测试用例，断言 `F_obs` 节点的存在及其正确连接。

~~~~~act
write_file
packages/cascade-compiler/tests/unit/backend/test_builder_observability.py
~~~~~
~~~~~python
import pytest
from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.environment import EnvironmentDef
from cascade.spec.triad import ObservabilityNode
from cascade.compiler.backend.builder import Builder


@pytest.fixture
def empty_graph_ir():
    # Even with no user tasks, the observability infrastructure should be present
    # (D_life and F_obs are global singletons)
    return GraphIR(nodes=[])


def test_builder_creates_observer_sidecar(empty_graph_ir):
    builder = Builder()
    graph = builder.build(empty_graph_ir, environment=EnvironmentDef())

    # 1. Assert D_life exists (Baseline check)
    assert "global_d_life" in graph.nodes

    # 2. Assert F_obs exists (New Requirement)
    f_obs_id = "global_f_obs"
    assert f_obs_id in graph.nodes
    f_obs = graph.nodes[f_obs_id]
    assert isinstance(f_obs, ObservabilityNode)

    # 3. Assert Connection: D_life -> F_obs
    obs_channels = [
        c for c in graph.channels 
        if c.source_node_id == "global_d_life" and c.target_node_id == f_obs_id
    ]
    assert len(obs_channels) == 1
    channel = obs_channels[0]
    
    # 4. Assert Port Mapping
    # D_life is a DataNode, source_port is typically "out"
    assert channel.source_port == "out"
    # F_obs expects input on "event_token" port (per standard_observer signature)
    assert channel.target_port == "event_token"
~~~~~

### 下一步建议

当前状态为 **RED**。
`test_builder_creates_observer_sidecar` 将会失败，因为当前的 `Builder` 只创建了 `D_life`，并没有创建 `F_obs` 及其连接。

下一步，我们将修改 `Builder` 的实现，补全这个缺口，使系统进入 **GREEN** 状态。这将标志着 **Phase 4.5** 的圆满完成。
