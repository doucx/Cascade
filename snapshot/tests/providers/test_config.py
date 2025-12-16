import pytest
import cascade as cs
import asyncio
from typing import Dict, Any

# Skip if PyYAML missing
pytest.importorskip("yaml")


# --- Resources (Mocking the user-provided config loader) ---

# This resource is what cs.config will inject
@cs.resource
def config_data():
    """A mock config loader resource."""
    # Simulate loading a complex config structure
    config = {
        "project": {
            "name": "Cascade",
            "version": "1.0.0",
            "feature_flags": {"beta": True, "release": False},
        },
        "databases": [
            {"name": "analytics", "url": "url1"},
            {"name": "app_db", "url": "url2"},
        ],
    }
    yield config


# --- Tests ---

@pytest.mark.asyncio
async def test_config_basic_lookup():
    """Test lookup of a simple nested key."""
    # cs.config relies on dynamic loading via __getattr__
    project_name = cs.config("project.name")

    engine = cs.Engine()
    engine.register(config_data)

    result = await engine.run(project_name)
    assert result == "Cascade"


@pytest.mark.asyncio
async def test_config_list_index_lookup():
    """Test lookup that involves indexing into a list."""
    db_name = cs.config("databases.1.name")  # databases[1].name

    engine = cs.Engine()
    engine.register(config_data)

    result = await engine.run(db_name)
    assert result == "app_db"


@pytest.mark.asyncio
async def test_config_dynamic_key_lookup():
    """Test lookup where the key itself comes from an upstream LazyResult."""
    
    # Task that provides the configuration key part
    @cs.task
    def get_version_key():
        return "version"

    # Use cs.template to build the full key path
    version_key_path = cs.template("project.{{ key }}", key=get_version_key())
    
    # Use the dynamic path in cs.config
    version = cs.config(version_key_path)

    engine = cs.Engine()
    engine.register(config_data)

    result = await engine.run(version)
    assert result == "1.0.0"


@pytest.mark.asyncio
async def test_config_missing_key_raises_error():
    """Test that a missing key raises a KeyError."""
    missing_key = cs.config("project.missing_field")

    engine = cs.Engine()
    engine.register(config_data)

    with pytest.raises(KeyError, match="missing_field"):
        await engine.run(missing_key)


@pytest.mark.asyncio
async def test_config_invalid_list_index_raises_error():
    """Test accessing non-existent index or non-dict/list element."""
    invalid_index = cs.config("databases.5")
    
    engine = cs.Engine()
    engine.register(config_data)

    with pytest.raises(KeyError, match="5"):
        await engine.run(invalid_index)
        
    invalid_access_type = cs.config("project.version.sub_key")
    
    with pytest.raises(TypeError, match="Cannot access segment 'sub_key' on non-container type 'str'"):
        await engine.run(invalid_access_type)
