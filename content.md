我已经完成了 CI 任务重构引发的测试同步工作，并确认了当前的文件状态。现在我将生成一个 `[COMMIT]` 计划来提交所有关于 CI 修复的变更。

## [COMMIT] fix(ci): Resolve coverage concurrency issue and import errors

### 用户需求
修复 CI/CD 流程中的稳定性问题，包括：
1.  解决并发 `pytest-cov` 写入导致的 `.coverage` 文件损坏问题 (`coverage.exceptions.DataError`)。
2.  修复因移除 `get_test_command` 任务后，测试文件 (`cicd/tests/test_tasks.py`) 导致的 `ImportError`。

### 评论
这次提交确保了 CI 流程的健壮性。通过将所有测试合并到一个单一的 `pytest` 进程中执行，我们解决了覆盖率报告中的致命竞态条件。同时，我们同步更新了测试用例，使测试基础设施的完整性得到了维护。

### 目标
1.  提交 `cicd/tasks.py` 和 `cicd/workflows.py` 中关于测试命令聚合的逻辑变更。
2.  提交 `cicd/tests/test_tasks.py` 中对新聚合逻辑的测试。

### 基本原理
1.  **并发修复**: 移除 `cicd/tasks.py` 中的 `get_test_command`，并引入 `get_aggregated_test_command(package_names: List[str])`。新的任务将所有待测试包路径聚合为一个 `pytest packages/a packages/b ...` 命令。
2.  **流程更新**: 修改 `cicd/workflows.py`，确保 `pr_check_workflow` 和 `release_workflow` 调用新的聚合任务，从而保证所有测试在一个进程内执行。
3.  **测试同步**: 更新 `cicd/tests/test_tasks.py`，移除对旧任务的依赖，并新增对 `get_aggregated_test_command` 的断言，包括测试空列表输入的健壮性。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #concept/state #scope/dx #ai/instruct

---
### Script

#### Acts 1: 提交 CI 修复和同步代码

~~~~~act
git_add
cicd/tasks.py
cicd/workflows.py
cicd/tests/test_tasks.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(ci): Resolve coverage concurrency issue and consolidate test commands

The previous CI workflow executed tests for changed packages using separate `cs.shell.map` calls, resulting in multiple concurrent `pytest --cov` processes. This caused a race condition and corruption of the shared `.coverage` SQLite file, leading to CI failures.

This commit resolves the issue by:
1.  **Aggregating Test Commands**: Replacing the old `get_test_command` task with `get_aggregated_test_command`, which generates a single `pytest packages/a packages/b` command string.
2.  **Updating Workflows**: Modifying `pr_check_workflow` and `release_workflow` to execute this single, aggregated test command, ensuring all tests run within a coordinated process and avoiding coverage file corruption.
3.  **Synchronizing Tests**: Updating `cicd/tests/test_tasks.py` to test the new aggregated command logic and removing references to the deleted task, fixing the final `ImportError`.
~~~~~
