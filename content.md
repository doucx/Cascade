好的，我们继续执行路线图，现在是 `1.2` 阶段。

此计划旨在创建 `ExpansionPolicy` 协议，为所有“节点创建”逻辑建立一个正式的、统一的接口。这是将节点创建（Materialization）与节点连接（Wiring）职责分离的核心步骤。

## [WIP] feat(compiler): 定义 ExpansionPolicy 协议以分离节点创建职责

### 用户需求

根据架构路线图 1.2，需要创建 `ExpansionPolicy` 协议。此协议将作为所有节点创建（物理实化）逻辑的统一接口，并为后续从 `WiringPolicy` 中迁移代码提供一个清晰的契约。

### 评论

这是奠定新架构基石的一步。通过定义一个严格的 `ExpansionPolicy` 协议，我们正在构建一个架构级的“护栏”，从根本上杜绝节点创建和节点连接的职责混淆。这确保了编译器后端的各个阶段都遵循单一职责原则，使得整个编译流程更加清晰、可预测和易于维护。

### 目标

1.  创建新的目录结构: `packages/cascade-compiler/src/cascade/compiler/backend/expansion/`。
2.  在该目录中创建 `__init__.py`，使其成为一个 Python 包。
3.  创建 `context.py` 文件，并定义一个临时的 `ExpansionContext`，为协议提供必要的类型提示。
4.  创建 `protocol.py` 文件，并在其中定义 `ExpansionPolicy` 协议，包含一个 `expand` 方法。

### 基本原理

为了实现“扩展流水线”模式，我们必须首先形式化地定义流水线中每个阶段的契约。`ExpansionPolicy` 协议就是“物理实化”阶段的契约。

所有实现此协议的策略，其唯一职责就是向 `SubGraph` 容器中添加物理节点（`add_node`），但**严禁**进行跨越 `SubGraph` 边界的连接（`connect`）。这强制性地将编译过程分解为两个独立的、确定性的阶段，为后续重构和功能扩展提供了坚实的基础。

### 标签

#intent/architect #flow/ready #priority/high #task/domain/compiler #task/object/expansion-policy #task/action/implementation #task/state/continue #scope/core #scope/api #ai/instruct

---

### Script

#### Acts 1: 创建 `expansion` 包目录结构

我们首先创建新的 `expansion` 目录和空的 `__init__.py` 文件。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-compiler/src/cascade/compiler/backend/expansion
touch packages/cascade-compiler/src/cascade/compiler/backend/expansion/__init__.py
~~~~~

#### Acts 2: 定义 `ExpansionContext`

为了让 `ExpansionPolicy` 协议的类型提示完整，我们先创建一个 `ExpansionContext`。目前，它的结构将与 `WiringContext` 类似，后续会根据需要进行调整。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/context.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Dict

from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.environment import EnvironmentDef
from cascade.spec.ir.graph import GraphIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring import WiringHarness


@dataclass
class ExpansionContext:
    graph_ir: GraphIR
    environment: EnvironmentDef
    physical_graph: BipartiteGraph
    wire: WiringHarness
    subgraphs: Dict[str, SubGraph] = field(default_factory=dict)
~~~~~

#### Acts 3: 定义 `ExpansionPolicy` 协议

现在，我们创建 `protocol.py` 并定义核心的 `ExpansionPolicy` 协议。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/protocol.py
~~~~~
~~~~~python
from typing import Protocol
from cascade.spec.ir.graph import NodeIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.expansion.context import ExpansionContext


class ExpansionPolicy(Protocol):
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        """
        Expands a logical node by creating and adding new physical nodes
        to its corresponding subgraph.

        This phase is strictly for MATERIALIZATION. Implementations of this
        protocol are FORBIDDEN from creating channels between different
        subgraphs.
        """
        ...
~~~~~

### 下一步建议

我们已经成功定义了 `ExpansionPolicy` 协议，为节点创建逻辑建立了清晰的契约。

路线图的下一步 (`1.3`) 是**改造 `Builder` 的执行流程**。我们需要修改 `Builder` 来消费这个新协议，并将其 `build` 方法重构为两个独立的阶段：
1.  **Materialization**: 运行所有 `ExpansionPolicy` 来创建节点。
2.  **Wiring**: 运行所有 `WiringPolicy` 来连接节点。

如果你同意，我将生成执行此 `Builder` 重构的计划。
