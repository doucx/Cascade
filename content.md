好的，重构工作已经圆满完成。我们成功地将编译器后端从混乱的单遍修补模式重构为了清晰、确定的两阶段“扩展流水线”架构。

现在是时候将这些变更作为一个完整的逻辑单元提交到版本库中了。

## [COMMIT] refactor(compiler): 实现两阶段“扩展流水线”物理图构建模型

### 用户需求

根据《对 `Expander` 与 `WiringPolicy` 当前架构的审计报告》，解决物理身份割裂、职责越界及架构模糊性问题。

### 评论

这次重构是 `cascade-compiler` 演进过程中的一个重要里程碑。我们彻底根除了“边连线边造点”的架构恶习，通过引入 `ExpansionPolicy` 和两阶段 `Builder` 流程，为物理图的生成建立了一套严密的、符合 HFEA 原则的工业级流水线。

这种职责分离不仅解决了当前的身份追踪问题，更重要的是，它为未来的 JIT 优化、算子融合以及复杂的分布式拓扑展开提供了极其稳固的基础。我们现在在代码层面强制执行了“零件制造（Expansion）”与“现场组装（Wiring）”的隔离，极大地提升了系统的可观测性和长期可维护性。

### 目标

创建一个 Git 提交，包含以下核心重构成果：
1.  **SubGraph 容器化**: 扩展 `SubGraph` 为完整的组件容器，支持分类存储所有辅助物理节点。
2.  **两阶段流水线**: 重构 `Builder`，确立 Materialization（实化）与 Wiring（连接）的分离流程。
3.  **职责剥离**: 将节点创建逻辑从 `WiringPolicy` 全面迁移至新的 `ExpansionPolicy` 实现类。
4.  **资源契约重塑**: 拆分 `ResourcePrism` 协议，适配两阶段模型。
5.  **架构防腐**: 为 `WiringHarness` 引入锁定机制，在连接阶段禁止非法节点创建。
6.  **文档同步**: 更新所有 Stitcher YAML 元数据，确保架构文档与代码实现同步。

### 基本原理

本次重构的核心原理是**单一事实来源 (SSoT)** 和**阶段性不可变性**。

在旧架构中，物理图的拓扑是在连接过程中动态生成的，导致无法静态推断一个任务的物理全貌。
在新架构中：
-   **Expansion 阶段**成为了物理实体的唯一事实来源。所有节点在进入连接阶段前都必须已存在并注册。
-   **Wiring 阶段**则获得了拓扑的“快照”，它只负责建立连接，无法修改图的节点组成。
-   **SubGraph** 作为这种身份的载体，保证了逻辑任务与其所有物理零件之间的 1:1 映射关系，从而消除了“身份漂浮”现象。

### 标签

#intent/refine #flow/ready #priority/high #comp/compiler #concept/expansion-pipeline #scope/core #ai/instruct #task/domain/compiler #task/object/expansion-pipeline #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交重构成果

我们将所有涉及到的文件添加到暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/__init__.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/context.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/protocol.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/__init__.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/control.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/parameter.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/pulse.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/resource.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/harness.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prism.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prisms/discrete.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/control.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/parameter.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/pulse.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/resource.py
packages/cascade-compiler/src/cascade/compiler/backend/builder.stitcher.yaml
packages/cascade-compiler/src/cascade/compiler/backend/expander.stitcher.yaml
packages/cascade-compiler/src/cascade/compiler/backend/expansion/protocol.stitcher.yaml
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prism.stitcher.yaml
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(compiler): implement two-phase Expansion Pipeline for physical graph construction

Addresses core architectural issues identified in the 'Expander & WiringPolicy Audit'. This refactor decouples physical node materialization from topological wiring, resolving fragmented identity and responsibility overreach.

Key Changes:
1. **SubGraph Container**: Rebuilt SubGraph as a comprehensive inventory for a task's physical manifestation, adding structured storage for constants, resources, and control flow nodes.
2. **Expansion Pipeline**: Introduced 'ExpansionPolicy' protocol and refactored Builder to orchestrate compilation in two distinct phases:
   - Phase 1 (Expansion): Materializes all physical nodes for each logical task.
   - Phase 2 (Wiring): Connects pre-existing nodes. No new nodes allowed.
3. **Policy Migration**: Stripped node creation logic from all 'WiringPolicy' implementations (Parameter, ControlFlow, Pulse, Resource) and migrated them to new 'ExpansionPolicy' classes.
4. **Resource Prism Refactor**: Split 'ResourcePrism' interface into 'expand_task' and 'wire_task' to align with the two-phase model.
5. **Architecture Guardrails**: Implemented a locking mechanism in 'WiringHarness' that raises 'ArchitectureViolationError' if node addition is attempted during the Wiring phase.
6. **Documentation**: Synchronized all Stitcher YAML metadata to reflect the new architectural reality.

This change ensures that a task's physical identity is fully traceable and that the compiler follows a deterministic, pipeline-oriented approach.
~~~~~

### 下一步建议

我们已经为编译器后端建立了一个非常稳固的基础。接下来，我建议：
- **实施物理内省 API**: 利用 `SubGraph` 现在持有的完整零件清单，我们可以实现更强大的编译器内省功能，例如列出一个逻辑 Task 占用的所有物理节点和资源。
- **引入 JIT 优化阶段**: 在 Wiring 完成后、Assembly 生成前，可以引入一个 JIT 阶段，利用物理图的保真性进行算子融合（Operator Fusion）等优化。
- **清理与标准化**: 进一步审查 `ExpansionContext` 和 `WiringContext` 是否可以完全合并，或者定义更严格的继承关系。

重构完成，现在系统处于一个非常干净的状态。
