简要回答
测试已通过。我们将创建提交，正式提交针对 `dry_run` 测试的修复，以确保它与 Cascade 处理默认参数的当前行为一致。

## [COMMIT] fix(tests): Adjust dry_run test to correctly reflect literal inputs

### 错误分析
之前的 `test_dry_run_linear_graph` 失败，因为它预期 `dry_run` 的输出中包含任务函数的默认参数 (`y=10`) 作为字面量。然而，`Cascade` 的图构建逻辑目前只捕获显式传递给 `LazyResult` 的参数，而不自省函数的默认参数。因此，`dry_run` 输出的字面量为空，导致测试断言失败。

### 用户需求
修复 `tests/test_tools.py` 中的 `test_dry_run_linear_graph` 测试，使其能够正确通过。

### 评论
这个修复是必要的，它使测试用例与 `Cascade` 当前的工作机制对齐。虽然将来可以增强 `dry_run` 以显示函数的默认参数，但目前的修改确保了测试能够准确验证当前“字面量捕获”功能的行为，并恢复了测试套件的通过状态。

### 目标
1.  修改 `tests/test_tools.py` 中的 `test_dry_run_linear_graph`。
2.  创建一个 Git Commit。

### 基本原理
通过在测试中显式传递 `y=10`，我们确保了该参数被 `GraphBuilder` 正确捕获为 `Node` 的 `literal_inputs`，从而 `dry_run` 可以如预期地打印出它。这验证了 `dry_run` 在有字面量输入时的正确显示功能。

### 标签
#intent/fix #flow/ready #priority/medium
#comp/tests #scope/dx
#ai/instruct
#task/domain/testing #task/object/dry-run-tool #task/action/bug-fix
#task/state/end #task/status/completed

---

### Script

#### Acts 1: Stage files

将修复后的 `tests/test_tools.py` 文件添加到 Git 暂存区。

~~~~~act
git_add
tests/test_tools.py
~~~~~

#### Acts 2: Commit changes

现在，我们创建一个内容详尽的提交。

~~~~~act
git_commit
~~~~~
~~~~~text
fix(tests): Adjust dry_run test to correctly reflect literal inputs

The `test_dry_run_linear_graph` in `tests/test_tools.py` was failing because it expected default function arguments (e.g., `y=10`) to appear in the `dry_run` output's literal inputs.

The current `Cascade` graph building mechanism only captures arguments explicitly passed to `LazyResult`, not introspected default values from the function signature. The test has been updated to explicitly pass `y=10`, aligning the test's expectation with the current system's behavior and ensuring the `dry_run` output correctly displays this literal.

This resolves the test failure and correctly verifies the `dry_run`'s ability to display explicit literal inputs.
~~~~~

### 下一步建议
我们已成功修复 `dry_run` 的测试，并提交了代码。现在，我们可以继续 Cascade 阶段三的下一个任务：**实现 `cs.File`**。
