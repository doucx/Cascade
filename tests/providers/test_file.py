import pytest
import cascade as cs
import json
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


# --- Fixtures ---


@pytest.fixture
def dummy_file(tmp_path):
    """Creates a temporary file with known JSON content."""
    p = tmp_path / "test_data.json"
    content = {"status": "ok", "value": 123}
    p.write_text(json.dumps(content))
    return str(p)


@pytest.fixture
def binary_file(tmp_path):
    """Creates a temporary file with binary content."""
    p = tmp_path / "binary_data.bin"
    content = b"\x01\x02\x03\x04"
    p.write_bytes(content)
    return str(p)


# --- Tests ---


@pytest.mark.asyncio
async def test_file_read_text_success(dummy_file):
    """Tests reading a file as text using cs.file."""

    # cs.file returns the factory, read_text() returns the LazyResult
    read_result = cs.file(dummy_file).read_text()

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_result)

    assert "status" in result
    assert "ok" in result


@pytest.mark.asyncio
async def test_file_read_bytes_success(binary_file):
    """Tests reading a file as bytes."""

    read_result = cs.file(binary_file).read_bytes()

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_result)

    assert result == b"\x01\x02\x03\x04"


@pytest.mark.asyncio
async def test_file_exists_true(dummy_file):
    """Tests checking existence for an existing file."""

    exist_result = cs.file(dummy_file).exists()

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(exist_result)

    assert result is True


@pytest.mark.asyncio
async def test_file_exists_false(tmp_path):
    """Tests checking existence for a non-existing file."""

    path = str(tmp_path / "non_existent.txt")
    exist_result = cs.file(path).exists()

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(exist_result)

    assert result is False


@pytest.mark.asyncio
async def test_file_json_parsing(dummy_file):
    """Tests the chained .json() method."""

    json_result = cs.file(dummy_file).json()

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(json_result)

    assert isinstance(result, dict)
    assert result["status"] == "ok"
    assert result["value"] == 123


@pytest.mark.asyncio
async def test_file_dynamic_path_dependency(tmp_path):
    """Tests dependency where the file path comes from an upstream task."""

    # Upstream task generates the path string
    @cs.task
    def generate_path() -> str:
        p = tmp_path / "dynamic.txt"
        p.write_text("dynamic content")
        return str(p)

    path_result = generate_path()

    # cs.file receives the LazyResult path
    read_result = cs.file(path_result).read_text()

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_result)

    assert result == "dynamic content"
