好的，既然代码已经重构完成且符合“Cascade 编程模型”原则，我们现在将这些变更提交。这将正式应用新的 CI/CD 逻辑并触发流水线运行。

## [COMMIT] refactor(ci): align cicd with cascade programming model

### 用户需求
提交对 `cicd` 模块和相关测试的重构，以正式启用符合 Cascade 编程模型的声明式 CI/CD 流程。

### 评论
通过将变更原子化提交，我们确保了代码库的一致性。这次重构不仅提升了 CI/CD 的透明度，也为后续在 `visualize` 工具中观察自动化任务图奠定了基础。

### 目标
1. 将 `cicd/tasks.py`、`cicd/workflows.py` 和 `tests/cicd/test_tasks.py` 添加到暂存区。
2. 创建一个符合 Conventional Commits 规范的详细提交记录。

### 基本原理
遵循 `d3-constraint-quipu-plan-script-rules` 协议，在独立于文件修改的计划中执行 Git 操作。这确保了变更在被永久记录之前已经过环境确认。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #concept/workflow #scope/core #ai/instruct #task/domain/ops #task/object/ci-pipeline #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交 CI/CD 重构代码

我们将把重构后的任务逻辑、工作流定义以及单元测试一并提交。

~~~~~act
git_add
cicd/tasks.py
cicd/workflows.py
tests/cicd/test_tasks.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(ci): align cicd with cascade programming model

This commit refactors the CI/CD pipeline to eliminate the "Task-Calling-Task" (TCO Anti-pattern) and adhere to the transparency principles of the Cascade Programming Model.

Key changes:
- Refactored `cicd/tasks.py`: Tasks are now "Recipe Generators" that return pure command strings (str) instead of executing side effects internally.
- Refactored `cicd/workflows.py`: Workflows now explicitly compose commands and execute them via `cs.shell`, making the execution graph fully visible to static analysis.
- Updated `tests/cicd/test_tasks.py`: Tests now verify the generated command strings directly, simplifying the testing surface.

This move from an opaque, imperative execution model to a transparent, declarative one ensures that tools like `cs.visualize()` can correctly render the CI/CD pipeline.
~~~~~

### 下一步建议
- **监控 CI**: 观察 GitHub Actions 或本地 CI 环境的运行情况，确保显式调用的 `cs.shell.map` 能够正确处理包的并发 lint 和 test。
- **架构可视化**: 建议在本地运行 `cascade visualize cicd.workflows:pr_check_workflow`（如果工具链已支持），以直观确认图结构的透明度提升。
