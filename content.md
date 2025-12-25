是的，我们已经完成了这项重构任务的所有工作。

您的总结非常准确。我们不仅完成了您列出的前四个阶段的结构性重构，而且在后续的交互中，我们已经成功地解决了您指出的所有“遗留问题”：

1.  **Mock 提取**: 我们已将 `MockExecutor`, `MockConnector` 和所有相关的行为变体 (`SlowWorkExecutor` 等) 全部提取并统一到了 `cascade.testing`。
2.  **遗留的 MockSolver**: 我们也已将 `MockSolver` 成功提取。

现在，代码库的测试基础设施已经高度统一和整洁，所有已识别的冗余都已被消除。这是一个完整的、可交付的工作单元。

我将生成一个 `[COMMIT]` 计划来提交这些成果。

## [COMMIT] refactor(testing): 统一测试结构并中心化核心测试辅助工具

### 用户需求
对整个项目的测试基础设施进行深度重构，包括：
1.  将测试代码与源代码并置 (Co-location)。
2.  消除跨包的测试依赖。
3.  解决测试隔离性问题。
4.  将所有重复定义的测试辅助类（Spies, Mocks, Stubs）中心化到一个统一的模块中。

### 评论
这是一次至关重要的、影响深远的重构。它极大地提升了项目的架构健康度和开发者体验 (DX)。通过建立一个清晰、隔离且无冗余的测试环境，我们为未来的功能开发和维护工作奠定了坚实的基础。

### 目标
1.  将自上次提交以来的所有文件结构变更和代码修改提交到版本库。
2.  创建一个清晰、全面的 Git 提交信息，记录下这次重构的完整范围和基本原理。

### 基本原理
这次重构分两个主要阶段完成：
1.  **结构整理**: 通过将测试文件移动到其所属包的 `tests/` 目录下，实现了代码和测试的并置，增强了模块的内聚性。同时解决了由此引发的 Fixture 和测试状态泄漏问题。
2.  **工具集中心化**: 通过在 `cascade.testing` 模块中创建并统一 `MockExecutor`, `MockConnector`, `MockSolver` 以及所有 `Spy*` 类，彻底贯彻了 DRY 原则。这确保了整个测试套件中使用行为一致的测试替身，简化了未来的测试编写工作。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #comp/build #scope/dx #ai/instruct #task/domain/testing #task/object/test-doubles #task/action/refactor #task/state/end

---
### Script

#### Acts 1: 提交所有重构变更

我们将把所有已暂存的变更提交到 Git 仓库，形成一个逻辑上完整的提交。

~~~~~act
git_add
.
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(testing): Unify test structure and centralize core test doubles

This extensive refactoring overhauls the entire testing infrastructure to improve modularity, developer experience, and maintainability. The changes are in two main categories:

1.  **Test Co-location and Isolation:**
    -   Moved all package-specific tests from the root `tests/` directory to a `tests/` subdirectory within each respective package (e.g., `packages/cascade-engine/tests/`).
    -   Relocated tests that were "parasitic" in other packages to their correct homes (e.g., graph tests moved to `cascade-graph`, connector tests to `cascade-connector-local`).
    -   Resolved test isolation issues, particularly state leakage from the `LocalBusConnector` in E2E tests, by introducing a scoped conftest.

2.  **Centralization of Test Doubles (DRY):**
    -   Created a canonical `cascade.testing` module to act as a centralized home for all test utilities.
    -   Consolidated all variations of Spies, Mocks, and Stubs into this module, removing dozens of redundant local definitions across the test suite.
    -   Key centralized classes include: `MockExecutor`, `MockConnector`, `MockSolver`, `SpyExecutor`, `SpySolver`, and `SpySubscriber`.
    -   Refactored all tests to import and use these standardized doubles, ensuring consistent mock behavior and simplifying test setup.

This commit represents a foundational improvement, making the codebase cleaner, more organized, and easier to work with.
~~~~~

### 下一步建议
- **文档化**: 考虑为 `cascade.testing` 模块添加文档字符串或一篇简短的开发者文档，说明如何使用这些新的、统一的测试辅助工具。
- **新功能**: 现在测试基础设施已经非常稳固，我们可以更有信心地开始构建下一个主要功能。
