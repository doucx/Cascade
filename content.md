太棒了！测试全部通过意味着我们的重构不仅实现了预期的深度依赖支持，而且保持了系统的稳定性。

现在我们将这些改动作为一个完整的逻辑单元提交。这标志着 Cascade 架构向“直觉化”迈出了重要的一步。

## [COMMIT] refactor: 架构直觉化与深度依赖支持

### 用户需求
解决 Cascade 架构中不符合直觉的限制（如无法在列表中嵌套依赖）并提升开发者体验。

### 评论
这是 Cascade 核心运行时的一次重大进化。通过从“浅层参数扫描”转向“深度结构解析”，我们彻底消除了 Python 开发者在使用列表、字典组合任务时最常遇到的陷阱。同时，新增的 `cs.dict` 和 `cs.format` 让工作流的表达更加自然，而显式的 `ResourceNotFoundError` 则让 DI 系统的调试变得轻松。

### 目标
1.  提交支持深度依赖发现的 `GraphBuilder` 和 `ArgumentResolver`。
2.  提交新增的 `cs.dict` 和 `cs.format` 提供者。
3.  提交增强的 DI 报错机制。
4.  包含所有配套的测试用例。

### 基本原理
我们将所有与阶段二（架构直觉化）相关的代码和测试变动打包提交。这包括运行时内核的重构、提供者扩展以及相应的工具函数调整。

### 标签
#intent/refine #flow/ready #priority/high #comp/core #comp/runtime #comp/py #concept/graph #concept/di #scope/api #scope/dx #ai/instruct #task/domain/core #task/object/architecture #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交阶段二成果

我们将所有修改过的文件添加到暂存区并创建详细的提交。

~~~~~act
git_add
packages/cascade-py/src/cascade/providers/helpers.py
packages/cascade-py/pyproject.toml
packages/cascade-runtime/src/cascade/runtime/exceptions.py
packages/cascade-runtime/src/cascade/graph/build.py
packages/cascade-runtime/src/cascade/runtime/resolvers.py
packages/cascade-runtime/src/cascade/graph/serialize.py
packages/cascade-py/src/cascade/tools/preview.py
tests/cascade-py/providers/test_helpers.py
tests/cascade-runtime/graph/test_build.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: implement deep dependency resolution and intuitive helpers

This major refactoring removes long-standing architectural limitations and improves the overall Developer Experience (DX).

Key Changes:
1. **Deep Dependency Discovery**: Refactored `GraphBuilder` and `ArgumentResolver` to recursively scan and resolve dependencies nested within lists, tuples, and dictionaries. This allows users to naturally group task results without breaking the dependency graph.
2. **Intuitive Helpers**: Introduced `cs.dict()` and `cs.format()` providers. `cs.format` provides a lightweight, Jinja-free way to perform string interpolation, while `cs.dict` enables clean composition of dynamic task inputs.
3. **Explicit DI Errors**: Replaced silent failures and `None` injections in `cs.inject` with a loud `ResourceNotFoundError`, significantly easing the debugging of dependency injection issues.
4. **Improved Observability**: Updated the `dry_run` tool to filter out internal lazy objects from the output, ensuring a clean, literal-only view of the execution plan.

Validated with new unit and integration tests covering nested dependency resolution and the new helper providers.
~~~~~

### 下一步建议
我们已经完成了阶段二的核心工作。现在 Cascade 已经变得非常顺手且强大。

下一步建议进入 **阶段三：文档与契约**。
1.  **编写 `CONTRIBUTING.md`**: 记录新的安装流程 (`uv pip install -e .[dev]`) 和开发规范。
2.  **更新入门教程**: 确保 `getting-started.md` 展示了我们刚实现的这些“直觉化”用法（例如列表依赖和 `cs.format`）。

如果你准备好了，请指示我开始阶段三。
