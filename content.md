我们正处于 **RED** 状态，现在是时候实现代码，让测试套件回到 **GREEN** 状态。

此计划将补全“全息可观测性”的物理环路，确保系统状态能被外部世界感知。这也标志着 **Phase 4.5** 技术债务偿还工作的圆满完成。

## [WIP] feat(compiler): 实现完整的观测环路 (F_obs)

### 用户需求

修改 `Builder` 的实现，使其：
1.  自动创建一个全局的 `ObservabilityNode` (`F_obs`) 实例。
2.  自动创建一条从 `D_life` 到 `F_obs` 的 `Channel`，将生命周期事件从数据总线引导至观测处理器。
3.  修复因节点和通道数量增加而损坏的现有测试。

### 评论

这是实现白皮书中“全息可观测性”承诺的关键一步。通过将 `F_obs` 节点及其连接作为物理图的一部分进行实例化，我们确保了系统的可观测性不再是一个可选的或侵入式的特性，而是根植于其物理结构中的固有属性。任何通过此 `Builder` 编译的工作流，都将自动具备生命周期遥测能力，这是一种架构层面的保证。

### 目标

1.  重构 `cascade.compiler.backend.builder.Builder`，实现 `F_obs` 的创建和连接逻辑。
2.  更新 `tests.unit.backend.test_builder` 测试用例，使其断言正确的节点和通道数量。
3.  使 `tests.unit.backend.test_builder_observability` 中的所有测试通过。

### 基本原理

1.  **全局单例**: `F_obs` 和 `D_life` 是物理场中的全局单例。`Builder` 在构建任何用户节点之前，会首先实例化这两个基础设施节点并连接它们，构成观测系统的骨架。
2.  **职责明确**: `D_life` 负责汇聚事件，`F_obs` 负责处理和发射事件。`Builder` 负责将它们连接起来。
3.  **测试适应**: 随着基础设施的完善，图中节点的总数和通道的总数会发生确定性的变化。我们必须更新 `test_builder.py` 中的断言以反映这个新的、更完整的拓扑结构，确保测试与实现保持同步。

### 标签

#intent/refine #flow/ready #priority/high #comp/compiler #concept/observability #scope/core #ai/instruct #task/domain/refactoring #task/object/observability #task/action/implement #task/state/end

---

### Script

#### Acts 1: 在 `Builder` 中创建并连接 `F_obs` 节点

我们将重写 `builder.py`，在其初始化阶段就建立起完整的 `D_life -> F_obs` 观测骨架。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python
from typing import Dict

from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode
from cascade.spec.triad import ObservabilityNode
from cascade.spec.environment import EnvironmentDef
from .expander import Expander, SubGraph


class Builder:
    def __init__(self):
        self._expander = Expander()

    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> BipartiteGraph:
        physical_graph = BipartiteGraph()
        env_resources = {res.name: res for res in environment.resources}

        # 1. Create Objective Environment (D_res nodes)
        for res_def in environment.resources:
            res_node_id = f"global_res_{res_def.name}"
            d_res = PhysicsDataNode(
                id=res_node_id,
                name=f"Resource({res_def.name})",
                capacity=res_def.capacity,
                initial_tokens=res_def.capacity,
            )
            physical_graph.nodes[res_node_id] = d_res

        # 2. Create and wire the global observability sidecar infrastructure
        d_life_id = "global_d_life"
        f_obs_id = "global_f_obs"

        d_life = PhysicsDataNode(id=d_life_id, name="LifecycleBus")
        f_obs = ObservabilityNode(
            id=f_obs_id,
            name="LifecycleObserver",
            input_ports={"event_token": "Event"},
            output_ports={},  # Observer emits to the outside world, not back into the graph
        )
        physical_graph.nodes[d_life_id] = d_life
        physical_graph.nodes[f_obs_id] = f_obs

        physical_graph.channels.append(
            Channel(
                source_node_id=d_life_id,
                source_port="out",
                target_node_id=f_obs_id,
                target_port="event_token",
            )
        )

        # 3. Expand all logical nodes into physical subgraphs
        subgraphs: Dict[str, SubGraph] = {}
        for node_ir in graph_ir.nodes:
            # 3.1 Validate resource constraints against the environment
            for res_name in node_ir.constraints:
                if res_name not in env_resources:
                    raise ValueError(
                        f"Resource '{res_name}' required by node '{node_ir.id}' is not defined"
                    )

            # 3.2 Expand
            subgraph = self._expander.expand_node(node_ir)
            if subgraph.bleacher is None or subgraph.stainer is None:
                raise RuntimeError(f"Subgraph for {node_ir.id} is incomplete.")

            subgraphs[node_ir.id] = subgraph
            physical_graph.nodes.update(subgraph.nodes)
            physical_graph.channels.extend(subgraph.channels)

            # 3.3 Wire task observability TO the sidecar bus
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.bleacher.id,
                    source_port="obs_output",
                    target_node_id=d_life_id,
                    target_port="event_token",
                )
            )
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.stainer.id,
                    source_port="obs_output",
                    target_node_id=d_life_id,
                    target_port="event_token",
                )
            )

        # 4. Wire data dependencies between subgraphs
        for node_ir in graph_ir.nodes:
            target_subgraph = subgraphs[node_ir.id]
            for arg_name, source_ref in node_ir.inputs.items():
                if isinstance(source_ref, str) and source_ref in subgraphs:
                    source_subgraph = subgraphs[source_ref]
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=arg_name,
                        )
                    )

        # 5. Wire Global Resources (The Loop)
        for node_ir in graph_ir.nodes:
            subgraph = subgraphs[node_ir.id]
            for res_name in node_ir.constraints:
                res_node_id = f"global_res_{res_name}"
                port_name = f"res_{res_name}"

                # Acquire: D_res -> F_bleach
                physical_graph.channels.append(
                    Channel(
                        source_node_id=res_node_id,
                        source_port="out",
                        target_node_id=subgraph.bleacher.id,
                        target_port=port_name,
                    )
                )

                # Release: F_stain -> D_res
                physical_graph.channels.append(
                    Channel(
                        source_node_id=subgraph.stainer.id,
                        source_port=port_name,
                        target_node_id=res_node_id,
                        target_port="in",
                    )
                )

        return physical_graph
~~~~~

#### Acts 2: 修复 `test_builder.py` 中的断言

现在，我们将更新旧测试中的节点和通道计数，以反映新加入的 `F_obs` 节点和 `D_life -> F_obs` 通道。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python.old
    graph = builder.build(sample_graph_ir, environment=EnvironmentDef())

    # Assert nodes: 2 triads (6 nodes each) + 1 global D_life = 13 nodes
    assert len(graph.nodes) == 13
    assert "global_d_life" in graph.nodes
    assert "node_a_stain" in graph.nodes
    assert "node_b_bleach" in graph.nodes

    # Assert channels
    # 2 triads (6 channels each) = 12
    # 1 data dependency channel = 1
    # 2 triads * 2 obs channels each = 4
    # Total = 12 + 1 + 4 = 17
    assert len(graph.channels) == 17

    # 1. Test data dependency wiring
    data_channel = next(
~~~~~
~~~~~python.new
    graph = builder.build(sample_graph_ir, environment=EnvironmentDef())

    # Assert nodes: 2 triads (6 nodes each) + 1 D_life + 1 F_obs = 14 nodes
    assert len(graph.nodes) == 14
    assert "global_d_life" in graph.nodes
    assert "global_f_obs" in graph.nodes
    assert "node_a_stain" in graph.nodes
    assert "node_b_bleach" in graph.nodes

    # Assert channels
    # 2 triads (6 internal) = 12
    # 1 data dependency = 1
    # 2 triads * 2 obs channels to D_life = 4
    # 1 D_life -> F_obs channel = 1
    # Total = 12 + 1 + 4 + 1 = 18
    assert len(graph.channels) == 18

    # 1. Test data dependency wiring
    data_channel = next(
~~~~~

### 下一步建议

**Phase 4.5 已完成！**

我们已经成功地偿还了在 Phase 4 中积累的核心技术债务：
1.  ✅ 修复了所有静态类型错误。
2.  ✅ 形式化了 `EnvironmentDef`，使资源管理符合物理现实。
3.  ✅ 补全了“全息可观测性”的物理环路。

代码库现在处于一个更健康、更符合架构愿景的状态。

根据[重构路线图](obsidian://open?vault=obsidian&file=20_领域/Cascade/01_current/当前任务/Cascade%203.0%20重构路线图：迈向全对称计算物理场)，我们现在已经为 **Phase 5: 全系统集成 (System Integration)** 做好了准备。这一阶段的目标是将 `Frontend`, `Compiler`, 和 `VM` 组装成一个对外可用的、统一的 API。

我建议我们开始实施 **Phase 5.1: 重建 `VMExecutionStrategy`**。
