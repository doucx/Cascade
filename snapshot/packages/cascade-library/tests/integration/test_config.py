import cascade.sdk as cs
import pytest

# Skip if PyYAML missing
pytest.importorskip("yaml")

# --- Fixtures ---


@pytest.fixture
def dummy_config_file(tmp_path):
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
async def test_load_yaml_provider(engine, dummy_config_file):
    loaded_data = cs.load_yaml(dummy_config_file)

    result = await engine.run(loaded_data)

    assert isinstance(result, dict)
    assert result["project"]["name"] == "Cascade"


@pytest.mark.asyncio
async def test_lookup_provider_basic(engine, dummy_config_file):
    # 1. Explicitly load the config
    config_source = cs.load_yaml(dummy_config_file)

    # 2. Explicitly look up the value
    version = cs.lookup(source=config_source, key="project.version")

    result = await engine.run(version)

    assert result == "1.0.0"


@pytest.mark.asyncio
async def test_lookup_on_static_dict(engine):
    @cs.task
    def provide_dict():
        return {"a": {"b": 10}}

    source = provide_dict()
    value = cs.lookup(source=source, key="a.b")

    result = await engine.run(value)
    assert result == 10


@pytest.mark.asyncio
async def test_lookup_missing_key_raises_error(engine):
    @cs.task
    def provide_dict():
        return {"a": 1}

    source = provide_dict()
    # "b" does not exist in the root dict, should raise KeyError
    missing_value = cs.lookup(source=source, key="b")

    with pytest.raises(KeyError):
        await engine.run(missing_value)


@pytest.mark.asyncio
async def test_lookup_invalid_path_raises_type_error(engine):
    @cs.task
    def provide_dict():
        return {"a": 1}

    source = provide_dict()
    # "a" resolves to 1 (int), which is not a container.
    # Attempting to look up "nonexistent" on it should raise TypeError.
    invalid_lookup = cs.lookup(source=source, key="a.nonexistent")

    with pytest.raises(TypeError, match="Cannot access segment"):
        await engine.run(invalid_lookup)
