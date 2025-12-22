好的，我将执行一个包含所有 linting 修复的 `[COMMIT]` 计划。

## [COMMIT] fix: Clean up all ruff linting errors (F841, E402, F821)

### 错误分析

此任务涉及解决多个 Ruffle 报告的错误：

1.  **F841 (Unused Variables)**: 多个文件中存在不再使用的局部变量（例如 `consumer_queues`, `results`, `rate`, `updates_count`, `node_map`, `flash_times` 等）。这些是代码重构后留下的死代码，增加了认知负担。
2.  **E402 (Misplaced Imports)**: 在 `cascade-sdk/src/cascade/__init__.py` 等文件中，导入语句被放置在模块顶层以外的位置，违反了 PEP 8 规范。
3.  **F821 (Undefined Names)**: 在 `cascade-engine/src/cascade/runtime/engine.py` 中，由于缺少核心类型 `LazyResult` 和 `MappedLazyResult` 的导入，导致名称未定义。

### 用户需求
解决所有由 `ruff check .` 报告的 14 个 linting 错误。

### 评论
这些修复是基础的代码卫生工作，确保了项目的可维护性和遵循标准规范。特别是对 Engine 核心的 `F821` 修复和对测试脚本中死代码的清理，消除了潜在的歧义和未来可能引入的 bug。

### 目标

1.  通过移除或重构，消除所有无用变量的赋值。
2.  将所有模块级导入移动到文件顶部。
3.  导入 Engine 核心所需的 `LazyResult` 和 `MappedLazyResult` 类型。
4.  创建一个描述详尽的 Git Commit。

### 基本原理

根据 `d3-constraint-quipu-plan-script-rules` 约束，文件系统修改和 Git 提交必须隔离。由于所有的文件修改已在前面的 [WIP] 计划中完成并通过测试，本计划只包含 `git_add` 和 `git_commit` 指令，并使用 `[COMMIT]` 状态标记。

### 标签
#intent/fix #flow/ready #priority/medium #comp/engine #comp/cli #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/linting #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 暂存所有修改的文件

将所有涉及 linting 修复的文件添加到 Git 暂存区。

~~~~~act
git_add
observatory/protoplasm/networking/proto_direct_connect.py
observatory/protoplasm/physics/recursion_test.py
observatory/scripts/debug_headless_throughput.py
observatory/visualization/raw_app.py
packages/cascade-cli-observer/src/cascade/cli/observer/rendering.py
packages/cascade-engine/src/cascade/runtime/engine.py
packages/cascade-engine/src/cascade/runtime/strategies.py
packages/cascade-library/src/cascade/providers/template.py
packages/cascade-sdk/src/cascade/__init__.py
tests/cli/e2e/test_e2e_cli_local_backend.py
tests/engine/runtime/test_engine_recursion.py
~~~~~

#### Acts 2: 提交变更

创建一个单一的、详细的提交。

~~~~~act
git_commit
~~~~~
~~~~~text
fix(lint): Clean up all ruff linting errors (F841, E402, F821)

This patch resolves all 14 reported ruff check errors, improving code hygiene and compliance with PEP 8.

- **F841 (Unused Variables)**: Removed several unused local variables (`consumer_queues`, `results`, `rate`, `updates_count`, `node_map`, `flash_times`, `idx_run1`, `result`) across various files, including the removal of the now-redundant `collections.deque` import.
- **E402 (Misplaced Imports)**: Corrected import order in `cascade/__init__.py`, `rendering.py`, and `template.py` by moving module-level imports to the top of the file.
- **F821 (Undefined Names)**: Added missing imports for `LazyResult` and `MappedLazyResult` in `cascade/runtime/engine.py` to correctly define Tail Call Optimization (TCO) logic types.
~~~~~

### 下一步建议

代码库现在通过了 linting 检查。你可以继续进行下一个功能或重构任务。

如果后续任务涉及新的功能开发，请先运行 `git status` 确认工作区是干净的。
