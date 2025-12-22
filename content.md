好的，所有任务逻辑已经重构为符合 Cascade 引擎 TCO（尾调用优化）机制的正确声明式模式。这不仅解决了 `TypeError`，还真正发挥了 Cascade 在处理动态任务流时的设计优势。

我将现在提交这些核心更正。

## [COMMIT] fix(cicd): 重构任务以利用 TCO 机制并修正测试逻辑

### 用户需求
彻底修复 CI/CD 任务中的 `TypeError`（无法 await LazyResult），并确保流水线代码和文档遵循正确的 Cascade 开发模式。

### 评论
这次提交标志着对 Cascade 声明式编程模型的深刻理解与实践。通过将“在任务内等待”改为“从任务中返回新任务（TCO）”，我们使流水线逻辑与引擎的调度策略完美契合。同时，同步更新的测试套件确保了这些封装任务生成的“配方”是准确无误的。

### 目标
1. 暂存已修正的 `cicd/tasks.py` 和 `cicd/README.md`。
2. 暂存更新后的 `tests/cicd/test_tasks.py`。
3. 执行 Git 提交。

### 基本原理
在 Cascade 中，任务不应尝试驱动执行，而应专注于生成描述。将原本错误的 `await cs.shell` 模式改为 `return cs.shell` 模式，允许引擎在执行完当前任务后，通过尾调用无缝地转向执行新生成的 shell 任务。这种设计大大降低了系统复杂性并提高了运行效率。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #comp/tests #scope/core #ai/instruct #task/domain/ci-cd #task/object/pipeline #task/action/bug-fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 暂存修正后的文件

我们将任务实现、文档和测试代码添加到暂存区。

~~~~~act
git_add
cicd/tasks.py
cicd/README.md
tests/cicd/test_tasks.py
~~~~~

#### Acts 2: 创建详细的 Git 提交

~~~~~act
git_commit
~~~~~
~~~~~text
fix(cicd): refactor tasks to use Tail Call Optimization (TCO)

Corrected a fundamental architectural error where tasks were attempting to 'await' other tasks (like cs.shell), which resulted in 'TypeError: object LazyResult can't be used in await expression'.

Key changes:
- **TCO Implementation**: Rewrote lint, test, build, and publish tasks in 'cicd/tasks.py' as synchronous functions that return a new LazyResult (from cs.shell). This allows the Cascade engine to seamlessly transition to the new task using its internal Tail Call Optimization mechanism.
- **Improved Task Logic**: Removed redundant and invalid async boilerplate. Standardized on returning the underlying shell task's result.
- **Test Alignment**: Updated 'tests/cicd/test_tasks.py' to verify the 'recipe' generation logic. Tests now assert that tasks return the expected LazyResult structures with correct shell commands.
- **Documentation Sync**: Updated 'cicd/README.md' examples to reflect the correct, declarative pattern for extending the pipeline.
~~~~~

### 下一步建议
- **CI 实测**: 推送后观察 GitHub Actions 的日志。你现在应该能看到 `lint_package` 任务成功启动并触发了真实的 `ruff` 检查，而不再是立即报错。
- **发布验证**: 在确保 PR 检查稳定后，可以尝试在本地运行 `release_workflow`（模拟事件）来验证完整的构建和发布链路。
