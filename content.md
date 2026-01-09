好的，我们进入路线图的**阶段三**，这是整个重构中最核心的部分。我们首先执行 `3.1 重构 ResourcePrism 协议`。

此计划将重塑资源管理的接口契约。我们将 `ResourcePrism` 这个原本“大包大揽”的接口，拆解为符合两阶段编译模型的 `expand_task`（造点）和 `wire_task`（连线），为后续的实现类迁移提供法律依据。

## [WIP] refactor(compiler): 重构 ResourcePrism 协议以支持两阶段编译

### 用户需求

根据架构路线图 3.1，需要修改 `packages/cascade-compiler/src/cascade/compiler/backend/wiring/prism.py` 文件。
目标是将 `ResourcePrism` 协议中的 `connect_task` 方法拆分为两个独立的方法：
1.  `expand_task`: 负责创建资源相关的物理节点（如 `F_req`, `D_amt`）。
2.  `wire_task`: 负责连接这些节点到全局资源基础设施。

### 评论

这是对资源管理子系统的“宪法修正案”。`ResourcePrism` 负责将高层的资源需求（如“需要 1 个 GPU”）“折射”为底层的物理拓扑。此前，这个折射过程是一次性完成的。现在，为了配合 `Builder` 的两阶段模型，我们必须强制要求所有的 `Prism` 实现都明确区分“制造零件”和“组装零件”这两个步骤。这不仅是为了适配新架构，更是为了让复杂的资源拓扑变得可调试、可观测。

### 目标

1.  修改 `packages/cascade-compiler/src/cascade/compiler/backend/wiring/prism.py`。
2.  引入 `ExpansionContext` 的导入。
3.  在 `ResourcePrism` 协议中删除 `connect_task` 方法。
4.  新增 `expand_task` 方法，接受 `ExpansionContext`。
5.  新增 `wire_task` 方法，接受 `WiringContext`。

### 基本原理

当前的 `ResourcePrism` 协议定义了一个单一的 `connect_task` 方法，这迫使实现者（如 `DiscreteResourcePrism`）在同一个方法里混合使用 `add_node`（造点）和 `connect`（连线）。

通过将其拆分为 `expand_task` 和 `wire_task`，我们在接口层面强制实施了单一职责原则：
-   **`expand_task`**：输入是“需求”，输出是“组件”。它告诉编译器：“为了满足这个资源需求，我们需要创建这些物理节点。”
-   **`wire_task`**：输入是“组件”，输出是“连接”。它告诉编译器：“现在这些节点都造好了，请把它们连入电网。”

注意：此更改会暂时破坏现有的 `DiscreteResourcePrism` 实现和 `ResourceWiringPolicy` 调用，这是预期的。接下来的 3.2 和 3.3 步骤将修复它们。

### 标签

#intent/refine #flow/ready #priority/high #task/domain/compiler #task/object/resource-prism #task/action/refactor #task/state/continue #scope/core #scope/api #ai/instruct

---

### Script

#### Acts 1: 更新 `ResourcePrism` 协议定义

我们将重写 `prism.py`，引入必要的上下文导入，并重新定义协议方法。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prism.py
~~~~~
~~~~~python
from typing import Protocol, Any
from cascade.spec.physical.environment import ResourceDef
from cascade.spec.ir.graph import NodeIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.expansion.context import ExpansionContext


class ResourcePrism(Protocol):
    def ensure_globals(self, ctx: WiringContext, res_def: ResourceDef) -> None:
        """
        Creates global infrastructure for this resource type (e.g., Allocator, Ledger).
        Called once per resource type during the global setup phase.
        """
        ...

    def expand_task(
        self,
        ctx: ExpansionContext,
        node_ir: NodeIR,
        subgraph: SubGraph,
        res_name: str,
        amount: Any,
    ) -> None:
        """
        Phase 1: Materialization.
        Creates the physical nodes required for a task to consume this resource
        (e.g., Requestor, Amount Constant).
        MUST NOT create any connections.
        """
        ...

    def wire_task(
        self,
        ctx: WiringContext,
        node_ir: NodeIR,
        subgraph: SubGraph,
        res_name: str,
        amount: Any,
    ) -> None:
        """
        Phase 2: Wiring.
        Connects the nodes created in Phase 1 to the task's triad and the
        global resource infrastructure.
        MUST NOT create any new nodes.
        """
        ...
~~~~~

### 下一步建议

我们已经更新了 `ResourcePrism` 协议，现在接口已经清晰地支持两阶段编译了。

路线图的下一步 (`3.2`) 是**升级 `DiscreteResourcePrism`**。我们需要修改这个具体的实现类，使其符合新的协议，将原本堆砌在 `connect_task` 中的逻辑拆分到 `expand_task` 和 `wire_task` 中。

如果你同意，我将开始制定升级 `DiscreteResourcePrism` 的计划。
