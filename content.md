Excellent. With the tests passing, we have validated both the new `cs.sql` provider and the crucial enhancement to the dependency injection system. This is a significant step forward for the framework's flexibility.

I will now generate the `[COMMIT]` plan to merge these changes.

## [COMMIT] feat(core): Add dynamic DI and implement `cs.sql` provider

### 用户需求
将已完成并经过测试的 `cs.sql` provider 以及其所依赖的、对核心动态依赖注入（DI）系统的增强，作为一个完整的逻辑单元提交到版本控制中。

### 评论
这是一个双重价值的提交。它不仅交付了一个高价值的 `cs.sql` Provider，还从根本上提升了 `Cascade` 核心 DI 系统的灵活性。通过允许在任务调用时动态传递 `cs.inject("resource_name")`，我们打破了资源依赖必须在任务签名中静态声明的限制。这一核心改进使得 `cs.sql` 等 Provider 变得异常强大和可复用，为未来构建更复杂的、上下文感知的工具奠定了坚实的基础。

### 目标
创建一个 Git 提交，包含对 `Engine` 和 `Executor` 中 DI 逻辑的增强、新的 `SqlProvider` 的完整实现、`sqlalchemy` 依赖项的添加以及所有相关的测试代码。

### 基本原理
动态 DI 的增强和 `cs.sql` Provider 的实现是紧密耦合的，后者依赖于前者的功能。将它们作为一整个逻辑单元进行开发、测试和提交，可以确保版本历史的原子性和清晰性，形成一个稳定、可验证的里程碑。

### 标签
#intent/build #intent/refine #flow/ready #priority/high #comp/core #comp/runtime #concept/di #concept/sql #scope/api #scope/dx #ai/instruct #task/domain/ecosystem #task/object/sql-provider #task/action/implementation #task/state/continue #task/status/active

---

### Script

#### Acts 1: 暂存所有相关变更

我们将所有与此功能相关的修改和新增文件添加到 Git 暂存区。

~~~~~act
git_add
pyproject.toml
src/cascade/adapters/executors/local.py
src/cascade/providers/sql.py
src/cascade/runtime/engine.py
tests/test_sql.py
~~~~~

#### Acts 2: 创建 Git 提交

现在，执行 `git commit` 并附上详细的提交信息，解释这次重要的核心升级和新功能。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(core): Add dynamic DI and implement cs.sql provider

This commit introduces two major enhancements: a more flexible, dynamic Dependency Injection (DI) system and a new `cs.sql` provider that leverages it.

Core DI Enhancement:
- The DI mechanism is no longer limited to static injection via function signature defaults.
- `Engine`: The resource scanner (`_scan_for_resources`) now inspects a task's literal arguments for `Inject` objects, allowing resources to be discovered at graph build time even when passed dynamically.
- `LocalExecutor`: The argument resolution logic now identifies and resolves `Inject` objects passed as regular arguments, fetching the corresponding resource from the active context at runtime.

`cs.sql` Provider:
- A new `cs.sql` provider is introduced, using SQLAlchemy as an optional dependency (`[sql]`).
- It exposes a factory `cs.sql(query, db, params)` that allows users to dynamically specify the target database resource via the `db` string argument.
- The provider's implementation serves as a prime example of the new dynamic DI, converting the `db` name into an `Inject` object passed to an underlying task.
- The task robustly handles both SQLAlchemy `Engine` and `Connection` objects.

This dual enhancement significantly increases the power and reusability of providers and marks a key step in making Cascade a more versatile and enterprise-ready automation framework.
~~~~~

### 下一步建议
我们已经成功地交付了两个高价值的 Provider (`http`, `sql`) 并增强了核心引擎。现在是时候关注开发者体验和可观测性了。根据我们的路线图和积压的改进点，我强烈建议下一步实现：

**`cs.visualize(target)`**: 提供一个将计算图可视化为 Graphviz DOT 格式的工具。这将极大地帮助我们（以及未来的用户）理解和调试日益复杂的工作流，使依赖关系一目了然。
