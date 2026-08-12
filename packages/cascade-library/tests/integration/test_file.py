import json

import cascade.sdk as cs
import pytest

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
async def test_file_read_text_success(engine, dummy_file):
    read_result = cs.read.text(dummy_file)

    result = await engine.run(read_result)

    assert "status" in result
    assert "ok" in result


@pytest.mark.asyncio
async def test_file_read_bytes_success(engine, binary_file):
    read_result = cs.read.bytes(binary_file)

    result = await engine.run(read_result)

    assert result == b"\x01\x02\x03\x04"


@pytest.mark.asyncio
async def test_file_exists_true(engine, dummy_file):
    exist_result = cs.fs.exists(dummy_file)

    result = await engine.run(exist_result)

    assert result is True


@pytest.mark.asyncio
async def test_file_exists_false(engine, tmp_path):
    path = str(tmp_path / "non_existent.txt")
    exist_result = cs.fs.exists(path)

    result = await engine.run(exist_result)

    assert result is False


@pytest.mark.asyncio
async def test_file_json_parsing_composition(engine, dummy_file):
    @cs.task
    def parse_json(text: str):
        return json.loads(text)

    # Chain the new atomic providers
    text_content = cs.read.text(dummy_file)
    json_result = parse_json(text_content)

    result = await engine.run(json_result)

    assert isinstance(result, dict)
    assert result["status"] == "ok"
    assert result["value"] == 123


@pytest.mark.asyncio
async def test_file_dynamic_path_dependency(engine, tmp_path):
    @cs.task
    def generate_path() -> str:
        p = tmp_path / "dynamic.txt"
        p.write_text("dynamic content")
        return str(p)

    path_result = generate_path()
    read_result = cs.read.text(path_result)

    result = await engine.run(read_result)

    assert result == "dynamic content"
