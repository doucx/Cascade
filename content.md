## [COMMIT] test(graph): Add test for impurity propagation in pure functions

### 用户需求
提交新增的测试用例 `test_impurity_propagates_through_pure_functions`，该测试验证了不纯性通过依赖链向上传播的正确行为。

### 评论
这个测试用例提高了我们对 CP-006 行为验证的保真度。它确保了 Pure 任务在依赖于不同的 Impure 任务实例时，不会被错误地去重，证明了我们对哈希逻辑的修改是稳健的。

### 目标
提交 `tests/engine/graph/test_purity_model.py` 文件中的新增内容。

### 基本原理
该测试通过验证复合场景（`pure(impure)`）下的哈希行为，作为核心 `HashingService` 变更的安全网，是确保功能正确性的重要组成部分。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/tests #scope/dx #ai/instruct #task/domain/core #task/object/task-purity #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交测试文件修改

将已修改并验证通过的测试文件添加到 Git 暂存区，并执行提交。

~~~~~act
git_add
tests/engine/graph/test_purity_model.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
test(graph): Add test for impurity propagation in pure functions

Adds a new test case: `test_impurity_propagates_through_pure_functions`.

This critical test verifies that when a pure task consumes the output of an impure task, the impurity (uniqueness) of the upstream task's structural ID is correctly propagated.

This prevents a pure task from being incorrectly deduplicated if its arguments come from two distinct, side-effecting calls (e.g., `pure(impure_a())` vs `pure(impure_b())`).
~~~~~
