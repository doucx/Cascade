好的。`git status` 显示的变更完全符合 **“Cascade 架构提案：引入中间表示 (IR) 并解构 Node 对象”** 的实施范围。我们已经成功完成了所有阶段：

1.  **定义接口 (Phase 0)**：创建了 `cascade-spec` 中的 `ir` 模块和 `fingerprint` 模块。
2.  **默认实现 (Phase 1)**：创建了 `cascade-graph` 中的 `analysis` 模块和 `ReflectionAnalyzer`。
3.  **核心重构 (Phase 2)**：修改了 `Node`, `GraphBuilder`, `HashingService` 等核心组件。
4.  **验证清理 (Phase 3)**：更新了大量测试并通过，证明了重构的正确性。

现在是时候将这个里程碑式的重构作为一个原子提交并入了。

## [COMMIT] refactor(core): Introduce IR layer and decouple Node object

### 用户需求
根据“Cascade 架构提案”，通过引入一个纯粹的、面向数据的**中间表示 (IR) 层**和一个**分析器 (`Analyzer`) 协议**，将任务的“静态定义”与图节点的“运行时实例”彻底解耦。

### 评论
这是一个基础性的、影响深远的架构重构，它从根本上解决了“`Node` 上帝对象”问题。通过将节点的静态定义 (`TaskDef`) 与其实例状态分离，我们极大地提升了系统的模块化、可测试性，并为未来的序列化、分布式执行和可插拔静态分析引擎（如 `Stitcher`）奠定了坚不可摧的基石。

### 目标
创建一个单一的、原子化的 Git 提交，将这次 IR 重构的全部工作整合到代码库中。

### 基本原理
所有相关代码已经实现并通过了所有单元测试、集成测试和 E2E 测试，证明了这次重构在逻辑上是完整且正确的。将其作为一个原子提交，可以为项目历史建立一个清晰的、重要的架构演进节点。

### 标签
#intent/refine #flow/ready #priority/critical #comp/engine #comp/graph #comp/spec #concept/ir #scope/core #scope/api #ai/instruct #task/domain/architecture #task/object/ir-refactoring #task/action/completion #task/state/end

---

### Script

#### Acts 1: 提交 IR 重构

所有相关文件已经暂存，现在创建一个内容详尽的 Git 提交来记录这次重要的架构演进。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): Introduce IR layer and decouple Node object

This commit implements the "Intermediate Representation (IR)" proposal, fundamentally refactoring the core graph model to resolve the "Node God Object" problem.

Previously, the `Node` object was a complex mixture of a task's static definition (function signature, name), its topological role in the graph, and its runtime state (callable object, bound arguments). This tight coupling made the system difficult to maintain, test, and extend.

This refactoring introduces two key concepts:
1.  **IR Layer (`cascade.spec.ir`):** A new set of pure, serializable dataclasses (`TaskDef`, `ArgumentDef`) that represent the static, immutable definition of a task.
2.  **Analyzer Protocol (`cascade.graph.analysis`):** A protocol (`TaskAnalyzer`) and a default implementation (`ReflectionAnalyzer`) responsible for converting a Python callable into a static `TaskDef`.

Key changes:
-   **`Node` Simplification:** The `Node` object is no longer responsible for self-analysis. It now holds a single `definition: TaskDef` attribute, which is the single source of truth for its static properties.
-   **`GraphBuilder` Refactoring:** The `GraphBuilder` now uses an `Analyzer` instance to produce a `TaskDef` for each task, decoupling graph construction from runtime reflection details.
-   **Stable Hashing:** The `HashingService` now computes structural hashes based on the stable, explicit fields of `TaskDef` (via `Fingerprint`), leading to more robust and predictable node identity.

Benefits:
-   **Decoupling:** Clear separation of concerns between what a task is (`TaskDef`), where it is (`Node`), and how it's analyzed (`Analyzer`).
-   **Testability:** `ReflectionAnalyzer` and `TaskDef` are pure, easily testable components.
-   **Foundation for Future:** This lays the essential groundwork for serialization (making `TaskDef` distributable), pluggable static analysis engines (e.g., `StitcherAnalyzer`), and more advanced caching strategies.
~~~~~

### 下一步建议
这次重构是 Cascade 迈向 V2.0 架构的核心一步。我们现在已经解锁了许多可能性，下一步可以考虑：
1.  **实现 `StitcherAnalyzer`**: 创建 `cascade-provider-stitcher` 包，提供一个基于 `LibCST` 的静态分析器，并允许用户通过 `CascadeApp(analyzer=StitcherAnalyzer())` 无缝切换。
2.  **探索序列化**:  基于可序列化的 `TaskDef`，我们可以开始设计将整个计算图传输到远程工作节点或持久化到磁盘的机制。
