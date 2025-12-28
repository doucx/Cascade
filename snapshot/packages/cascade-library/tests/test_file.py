import pytest
import cascade as cs
import json
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


# --- Fixtures ---


@pytest.fixture
def dummy_file(tmp_path):
    p = tmp_path / "test_data.json"
    content = {"status": "ok", "value": 123}
    p.write_text(json.dumps(content))
    return str(p)


@pytest.fixture
def binary_file(tmp_path):
    p = tmp_path / "binary_data.bin"
    content = b"\x01\x02\x03\x04"
    p.write_bytes(content)
    return str(p)


# --- Tests ---


@pytest.mark.asyncio
async def test_file_read_text_success(dummy_file):
    read_result = cs.read.text(dummy_file)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )
    result = await engine.run(read_result)

    assert "status" in result
    assert "ok" in result


@pytest.mark.asyncio
async def test_file_read_bytes_success(binary_file):
    read_result = cs.read.bytes(binary_file)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )
    result = await engine.run(read_result)

    assert result == b"\x01\x02\x03\x04"


@pytest.mark.asyncio
async def test_file_exists_true(dummy_file):
    exist_result = cs.fs.exists(dummy_file)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )
    result = await engine.run(exist_result)

    assert result is True


@pytest.mark.asyncio
async def test_file_exists_false(tmp_path):
    path = str(tmp_path / "non_existent.txt")
    exist_result = cs.fs.exists(path)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )
    result = await engine.run(exist_result)

    assert result is False


@pytest.mark.asyncio
async def test_file_json_parsing_composition(dummy_file):
    @cs.task
    def parse_json(text: str):
        return json.loads(text)

    # Chain the new atomic providers
    text_content = cs.read.text(dummy_file)
    json_result = parse_json(text_content)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )
    result = await engine.run(json_result)

    assert isinstance(result, dict)
    assert result["status"] == "ok"
    assert result["value"] == 123


@pytest.mark.asyncio
async def test_file_dynamic_path_dependency(tmp_path):
    @cs.task
    def generate_path() -> str:
        p = tmp_path / "dynamic.txt"
        p.write_text("dynamic content")
        return str(p)

    path_result = generate_path()
    read_result = cs.read.text(path_result)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )
    result = await engine.run(read_result)

    assert result == "dynamic content"
