## [COMMIT] refactor(tests): Optimize sqlite_db fixture scope in test_sql.py

### 用户需求
提交对 `tests/providers/test_sql.py` 文件的修改，以遵循 `d3-principle-pytest-fixture-scoping` 原则，提升数据库相关的 Fixture 作用域，提高测试执行速度。

### 评论
这次重构有效地将数据库连接和初始化等高成本的 I/O 操作隔离到 `module` 作用域的 `db_engine` Fixture 中，确保在测试文件级别只执行一次，从而显著减少了测试的重复设置开销。

### 目标
创建一个 Git 提交，记录 `tests/providers/test_sql.py` 中 Fixture 作用域的优化。

### 基本原理
数据库资源的 setup（创建 in-memory 数据库和填充数据）是测试中的主要性能瓶颈之一。通过将 `Engine` 实例及其资源注册提升到 `module` 作用域，我们遵循了最佳实践，避免了在每个 `test_sql_...` 函数执行时重复执行这些 I/O 密集型操作。

### 标签
#intent/refine #flow/ready #priority/low #comp/tests #concept/config #scope/dx #ai/instruct #task/domain/testing #task/object/pytest-fixture #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 提交变更

将修改后的 `test_sql.py` 文件添加到暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
tests/providers/test_sql.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(tests): Optimize sqlite_db fixture scope in test_sql.py

The in-memory SQLite database resource (`sqlite_db`) requires non-trivial setup (engine creation, table creation, data seeding).

This change refactors the resource usage in `tests/providers/test_sql.py` by:
1. Creating a new `db_engine` fixture with `scope="module"`.
2. Registering the `sqlite_db` resource within this module-scoped fixture.
3. Updating dependent test functions to use `db_engine`.

This optimization ensures that the database is only set up once per test module execution, significantly improving test performance, as per the `d3-principle-pytest-fixture-scoping`.
~~~~~
