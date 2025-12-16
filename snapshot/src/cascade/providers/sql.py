from typing import Any, List, Dict, Optional

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
    query: str, db: str, params: Optional[Dict[str, Any]] = None
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
    return _sql_task(query=query, params=params or {}, conn=inject(db))


@task(name="sql_query")
def _sql_task(query: str, params: Dict[str, Any], conn: Any) -> List[Dict[str, Any]]:
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
