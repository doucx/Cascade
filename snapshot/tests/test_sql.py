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