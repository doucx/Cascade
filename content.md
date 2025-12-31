好的，我们现在进入 **GREEN** 阶段。

我将创建 `packages/cascade-spec/src/cascade/spec/topology.py` 文件，并精确实现 `test_bipartite_graph_schema.py` 中定义的 `PhysicsFuncNode`, `PhysicsDataNode`, `ChannelDef`, 和 `BipartiteGraph` 数据类。这将使我们的测试套件从 RED 变为 GREEN。

## [WIP] feat: 实现 BipartiteGraph 物理拓扑契约

### 用户需求
根据 TDD 流程，实现 `packages/cascade-spec/tests/topology/test_bipartite_graph_schema.py` 中定义的物理拓扑数据结构，以使测试通过。

### 评论
这是架构演进的关键一步。通过创建这些严格命名的 `dataclass`，我们正在为编译器后端建立一个坚实且无歧义的“物理层”基础。这是将“势能驱动的数据流网络”白皮书中的概念转化为具体代码的第一个实际步骤。

### 目标
1.  创建 `packages/cascade-spec/src/cascade/spec/topology.py` 文件。
2.  在文件中定义 `PhysicsFuncNode`, `PhysicsDataNode`, `ChannelDef`, 和 `BipartiteGraph` 四个 `dataclass`。
3.  确保所有字段名称和类型与测试契约完全匹配，使测试套件通过。

### 基本原理
我们遵循 TDD (Test-Driven Development) 的核心循环。上一步我们编写了一个失败的测试（RED），现在我们编写最少的代码来让它通过（GREEN）。这些 `dataclass` 是纯粹的数据容器，完全符合测试中定义的 API 契约，没有额外的逻辑。

### 标签
#intent/build #flow/ready #priority/high #comp/interfaces #concept/state #scope/core #ai/instruct #task/domain/compiler #task/object/topology #task/action/definition #task/state/continue

---

### Script

#### Acts 1: 创建拓扑数据类实现

我们将在 `cascade.spec` 包中创建新的 `topology.py` 文件，并定义所有必需的数据结构。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class PhysicsFuncNode:
    """
    Represents a computational instance in the physical bipartite graph.
    This is the "Verb" or the transformer.
    """
    current_node_instance_hash: str
    name: str


@dataclass(frozen=True)
class PhysicsDataNode:
    """
    Represents a data storage slot in the physical bipartite graph.
    This is the "Noun" or the container. It tracks its origin.
    """
    current_data_slot_hash: str
    name: str
    producer_node_instance_hash: str


@dataclass(frozen=True)
class ChannelDef:
    """
    Defines a static, directed connection from a FuncNode's output port
    to a DataNode's input slot, with routing logic.
    """
    source_node_instance_hash: str
    target_data_slot_hash: str
    port_name: str
    tag_filter: str = "default"


@dataclass(frozen=True)
class BipartiteGraph:
    """
    The static, physical blueprint of the computation network, output by the compiler.
    """
    func_nodes: Dict[str, PhysicsFuncNode]
    data_nodes: Dict[str, PhysicsDataNode]
    channels: List[ChannelDef]
~~~~~

### 下一步建议
我们已经成功定义了物理层的契约。根据路线图，下一步是 **阶段 3.2：[TDD] 编译线性图到拓扑**。

我将创建一个新的测试文件 `packages/cascade-compiler/tests/unit/test_backend_topology.py`。这个测试会驱动我们重构 `Backend`，使其停止生成旧的 `Blueprint`，转而生成我们刚刚定义的 `BipartiteGraph`。这将是编译器重构的核心。
