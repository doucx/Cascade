import pytest
import cascade as cs

# Skip if PyYAML missing
pytest.importorskip("yaml")

# --- Fixtures ---


@pytest.fixture
def dummy_config_file(tmp_path):
    """Creates a temporary YAML file."""
    p = tmp_path / "config.yml"
    content = """
project:
  name: Cascade
  version: 1.0.0
databases:
  - name: analytics
    url: url1
"""
    p.write_text(content)
    return str(p)


# --- Tests ---


@pytest.mark.asyncio
async def test_load_yaml_provider(dummy_config_file):
    """Tests that cs.load_yaml correctly loads and parses a file."""

    loaded_data = cs.load_yaml(dummy_config_file)

    engine = cs.Engine()
    result = await engine.run(loaded_data)

    assert isinstance(result, dict)
    assert result["project"]["name"] == "Cascade"


@pytest.mark.asyncio
async def test_lookup_provider_basic(dummy_config_file):
    """Tests cs.lookup on a dynamically loaded source."""

    # 1. Explicitly load the config
    config_source = cs.load_yaml(dummy_config_file)

    # 2. Explicitly look up the value
    version = cs.lookup(source=config_source, key="project.version")

    engine = cs.Engine()
    result = await engine.run(version)

    assert result == "1.0.0"


@pytest.mark.asyncio
async def test_lookup_on_static_dict():
    """Tests that cs.lookup can also work on a simple dictionary provided by a task."""

    @cs.task
    def provide_dict():
        return {"a": {"b": 10}}

    source = provide_dict()
    value = cs.lookup(source=source, key="a.b")

    engine = cs.Engine()
    result = await engine.run(value)
    assert result == 10


@pytest.mark.asyncio
async def test_lookup_missing_key_raises_error():
    """Tests that a missing key raises a KeyError."""

    @cs.task
    def provide_dict():
        return {"a": 1}

    source = provide_dict()
    # "b" does not exist in the root dict, should raise KeyError
    missing_value = cs.lookup(source=source, key="b")

    engine = cs.Engine()
    with pytest.raises(KeyError):
        await engine.run(missing_value)


@pytest.mark.asyncio
async def test_lookup_invalid_path_raises_type_error():
    """Tests that lookup on a non-container value raises TypeError."""

    @cs.task
    def provide_dict():
        return {"a": 1}

    source = provide_dict()
    # "a" resolves to 1 (int), which is not a container.
    # Attempting to look up "nonexistent" on it should raise TypeError.
    invalid_lookup = cs.lookup(source=source, key="a.nonexistent")

    engine = cs.Engine()
    with pytest.raises(TypeError, match="Cannot access segment"):
        await engine.run(invalid_lookup)
