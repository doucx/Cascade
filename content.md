好的，我们将开始实现 `cs.sql` Provider。

为了实现 `cs.sql("SELECT ...", db="my_db")` 这种灵活的 API（即在调用时指定使用的资源，而不是硬编码在任务定义中），我们需要对核心的依赖注入（DI）系统进行一项增强。

目前，`Cascade` 仅支持通过函数签名的默认值（`def t(c=inject("db"))`）进行注入。我们需要升级 `Engine` 和 `Executor`，使其支持将 `cs.inject("db")` 作为参数值直接传递给任务。

以下是实现计划：

## [WIP] feat(provider): 实现 `cs.sql` Provider 并增强动态资源注入能力

### 用户需求
1.  实现 `cs.sql` Provider，允许用户声明式地执行 SQL 查询。
2.  支持动态指定数据库资源，例如 `cs.sql(..., db="analytics_db")`。

### 评论
为了支持动态指定数据库（即 `db` 参数），我们需要增强核心的依赖注入机制。目前的 DI 仅支持静态的函数签名默认值。我们将扩展它，允许在调用任务时显式传递 `Inject` 对象（例如 `task(conn=cs.inject("db_name"))`）。这将赋予 `cs.sql` 极大的灵活性，使其能够复用同一个任务逻辑来连接不同的数据库实例。

### 目标
1.  **核心增强**: 修改 `Engine` 的资源扫描逻辑和 `LocalExecutor` 的参数解析逻辑，支持在 `literal_inputs` 中识别和处理 `Inject` 对象。
2.  **添加依赖**: 将 `sqlalchemy` 添加为可选依赖。
3.  **实现 Provider**: 创建 `src/cascade/providers/sql.py`。
4.  **编写测试**: 验证 SQL 执行及动态资源注入是否正常工作。

### 基本原理
通过将 `Inject` 对象视为一等公民，允许其作为参数传递，我们解耦了“任务定义”与“资源绑定”。`cs.sql` 的工厂函数将接收用户传入的 `db` 字符串名称，将其转换为 `Inject(name)` 对象，然后传递给底层的通用 SQL 任务。

### 标签
#intent/build #intent/refine #flow/ready #priority/high #comp/core #comp/runtime #concept/di #concept/sql #scope/api #ai/instruct #task/domain/ecosystem #task/object/sql-provider #task/action/implementation #task/state/begin #task/status/active

---

### Script

#### Acts 1: 更新项目依赖

添加 `sqlalchemy` 到 `pyproject.toml`。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
template = ["jinja2"]
http = ["aiohttp"]

[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
template = "cascade.providers.template:TemplateProvider"
http = "cascade.providers.http:HttpProvider"
~~~~~
~~~~~toml
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]

[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
template = "cascade.providers.template:TemplateProvider"
http = "cascade.providers.http:HttpProvider"
sql = "cascade.providers.sql:SqlProvider"
~~~~~

#### Acts 2: 安装新依赖

~~~~~act
echo
~~~~~
~~~~~bash
pip install -e .[sql]
~~~~~

#### Acts 3: 增强核心 DI 系统 (Engine & Executor)

我们需要修改两个地方：
1.  `Engine._scan_for_resources`: 不仅要检查函数签名，还要检查节点的 `literal_inputs` 中是否包含 `Inject` 对象，以便在运行前初始化这些资源。
2.  `LocalExecutor.execute`: 在准备参数时，如果发现参数值是 `Inject` 对象，则从 `resource_context` 中解析出实际资源。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def _scan_for_resources(self, plan: list[Node]) -> set[str]:
        """Finds all unique resource names required by the plan."""
        required = set()
        for node in plan:
            # Skip nodes that don't have a callable (e.g., Param nodes)
            if node.callable_obj is None:
                continue

            sig = inspect.signature(node.callable_obj)
            for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                    required.add(param.default.resource_name)
        return required
~~~~~
~~~~~python
    def _scan_for_resources(self, plan: list[Node]) -> set[str]:
        """Finds all unique resource names required by the plan."""
        required = set()
        for node in plan:
            # 1. Check literal inputs for dynamic injection
            for value in node.literal_inputs.values():
                if isinstance(value, Inject):
                    required.add(value.resource_name)

            # 2. Check function signature for static injection
            # Skip nodes that don't have a callable (e.g., Param nodes)
            if node.callable_obj is None:
                continue

            sig = inspect.signature(node.callable_obj)
            for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                    required.add(param.default.resource_name)
        return required
~~~~~

~~~~~act
patch_file
src/cascade/adapters/executors/local.py
~~~~~
~~~~~python
from cascade.graph.model import Graph, Node
from cascade.spec.resource import Inject


class LocalExecutor:
~~~~~
~~~~~python
from cascade.graph.model import Graph, Node
from cascade.spec.resource import Inject


class LocalExecutor:
~~~~~

~~~~~act
patch_file
src/cascade/adapters/executors/local.py
~~~~~
~~~~~python
        # 3. Combine arguments and execute
        # Injected resources take precedence over other inputs
        final_kwargs = {**final_kwargs, **kwargs_from_resources}

        if inspect.iscoroutinefunction(node.callable_obj):
            return await node.callable_obj(*args, **final_kwargs)
        else:
            return node.callable_obj(*args, **final_kwargs)
~~~~~
~~~~~python
        # 3. Resolve explicit Inject objects in arguments
        # This allows passing cs.inject("name") as a value to the task call
        resolved_args = []
        for arg in args:
            if isinstance(arg, Inject):
                if arg.resource_name in resource_context:
                    resolved_args.append(resource_context[arg.resource_name])
                else:
                    raise NameError(f"Resource '{arg.resource_name}' not found in context.")
            else:
                resolved_args.append(arg)
        args = resolved_args

        for key, value in final_kwargs.items():
            if isinstance(value, Inject):
                if value.resource_name in resource_context:
                    final_kwargs[key] = resource_context[value.resource_name]
                else:
                    raise NameError(f"Resource '{value.resource_name}' not found in context.")

        # 4. Combine arguments and execute
        # Injected resources take precedence over other inputs
        final_kwargs = {**final_kwargs, **kwargs_from_resources}

        if inspect.iscoroutinefunction(node.callable_obj):
            return await node.callable_obj(*args, **final_kwargs)
        else:
            return node.callable_obj(*args, **final_kwargs)
~~~~~

#### Acts 4: 实现 `cs.sql` Provider

现在我们可以利用增强后的 DI 系统来实现 `SqlProvider`。

~~~~~act
write_file
src/cascade/providers/sql.py
~~~~~
~~~~~python
from typing import Any, List, Dict, Union, Optional

try:
    import sqlalchemy
    from sqlalchemy import text
except ImportError:
    sqlalchemy = None

from cascade.spec.task import task, LazyResult
from cascade.spec.resource import inject
from cascade.providers import LazyFactory


class SqlProvider:
    name = "sql"

    def create_factory(self) -> LazyFactory:
        if sqlalchemy is None:
            raise ImportError(
                "The 'sqlalchemy' library is required to use the sql provider. "
                "Please install it with: pip install cascade-py[sql]"
            )
        return _sql_factory


def _sql_factory(
    query: str, 
    db: str, 
    params: Optional[Dict[str, Any]] = None
) -> LazyResult[List[Dict[str, Any]]]:
    """
    Factory function exposed as cs.sql.
    
    Args:
        query: The SQL query string.
        db: The name of the resource providing the SQLAlchemy connection/engine.
        params: Optional parameters for the query.
        
    Returns:
        A LazyResult that resolves to the query results.
    """
    # We dynamically inject the resource by converting the 'db' string name
    # into an Inject object and passing it to the 'conn' argument of the task.
    return _sql_task(
        query=query,
        params=params or {},
        conn=inject(db)
    )


@task(name="sql_query")
def _sql_task(
    query: str, 
    params: Dict[str, Any], 
    conn: Any
) -> List[Dict[str, Any]]:
    """
    Executes a SQL query using the provided connection.
    """
    # 'conn' can be an Engine or a Connection.
    # We use a context manager to ensure proper handling.
    
    stmt = text(query)
    
    # Check if it's an Engine or Connection by looking for 'connect' method
    if hasattr(conn, "connect"):
        with conn.connect() as active_conn:
            result = active_conn.execute(stmt, params)
            # Try to commit if available (for transaction handling)
            if hasattr(active_conn, "commit"):
                active_conn.commit()
            
            # Fetch results if it returns rows
            if result.returns_rows:
                # Use mappings() to get dict-like rows
                return [dict(row) for row in result.mappings()]
            return []
    else:
        # Assume it's an already open Connection
        result = conn.execute(stmt, params)
        if hasattr(conn, "commit"):
             conn.commit()
             
        if result.returns_rows:
            return [dict(row) for row in result.mappings()]
        return []
~~~~~

#### Acts 5: 编写测试

测试 `cs.sql` Provider 以及新的动态 DI 功能。

~~~~~act
write_file
tests/test_sql.py
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
        conn.execute(cs.providers.sql.text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(cs.providers.sql.text("INSERT INTO users (name) VALUES ('Alice')"))
        conn.execute(cs.providers.sql.text("INSERT INTO users (name) VALUES ('Bob')"))
        conn.commit()
        
    yield engine
    
    engine.dispose()

@pytest.mark.asyncio
async def test_sql_query_success():
    """Test a basic SELECT query."""
    
    # Define a workflow using the 'sqlite_db' resource
    users = cs.sql("SELECT * FROM users ORDER BY name", db="sqlite_db")
    
    engine = cs.Engine()
    engine.register(sqlite_db)
    
    result = await engine.run(users)
    
    assert len(result) == 2
    assert result[0]["name"] == "Alice"
    assert result[1]["name"] == "Bob"

@pytest.mark.asyncio
async def test_sql_with_params():
    """Test a query with parameters."""
    
    target = cs.sql(
        "SELECT * FROM users WHERE name = :name", 
        db="sqlite_db",
        params={"name": "Bob"}
    )
    
    engine = cs.Engine()
    engine.register(sqlite_db)
    
    result = await engine.run(target)
    
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

### 下一步建议
运行测试以验证实现。

```bash
pytest tests/test_sql.py
```

如果测试通过，我们不仅获得了一个强大的 SQL 工具，还显著提升了核心框架的灵活性（动态 DI）。接下来，我们可以考虑更新文档，或者实现更多的生态工具。
