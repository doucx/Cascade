简要回答
好的，我们已经确认了 `cs.file` 的所有引用点。现在，我将执行一个计划来彻底移除旧的 `cs.file` API，并迁移其测试用例以使用新的原子化 IO Provider。

## [WIP] refactor(providers): 废弃 cs.file 并迁移到原子化 IO Provider

### 用户需求
根据路线图，需要彻底移除旧的、不一致的 `cs.file(...)` API，并更新所有代码（主要是测试）以使用新引入的 `cs.read.text(...)`、`cs.fs.exists(...)` 等原子化 Provider。

### 评论
这是一个对 API 一致性和开发者体验 (DX) 的重要重构。通过移除 `cs.file`，我们消除了一个设计上的“孤岛”，使所有 Provider 都遵循“一次调用，一个原子操作”的原则。

### 目标
1.  删除旧的 Provider 实现文件 `src/cascade/providers/file.py`。
2.  从 `pyproject.toml` 中移除 `cs.file` 的入口点注册。
3.  重写 `tests/providers/test_file.py`，将其中的所有测试用例都迁移到使用新的 `cs.read.*`, `cs.write.*`, `cs.fs.*` API。

### 基本原理
由于 `rg` 的输出确认了旧 API 的使用范围仅限于其自身的实现和测试文件，我们可以安全地执行一次性的“删除并替换”操作。对测试文件 `tests/providers/test_file.py` 的重写将确保在移除旧功能的同时，我们保留了对核心 IO 操作的测试覆盖率。

### 标签
#intent/refine #flow/ready #priority/high #comp/core #scope/api #scope/dx #ai/instruct #task/domain/core #task/object/provider-deprecation #task/action/refactoring #task/state/continue

---

### Script

#### Acts 1: 移除旧的 Provider 实现
我们将删除 `file.py` 文件并从 `pyproject.toml` 中取消其注册。

~~~~~act
delete_file
src/cascade/providers/file.py
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
sql = "cascade.providers.sql:SqlProvider"
file = "cascade.providers.file:FileProvider"
load_yaml = "cascade.providers.config:YamlLoaderProvider"
lookup = "cascade.providers.config:LookupProvider"
~~~~~
~~~~~toml
sql = "cascade.providers.sql:SqlProvider"
load_yaml = "cascade.providers.config:YamlLoaderProvider"
lookup = "cascade.providers.config:LookupProvider"
~~~~~

#### Acts 2: 迁移测试用例
我们将重写 `tests/providers/test_file.py` 以适配新的原子化 API。

~~~~~act
write_file
tests/providers/test_file.py
~~~~~
~~~~~python
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
    """Tests reading a file as text using the new cs.read.text provider."""
    read_result = cs.read.text(dummy_file)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_result)

    assert "status" in result
    assert "ok" in result


@pytest.mark.asyncio
async def test_file_read_bytes_success(binary_file):
    """Tests reading a file as bytes using cs.read.bytes."""
    read_result = cs.read.bytes(binary_file)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_result)

    assert result == b"\x01\x02\x03\x04"


@pytest.mark.asyncio
async def test_file_exists_true(dummy_file):
    """Tests checking existence for an existing file using cs.fs.exists."""
    exist_result = cs.fs.exists(dummy_file)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(exist_result)

    assert result is True


@pytest.mark.asyncio
async def test_file_exists_false(tmp_path):
    """Tests checking existence for a non-existing file using cs.fs.exists."""
    path = str(tmp_path / "non_existent.txt")
    exist_result = cs.fs.exists(path)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(exist_result)

    assert result is False


@pytest.mark.asyncio
async def test_file_json_parsing_composition(dummy_file):
    """Tests composing read_text with a JSON parsing task."""
    @cs.task
    def parse_json(text: str):
        return json.loads(text)

    # Chain the new atomic providers
    text_content = cs.read.text(dummy_file)
    json_result = parse_json(text_content)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(json_result)

    assert isinstance(result, dict)
    assert result["status"] == "ok"
    assert result["value"] == 123


@pytest.mark.asyncio
async def test_file_dynamic_path_dependency(tmp_path):
    """Tests dependency where the file path comes from an upstream task."""
    @cs.task
    def generate_path() -> str:
        p = tmp_path / "dynamic.txt"
        p.write_text("dynamic content")
        return str(p)

    path_result = generate_path()
    read_result = cs.read.text(path_result)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_result)

    assert result == "dynamic content"
~~~~~

### 下一步建议
测试通过后，我们将开始执行路线图的第三部分：**明确化控制流行为**，首先从实现级联跳过逻辑开始。
