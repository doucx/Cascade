好的，我们已经完成了对 `src` 目录下核心代码重复问题的修复。现在是时候将这些重要的架构改进提交到版本控制中了。

我将生成一个 `[COMMIT]` 计划，它会暂存我们修改过的文件并创建一个清晰的提交记录。

## [COMMIT] refactor(arch): 消除核心包之间的代码重复

### 用户需求
用户要求将之前解决代码重复（DRY）问题的重构工作提交到 Git 仓库。

### 评论
这是一个关键的提交，它固化了我们为提高代码库健康度所做的努力。通过消除重复，我们降低了未来维护的复杂性，并确保了整个系统中类型和协议的一致性。

### 目标
1.  将所有被修改的文件（涉及 `cascade-engine`, `cascade-application`, `cascade-sdk`）添加到 Git 的暂存区。
2.  创建一个符合 Conventional Commits 规范的提交，详细说明本次重构的动机和具体内容。

### 基本原理
根据 `d3-constraint-quipu-plan-script-rules` 协议，一个 `[COMMIT]` 计划应该只包含 Git 相关操作。此计划将把文件系统变更的逻辑单元（在上一步完成）与版本控制的逻辑单元（本次提交）清晰地分离开来。

### 标签
#intent/refine #flow/ready #priority/high #comp/interfaces #comp/engine #scope/core #ai/instruct #task/domain/refactoring #task/object/dry-compliance #task/action/deduplicate #task/state/end

---

### Script

#### Acts 1: 暂存并提交变更

我们将把所有相关的修改暂存，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/cascade-engine/src/cascade/runtime/events.py
packages/cascade-application/src/cascade/app/__init__.py
packages/cascade-sdk/src/cascade/tools/events.py
packages/cascade-sdk/src/cascade/providers/registry.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(arch): Eliminate DRY violations across core packages

This commit addresses critical code duplication issues identified by the `check_dry_violations.py` script, improving architectural consistency and reducing maintenance overhead.

Key changes:
1.  **Centralized Tooling Events**:
    - The `ToolEvent` class and its subclasses (`PlanAnalysisStarted`, `PlanNodeInspected`, `PlanAnalysisFinished`) were duplicated between `cascade-application` and `cascade-sdk`.
    - These event definitions have been moved to a single source of truth in `cascade.runtime.events` within the `cascade-engine` package.
    - Both `cascade-application` and `cascade-sdk` now import these events, ensuring a consistent data contract for tooling and analysis across the ecosystem.

2.  **De-duplicated `LazyFactory` Protocol**:
    - The `LazyFactory` protocol was defined independently in both `cascade-spec` and `cascade-sdk`.
    - The redundant definition in `cascade-sdk` has been removed. The SDK now correctly imports the protocol from `cascade.spec.protocols`, which is the authoritative source for interface specifications.
~~~~~

### 下一步建议
现在代码库更加整洁了。你可以再次运行 `scripts/check_dry_violations.py` 来确认我们的修复已经生效。

下一步，我们可以考虑：
1.  **处理次要命名冲突**：分析脚本报告的其他命名冲突（例如 `MessageBus`），评估它们是否构成真正的架构问题，并制定相应的重构计划。
2.  **改进脚本**：为 `check_dry_violations.py` 添加更多配置选项，例如允许按路径排除文件（如 `tests/` 目录），使其报告更加聚焦于生产代码。
