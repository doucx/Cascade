好的，所有测试通过，对 `task` 装饰器的升级和 `shell` 任务的实现均已验证。我们将创建最终的 `[COMMIT]` 计划，正式结束 Cascade 阶段二。

## [COMMIT] feat(stdlib): Implement the Shell task and complete Phase Two

### 用户需求
1.  实现 `shell` 预置任务，作为执行外部命令的健壮接口。
2.  将 `task` 装饰器升级为支持命名参数的工厂模式。
3.  提交所有关于 `shell` 任务和 `task` 装饰器的修改，正式标记 Cascade 阶段二核心工作完成。

### 评论
本次提交通过实现 `cs.shell` 任务，极大地提升了 Cascade 在自动化和 DevOps 场景中的实用性，并进一步完善了开发者体验。同时，将 `@task` 升级为 decorator factory，使得任务的命名和元数据配置更加灵活，为未来更复杂的元编程和工具化奠定了基础。Cascade 现在已全面具备异步、重试、缓存的能力，为进入阶段三的生态构建做好了准备。

### 目标
1.  将 `src/cascade/spec/task.py`, `src/cascade/stdlib.py`, `src/cascade/__init__.py` 和 `tests/test_stdlib.py` 文件添加到 Git 暂存区。
2.  创建一个内容详尽的 Git Commit。

### 基本原理
将 `task` 装饰器重构与 `shell` 任务的实现放在一起提交是合理的，因为 `shell` 任务的实现（使用 `name="shell"`）直接推动了 `task` 装饰器的 API 升级。这构成了代码历史中一个完整的、驱动式演进的工作单元。

### 标签
#intent/build #flow/ready #priority/high
#comp/spec #comp/stdlib #comp/tests #scope/api #scope/dx
#task/domain/core #task/object/prebuilt-tasks #task/action/implementation
#task/state/end #task/status/completed

---

### Script

#### Acts 1: Stage all changes

将所有相关文件添加到 Git 暂存区。

~~~~~act
git_add
src/cascade/spec/task.py
src/cascade/stdlib.py
src/cascade/__init__.py
tests/test_stdlib.py
~~~~~

#### Acts 2: Commit changes

现在，我们创建一个内容详尽的提交。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(stdlib): Implement shell task and upgrade @task decorator

This commit introduces the final user-facing feature of Phase Two and includes a critical API improvement:

1.  **Shell Task (`cs.shell`)**: A pre-built asynchronous task for executing external commands. It automatically captures stdout/stderr and integrates robust error checking (`check=True` by default), replacing the need for users to manually wrap `subprocess.run` calls.

2.  **@task Decorator Upgrade**: The `@task` decorator in `cascade.spec.task` has been upgraded to a decorator factory, allowing users to pass arguments like `@task(name="...")` for better task traceability and logging. This structure is also used internally by the new `shell` task.

These additions significantly enhance developer experience (DX) and complete the functionality set planned for Phase Two, marking the transition to Phase Three development.
~~~~~

### 下一步建议
**Cascade 阶段二已正式结束。**

下一步，我们将启动 **阶段三：走向生态与可扩展性**。我建议我们从阶段三计划中的一个关键功能开始：**可视化工具 (`cs.visualize`)**。

可视化工具将使复杂的计算图变得直观易懂，这是提升框架被大型项目采纳的关键一步。如果你同意，我将生成实现 `cs.visualize` 的计划。
