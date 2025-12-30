from typing import Any, List, Dict, Optional

try:
    import sqlalchemy
    from sqlalchemy import text
except ImportError:
    sqlalchemy = None

from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider


class SqlProvider(Provider):
    name = "sql"

    def create_factory(self) -> LazyFactory:
        if sqlalchemy is None:
            raise ImportError(
                "The 'sqlalchemy' library is required to use the sql provider. "
                "Please install it with: pip install cascade-py[sql]"
            )
        # Directly return the Task object, satisfying the LazyFactory protocol.
        return _sql_task


@task(name="sql_query")
def _sql_task(
    query: str,
    conn: Any,  # The connection object is now an explicit, injectable argument
    params: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Executes a SQL query using the provided connection.

    Note on API Change:
    The user-facing API is now more explicit. Instead of cs.sql(db="my_db"),
    the call should be cs.sql(conn=cs.inject("my_db"), ...).
    """
    if sqlalchemy is None:
        # This check is redundant if create_factory is called, but good for safety
        raise ImportError("SQLAlchemy is not installed.")

    # 'conn' can be an Engine or a Connection.
    # We use a context manager to ensure proper handling.
    params = params or {}
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
