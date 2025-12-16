好的，我们已经完成了 `Engine` 职责的解耦工作。此操作将核心的协调逻辑与输入解析逻辑分离，显著提高了 `Cascade` 运行时的架构健康度。

现在，我将为您生成提交此变更的计划。

## [COMMIT] refactor(runtime): Decouple argument and constraint resolution from Engine

### 用户需求
提交对 `Engine` 核心运行时进行的重构，将参数解析和资源约束解析逻辑分离到独立的 Resolver 类中。

### 评论
这是一次关键的架构提炼。通过将 `_resolve_arguments` 和 `_resolve_constraints` 逻辑提取到专门的 `ArgumentResolver` 和 `ConstraintResolver` 类中，我们成功地使 `Engine` 专注于其核心的协调和调度角色。这遵循了单一职责原则，并为未来的解析策略扩展提供了清晰的接口。

### 目标
将新创建的 `src/cascade/runtime/resolvers.py` 文件和重构后的 `src/cascade/runtime/engine.py` 文件作为一个逻辑单元提交。

### 基本原理
此变更使 `Engine` 的方法签名更简洁，其内部复杂性得以降低。由于解析逻辑现在集中在 `resolvers.py` 中，它们可以被独立于 `Engine` 进行测试和验证，大大提高了开发者体验（DX）。

### 标签
#intent/refine #intent/architect #flow/ready #priority/high #comp/runtime #concept/architecture #scope/core #scope/dx #ai/instruct #task/domain/architecture #task/object/core-engine #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 暂存并提交变更

将新创建的 `resolvers.py` 文件和重构后的 `engine.py` 添加到 Git 暂存区，并执行提交。

~~~~~act
git_add
src/cascade/runtime/resolvers.py
src/cascade/runtime/engine.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(runtime): Decouple argument and constraint resolution from Engine

The Engine class was taking on too much responsibility, specifically handling the complex logic of argument resolution (including Router lookups and Inject substitution) and dynamic resource constraint resolution.

This refactoring separates concerns:
1. Introduced `ArgumentResolver` to handle dynamic argument assembly.
2. Introduced `ConstraintResolver` to handle resolution of LazyResult values within constraints.

The `Engine` now delegates these tasks, making it a pure coordinator and significantly improving the maintainability and testability of the core runtime.
~~~~~

### 下一步建议

架构重构完成后，我们应立即偿还已识别出的最高优先级技术债务。

根据 `开发/债务分析251216.md` 的报告：
1.  **任务**: 偿还文档债 (高优先级)。
2.  **内容**: 更新 `docs/how-to-guides/improving-robustness.md` 文件，详细介绍新引入的 `.with_constraints()` 和 `cs.run` 的 `system_resources` 参数。

我建议我们开始编写这个文档。
