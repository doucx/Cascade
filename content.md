我们已经处于 **RED** 状态，现在是时候实现代码，让测试套件回到 **GREEN** 状态。

此计划将重构 `Builder` 以接受 `EnvironmentDef`，从而将资源管理的责任从编译器转移到环境定义中，这更符合物理场的客观性原则。

## [WIP] feat(compiler): 重构 Builder 以消费 `EnvironmentDef`

### 用户需求

修改 `Builder` 的实现，使其：
1.  接受一个新的 `environment: EnvironmentDef` 参数。
2.  根据 `EnvironmentDef` 中定义的资源来创建物理 `D_res` 节点。
3.  在编译时验证任务请求的资源是否存在于环境中，如果不存在则抛出 `ValueError`。
4.  修复因 `Builder.build` 方法签名变更而损坏的现有测试。

### 评论

这是对 `Builder` 的一次关键重构，它将系统的架构向“全对称计算物理场”白皮书的哲学拉近了一大步。通过强制 `Builder` 尊重一个客观的、外部定义的环境，我们从根本上解决了之前“需求创造供给”的逻辑谬误。这使得我们的物理模型更加真实、健壮，并为未来实现更复杂的资源调度策略（如多环境部署）铺平了道路。

### 目标

1.  重构 `cascade.compiler.backend.builder.Builder`，实现新的资源创建和验证逻辑。
2.  更新 `tests.unit.backend.test_builder` 测试用例，使其适应新的 `build` 方法签名。
3.  使 `tests.unit.backend.test_builder_environment` 中的所有测试通过。

### 基本原理

我们将采用 `write_file` 彻底重写 `builder.py`，因为其核心逻辑（特别是资源处理部分）发生了根本性变化。
1.  **环境优先**: 新的 `Builder` 首先会根据 `EnvironmentDef` 创建所有客观存在的资源节点。
2.  **验证先行**: 在展开任何 `NodeIR` 之前，会检查其 `constraints` 是否能在已定义的环境资源中得到满足。这实现了“快速失败”原则。
3.  **解耦**: 资源的定义（`EnvironmentDef`）与资源的使用（`NodeIR.constraints`）被清晰地分离开来。`Builder` 成为连接这两者的桥梁，而不是其中任何一方的创造者。
4.  **测试修复**: 对旧测试的修复是微创的，只需提供一个空的 `EnvironmentDef` 即可满足新的方法签名，因为原测试不涉及资源约束。

### 标签

#intent/refine #flow/ready #priority/high #comp/compiler #concept/resources #scope/core #ai/instruct #task/domain/refactoring #task/object/environment #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 重构 `Builder` 以处理 `EnvironmentDef`

我们将用新的实现覆盖 `builder.py`，该实现遵循环境优先的原则。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python
from typing import Dict

from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode
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

        # 2. Create the global observability sidecar node (D_life)
        d_life = PhysicsDataNode(id="global_d_life", name="LifecycleBus")
        physical_graph.nodes[d_life.id] = d_life

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
                # This should not happen with the current expander implementation
                raise RuntimeError(f"Subgraph for {node_ir.id} is incomplete.")

            subgraphs[node_ir.id] = subgraph
            physical_graph.nodes.update(subgraph.nodes)
            physical_graph.channels.extend(subgraph.channels)

            # 3.3 Wire observability sidecars
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.bleacher.id,
                    source_port="obs_output",
                    target_node_id=d_life.id,
                    target_port="event_token",
                )
            )
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.stainer.id,
                    source_port="obs_output",
                    target_node_id=d_life.id,
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

#### Acts 2: 修复旧的 `test_builder.py` 测试

现在，我们将修复因 `build` 方法签名改变而失败的旧测试用例。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python.old
from cascade.compiler.backend.builder import Builder


@pytest.fixture
def sample_graph_ir():
    fp = Fingerprint.from_dict({"canonical_code_structure_hash": "abc"})
~~~~~
~~~~~python.new
from cascade.compiler.backend.builder import Builder
from cascade.spec.environment import EnvironmentDef


@pytest.fixture
def sample_graph_ir():
    fp = Fingerprint.from_dict({"canonical_code_structure_hash": "abc"})
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python.old
def test_builder_expands_and_wires_nodes(sample_graph_ir):
    builder = Builder()
    graph = builder.build(sample_graph_ir)

    # Assert nodes: 2 triads (6 nodes each) + 1 global D_life = 13 nodes
    assert len(graph.nodes) == 13
~~~~~
~~~~~python.new
def test_builder_expands_and_wires_nodes(sample_graph_ir):
    builder = Builder()
    graph = builder.build(sample_graph_ir, environment=EnvironmentDef())

    # Assert nodes: 2 triads (6 nodes each) + 1 global D_life = 13 nodes
    assert len(graph.nodes) == 13
~~~~~

### 下一步建议

我们已经成功地将 `EnvironmentDef` 集成到了 `Builder` 中，测试套件现在应该是 **GREEN** 状态。

这完成了 **Phase 4.5 Step 2** 的核心工作。下一步，我们应该继续偿还技术债务，执行 **Phase 4.5 Step 3: 补全观测环路 (Complete the Loop)**。这将确保我们的物理场不仅行为正确，而且是完全可观测的。

如果你同意，我将开始制定该计划。
