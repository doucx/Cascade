这是一个严重的并发回归错误：`sqlite3.OperationalError: no such table: users`，伴随着 `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`。

原因在于我们将所有的同步任务（包括 SQL 操作）都移到了线程池中执行 (`loop.run_in_executor`)。
而测试代码中的 `sqlite_db` 资源是在**主线程**（或 `asyncio` 的事件循环线程）中创建的 `sqlite:///:memory:` 内存数据库。

SQLite 的内存数据库是**连接级**的，如果在一个线程创建连接并写入数据，而在另一个线程（我们的线程池）中尝试查询，不仅会因为连接对象不能跨线程共享而报错（`ProgrammingError`），即使能共享，内存数据库的数据对于新连接也是不可见的。

**为什么之前没报错？**
之前 `LocalExecutor` 是在主线程同步执行的，所以创建 DB 和查询 DB 都在同一个线程，自然没问题。

**为什么现在报错？**
`LocalExecutor` 现在将同步任务分派到了 `_blocking_executor` 线程池中。`cs.sql` 是一个同步任务，因此在子线程中运行。它尝试使用主线程注入的 `sqlalchemy.engine` 对象。虽然 SQLAlchemy 的 Engine 是线程安全的，但其底层的 SQLite 连接（特别是内存模式）对线程非常敏感。

修复策略

我们不能回滚“线程卸载”这一核心特性，因为它对整体架构至关重要。
问题出在测试代码 `test_sql.py` 的编写方式上，它假设了单线程执行模型。

要修复这个测试，我们需要让 `sqlite_db` 资源能够适应多线程环境。对于 SQLite 内存数据库，我们可以使用 `StaticPool` 来确保即使在多线程环境下，所有连接都共享同一个底层连接，从而共享内存中的数据。

我们需要修改 `test_sql.py`，在 `create_engine` 时指定 `poolclass=StaticPool`，并设置 `connect_args={"check_same_thread": False}` 以允许跨线程使用连接。

## [WIP] fix(tests): 更新 SQL 测试以适配多线程执行器

### 用户需求
修复因引入线程池执行器而导致的 `test_sql.py` 失败。确保测试环境中的 SQLite 内存数据库能够正确处理跨线程访问，从而验证 SQL 提供者在新的异步/多线程架构下的正确性。

### 评论
这是一个经典的“升级架构导致旧测试假设失效”的案例。我们的架构升级（线程隔离）是正确的，但测试用例依赖了旧架构的副作用（单线程）。修复测试代码使其兼容多线程环境是正确的做法。

### 目标
修改 `tests/sdk/providers/test_sql.py`。
1.  引入 `sqlalchemy.pool.StaticPool`。
2.  在 `create_engine` 调用中添加 `poolclass=StaticPool`。
3.  添加 `connect_args={"check_same_thread": False}` 以禁用 SQLite 的线程检查。

### 基本原理
`StaticPool` 保证了对于内存数据库，无论多少次 `connect()` 调用，都返回同一个连接实例。这对于内存数据库至关重要，否则每次连接看到的是一个全新的、空的数据库。`check_same_thread=False` 则允许这个连接对象被不同的线程（主线程创建，工作线程查询）使用。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/sql-test #task/action/fix-concurrency-issue #task/state/continue

---

### Script

#### Acts 1: 修复 test_sql.py 的连接配置

~~~~~act
patch_file
tests/sdk/providers/test_sql.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from sqlalchemy import create_engine

from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver

# Skip if sqlalchemy missing
pytest.importorskip("sqlalchemy")


@cs.resource
def sqlite_db():
    # Setup an in-memory SQLite database
    engine = create_engine("sqlite:///:memory:")

    # Create a table
    with engine.connect() as conn:
~~~~~
~~~~~python
import pytest
import cascade as cs
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver

# Skip if sqlalchemy missing
pytest.importorskip("sqlalchemy")


@cs.resource
def sqlite_db():
    # Setup an in-memory SQLite database.
    # Because tasks now run in a separate thread pool, we must ensure:
    # 1. We share the same connection (StaticPool) so data persists across tasks.
    # 2. We disable thread checking (check_same_thread=False) so the connection created
    #    here can be used by the worker threads.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create a table
    with engine.connect() as conn:
~~~~~

### 下一步建议
请再次运行测试。这应该能解决 `OperationalError: no such table: users` 错误。

一旦这个回归错误被修复，且 `tests/engine/e2e/test_executor_modes.py` 依然通过，我们就可以自信地提交包含线程池隔离特性的代码了。
