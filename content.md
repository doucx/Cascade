你的分析完全正确。

遵循 `d3-principle-pytest-fixture-scoping` 原则来优化涉及 I/O 的 Fixture 是优秀的工程实践，即使在当前规模下速度不是瓶颈。这种主动优化有助于保持测试套件的健康和高效。

你的建议是将 `sqlite_db` 资源提升为模块作用域的 Pytest Fixture，这是正确的方向。我的实现方案会稍微调整一下，以获得最佳效果：我将创建一个 `db_engine` Fixture，它在模块级别（`module` scope）初始化一个 `Engine` 实例并预先注册 `sqlite_db` 资源。这样，每个测试函数就可以直接使用一个准备就绪的、带有数据库资源的 `Engine`，从而将性能开销降至最低。

我将生成一个计划来实现这一优化。

## [WIP] refactor(tests): 优化 SQL 测试中的 Fixture 作用域

### 用户需求
根据 `d3-principle-pytest-fixture-scoping` 原则，将 `tests/integration/test_sql.py` 中的 `sqlite_db` 资源相关的设置提升为模块作用域的 Pytest Fixture，以优化测试性能并遵循最佳实践。

### 评论
这是一个应用架构原则来改善测试套件质量的绝佳示例。通过将 `Engine` 的设置和资源注册集中到一个模块级别的 Fixture 中，我们不仅减少了每个测试用例不必要的重复设置开销，还使测试代码本身变得更加简洁和意图明确。同时，特意保持 `test_sql_missing_resource` 测试的独立性是正确的，因为它需要一个“干净”的、未注册任何资源的 `Engine` 实例来验证其特定的失败场景。

### 目标
1.  在 `tests/integration/test_sql.py` 文件中，创建一个名为 `db_engine` 的、作用域为 `module` 的 Pytest Fixture。
2.  该 Fixture 将负责创建 `cs.Engine` 实例，并为其注册 `sqlite_db` 资源。
3.  重构 `test_sql_query_success` 和 `test_sql_with_params` 测试函数，使其依赖并使用 `db_engine` Fixture。
4.  确保 `test_sql_missing_resource` 测试函数维持原状，不使用新的 Fixture。

### 基本原理
遵循 `d3-principle-pytest-fixture-scoping` 原则，对于那些创建成本较高且在测试过程中不会被修改的只读 Fixture，应提升其作用域。在本例中，一个带有已注册的数据库资源的 `Engine` 实例完全符合这个条件。通过将其作用域提升至 `module`，我们可以确保在整个测试文件的执行过程中，相关的 `Engine` 初始化和资源注册操作只执行一次，从而显著提高测试套件的运行效率。

### 标签
#intent/refine #flow/ready #priority/low #comp/tests #concept/config #scope/dx #ai/instruct #task/domain/testing #task/object/pytest-fixture #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重构 SQL 集成测试

我们将使用 `write_file` 来更新整个 `test_sql.py` 文件。这包括引入新的模块级 `db_engine` Fixture，并更新依赖它的测试用例。

~~~~~act
write_file
tests/providers/test_sql.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from sqlalchemy import create_engine

# Skip if sqlalchemy missing
pytest.importorskip("sqlalchemy")


@cs.resource
def sqlite_db():
    # Setup an in-memory SQLite database
    engine = create_engine("sqlite:///:memory:")

    # Create a table
    with engine.connect() as conn:
        conn.execute(
            cs.providers.sql.text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"
            )
        )
        conn.execute(cs.providers.sql.text("INSERT INTO users (name) VALUES ('Alice')"))
        conn.execute(cs.providers.sql.text("INSERT INTO users (name) VALUES ('Bob')"))
        conn.commit()

    yield engine

    engine.dispose()


@pytest.fixture(scope="module")
def db_engine():
    """Provides a Cascade Engine with the sqlite_db resource pre-registered."""
    engine = cs.Engine()
    engine.register(sqlite_db)
    return engine


@pytest.mark.asyncio
async def test_sql_query_success(db_engine):
    """Test a basic SELECT query."""

    # Define a workflow using the 'sqlite_db' resource
    users = cs.sql("SELECT * FROM users ORDER BY name", db="sqlite_db")

    result = await db_engine.run(users)

    assert len(result) == 2
    assert result[0]["name"] == "Alice"
    assert result[1]["name"] == "Bob"


@pytest.mark.asyncio
async def test_sql_with_params(db_engine):
    """Test a query with parameters."""

    target = cs.sql(
        "SELECT * FROM users WHERE name = :name", db="sqlite_db", params={"name": "Bob"}
    )

    result = await db_engine.run(target)

    assert len(result) == 1
    assert result[0]["name"] == "Bob"


@pytest.mark.asyncio
async def test_sql_missing_resource():
    """Test failure when the specified DB resource is not registered."""

    target = cs.sql("SELECT 1", db="non_existent_db")

    engine = cs.Engine()
    # We don't register anything

    # Should fail during execution when trying to resolve the Inject object
    # Or during setup if we scan correctly?
    # With the new scanning logic, it should fail at setup time!

    with pytest.raises(NameError, match="not registered"):
        await engine.run(target)
~~~~~
