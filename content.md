Excellent catch. You've correctly identified a regression. This is a classic and subtle side-effect of introducing threading, and it's a perfect example of why comprehensive test suites are critical.

## [WIP] fix(test): Correct fixture scope to prevent SQLite threading errors

### 错误分析
The root cause is a **threading conflict** with SQLite's in-memory database, which was exposed by our change to `LocalExecutor`.

1.  **The Cause of the Error**: The key error message is `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`.
2.  **The Lifecycle**:
    *   The `db_engine` fixture in `test_sql.py` has `scope="module"`. This means it is created **once** for the entire test file, in the main `pytest` thread (let's call it Thread A).
    *   When it's created, the `@cs.resource def sqlite_db()` is registered. This resource provider function, when called, creates an **in-memory** SQLite database.
    *   When `await db_engine.run(users)` is called in the test, the `cs.sql` task, being a synchronous task, is now offloaded by our new `LocalExecutor` to a worker thread (Thread B).
    *   Inside Thread B, the `cs.sql` task injects and uses the `sqlite_db` resource. The first time this happens, the resource provider runs *in Thread B*, creating the in-memory database and the `users` table.
    *   However, `sqlalchemy`'s connection pool, created by `create_engine` in the fixture setup, might hold a connection that was implicitly created back in Thread A. When the task in Thread B tries to use a connection object created in Thread A, SQLite's strict thread-safety rules are violated.
3.  **Why `no such table: users`?**: For in-memory SQLite databases, when a connection is used from a different thread, it often behaves as if it's connecting to a *brand new, empty* in-memory database. So from the perspective of the worker thread (Thread B), the `users` table created during the fixture setup (in Thread A) simply does not exist.

### 用户需求
The user needs to fix the `test_sql.py` failures without removing the new thread offloading feature. The fix must address the underlying resource lifecycle and threading issue.

### 评论
This regression highlights the importance of managing resource lifecycles, especially for thread-sensitive resources like SQLite connections. Our fix will align the resource's scope with its usage scope, which is a core principle of robust testing and dependency injection.

### 目标
1.  Modify `tests/sdk/providers/test_sql.py`.
2.  Change the scope of the `db_engine` pytest fixture from `module` to the default `function` scope.

### 基本原理
By changing `@pytest.fixture(scope="module")` to `@pytest.fixture`, we ensure that a fresh `db_engine` is created for *each test function*. This means that the `sqlite_db` resource provider will be called within the context of a single test run. Crucially, the database connection will be established and used within the same worker thread that our `LocalExecutor` dispatches the `cs.sql` task to, thereby satisfying SQLite's same-thread constraint.

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #comp/engine #concept/executor #scope/dx #ai/instruct #task/domain/testing #task/object/test-fixture #task/action/scope-correction #task-state/continue

---

### Script

#### Acts 1: Correct the scope of the `db_engine` fixture

I will change the fixture scope to ensure resource creation and usage happen in the same thread context.

~~~~~act
patch_file
tests/sdk/providers/test_sql.py
~~~~~
~~~~~python
@pytest.fixture(scope="module")
def db_engine():
    """Provides a Cascade Engine with the sqlite_db resource pre-registered."""
    engine = cs.Engine(
~~~~~
~~~~~python
@pytest.fixture
def db_engine():
    """Provides a Cascade Engine with the sqlite_db resource pre-registered."""
    engine = cs.Engine(
~~~~~

### 下一步建议
The fixture scope has been corrected. Please run the full test suite again.

I expect that the `test_sql.py` failures will now be resolved, and our new tests (`test_offloading.py`, `test_executor_modes.py`) will continue to pass. Once all tests are green, we will have a stable state ready for a final commit.
