非常好！我们已经成功完成了架构重构的最后一步，并且通过了所有测试。现在，我们将把这个最终的、干净的状态作为一次原子提交，为整个重构工作画上圆满的句号。

## [COMMIT] refactor(arch): Decouple providers into a dedicated cascade-library package

### 用户需求
作为语义化重构的最后一步，创建一个独立的 `cascade-library` 包，并将所有内置的 Provider 实现从 `cascade-sdk` 中迁移过去。

### 评论
这次重构是 Cascade “小核心，大生态”设计哲学的完美体现。通过将具体的 Provider 实现（“标准库”）与核心 SDK 分离，我们极大地净化了 `cascade-sdk`，使其只专注于提供定义工作流的核心语言和扩展机制。这不仅使核心库更加稳定和轻量，也为未来 Provider 生态的独立发展和版本控制奠定了基础。

### 目标
创建一个单一、清晰的 Git 提交，以原子方式记录 `cascade-library` 的创建以及 Provider 代码的成功迁移，正式完成本次系列性的架构重构。

### 基本原理
测试套件的通过证明，在将 Provider 逻辑完全剥离到 `cascade-library` 后，系统的依赖注入和 `entry-points` 机制依然能够正确工作，整个项目处于功能完好、结构清晰的稳定状态。提交代码将永久性地记录下这一重大的架构改进。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #scope/core #ai/instruct #task/domain/architecture #task/object/package-structure #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 暂存所有与 `cascade-library` 相关的变更
我们将把新创建的 `cascade-library` 包、被修改的 `cascade-sdk` 包以及更新后的根 `pyproject.toml` 文件添加到暂存区。

~~~~~act
git_add
pyproject.toml
packages/
~~~~~

#### Acts 2: 创建原子提交
现在，我们将创建一个内容详尽的提交，以清晰地记录本次重构的目的和范围，并为整个重构宏任务画上句号。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(arch): Decouple providers into a dedicated cascade-library package

This commit completes the final phase of the semantic architecture refactoring by decoupling the built-in providers into a new, dedicated standard library package.

Previously, `cascade-sdk` (formerly `cascade-py`) was responsible for both the core user-facing DSL (`@task`, etc.) and the implementation of all standard providers (`http`, `sql`, `io`, etc.). This bloated the core SDK and tightly coupled the language with its implementations.

This change introduces `cascade-library` to solve this:

1.  **New `cascade-library` Package**: A new package is created to house all standard provider implementations.
2.  **Configuration Migration**: All provider-related `optional-dependencies` and `entry-points` have been moved from `cascade-sdk`'s `pyproject.toml` to `cascade-library`'s.
3.  **Code Migration**: All provider implementation files (`http.py`, `sql.py`, etc.) have been moved from `cascade-sdk` to `cascade-library`.
4.  **Clean `cascade-sdk`**: The `cascade-sdk` is now a pure, lightweight core. Its `providers` directory only contains the registration and discovery mechanism (`registry.py`), not the implementations.

This refactoring fully realizes the "small core, large ecosystem" philosophy, enhancing modularity and allowing the provider library to evolve independently of the core SDK.
~~~~~

### 下一步建议
我们已经成功地完成了《Cascade 架构重构建议书》中定义的所有核心任务！这是一个巨大的里程碑。

在开启新功能开发之前，我建议进行一次“冷却”和“巩固”：
1.  **全面审计与清理**：可以进行一次代码审查，专注于检查文档字符串、注释和内部文档，确保它们都反映了新的 `spec/engine/graph/sdk/library` 架构，消除任何残留的旧概念。
2.  **处理技术债务**：我们可以回顾一下 `债务监测.md` 中的条目，看看是否有任何在这次重构后变得更容易解决的问题。
3.  **规划新功能**：现在我们有了一个非常坚实的基础，是时候重新审视用户反馈中的新功能提案了，例如《引入流式编排原语 `cs.sequence` 与 `cs.pipeline`》。
