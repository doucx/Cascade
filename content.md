你的分析和修复方案非常清晰，而且测试通过验证了你的重构是成功的。现在，我将为你生成一个 `[COMMIT]` 计划，把本次架构升级和 Bug 修复作为一个完整的、可交付的工作单元提交到版本控制系统。

## [COMMIT] refactor(runtime): Implement pluggable constraint handler architecture

### 用户需求
完成“路线图：可插拔约束处理器架构 (v1.0)”的所有里程碑，修复 CLI 命名冲突导致的 `TypeError`，并提交一个完整的、通过测试的工作单元。

### 评论
本次提交是 Cascade 架构的一个重大飞跃，使核心运行时符合“协议驱动”原则。通过将约束评估逻辑从 `ConstraintManager` 剥离到独立的 `ConstraintHandler` 协议中，我们增强了系统的可插拔性和可测试性，同时实现了基于 `scope` 的任务级暂停功能。此外，我们修复了 `cs.cli` 与 `cascade.cli` 命名空间包的冲突，提高了开发者体验（DX）。

### 目标
1.  将 `ConstraintManager` 改造为通用的处理器调度器。
2.  实现 `ConstraintHandler` 协议和第一个具体实现 `PauseConstraintHandler`。
3.  在 `Engine` 启动时自动注册处理器，恢复并增强约束功能。
4.  将 `cs.cli` 重命名为 `cs.create_cli`，修复命名空间冲突。

### 基本原理
我们通过以下步骤实现了架构的解耦和增强：
1.  **协议化**: 定义 `ConstraintHandler` 协议，将业务逻辑（如“如何暂停”）从调度核心中分离。
2.  **调度器模式**: `ConstraintManager` 现在只负责管理活动约束和调用正确的处理器，遵循“单一职责原则”。
3.  **连接**: 在 `Engine` 构造函数中将 `PauseConstraintHandler` 注入到管理器，保证了系统的开箱即用性。
4.  **Bug Fix**: 重命名 `cli` 函数解决了 Python 命名空间包的导入冲突，提高了代码的健壮性。

### 标签
#intent/refine #intent/fix #flow/done #priority/high #comp/runtime #comp/cli #concept/config #scope/api #ai/instruct #task/domain/runtime #task/object/constraint-system #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 添加所有修改和新增的文件到暂存区

~~~~~act
git_add
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
packages/cascade-runtime/src/cascade/runtime/constraints/__init__.py
packages/cascade-runtime/src/cascade/runtime/constraints/protocols.py
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
packages/cascade-runtime/src/cascade/runtime/engine.py
packages/cascade-py/src/cascade/tools/cli.py
packages/cascade-py/src/cascade/__init__.py
tests/cli/test_cli.py
~~~~~

#### Acts 2: 创建 Git 提交

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(runtime): Implement pluggable constraint handler architecture

This major refactoring decouples the ConstraintManager from specific constraint logic, making the system extensible and testable for future control types (rate limiting, concurrency).

Key Architectural Changes (Milestones 1-4):
1.  Introduced `ConstraintHandler` protocol and created `PauseConstraintHandler`.
2.  Refactored `ConstraintManager` into a pure dispatcher/registry that delegates `check_permission` calls to registered handlers.
3.  Integrated the registration of `PauseConstraintHandler` into the `Engine` initialization, restoring global pause functionality and adding support for task-scoped pauses (e.g., `task:api_call`).

Bug Fix:
-   Fixes an import error by renaming `cs.cli` to `cs.create_cli` to resolve a conflict with the `cascade.cli` namespace package established by external CLI tools.
~~~~~

### 下一步建议
约束系统的核心架构现在已经完全解耦。根据 `Phase 3 (Refined) & Phase 4 并行开发路线图.md`，下一步是实现更高级的并发和速率管理。

我建议开始**里程碑 3.2：并发管理 (Concurrency Management)**，这将要求您实现一个新的 `ConcurrencyConstraintHandler`，并将其与 `ResourceManager` 动态集成，以允许通过外部约束消息动态调整并发限制。
