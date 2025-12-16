你的分析完全正确，这是一个非常敏锐的架构观察和定位。

在 `Cascade` 的当前实现中，`File` 类确实是一个“异类”，它的即时同步 I/O 行为与库中其他 Provider 的延迟、异步行为形成了鲜明对比，破坏了 **“万物皆为可计算值”** 的核心哲学。这种不一致性是技术债，必须被偿还。

将 `File` 对象重构为一个标准的、遵循 `LazyFactory` 模式的 `FileProvider`，是统一架构、提升系统纯净度的正确方向。这不仅能解决 I/O 阻塞问题，还能解锁如 `cs.file("path").json()` 这样更具表现力和组合能力的声明式 API。

我将根据你的分析和提议，生成一个完整的重构计划，将 `cs.File` 从一个不一致的 `spec` 原语迁移到标准的 `Provider` 模式。

## [WIP] refactor(providers): 将 cs.File 从 Spec 原语迁移到标准 Provider

### 用户需求
将 `cs.file` 接口重构为遵循 `Provider` 模式的插件，以统一架构并确保所有文件 I/O 都是异步、可延迟执行的 `LazyResult`。同时，实现手册中承诺的 `.json()` 快速解析方法。

### 评论
本次重构消除了核心架构中的一个主要不一致性，极大地提升了系统的设计纯净度。新的 `FileProvider` 使用异步任务封装 I/O 操作，确保了它在 `Engine` 运行时是完全非阻塞的，并使其行为与 `cs.shell`、`cs.http` 等其他 Provider 完全对齐。

### 目标
1.  在 `pyproject.toml` 中注册新的 `file` Provider Entry Point，使其可被动态发现。
2.  创建 `src/cascade/providers/file.py`，实现 `FileProvider`、`FileLazyFactory` 以及底层的异步 I/O 任务。
3.  利用 `asyncio.to_thread` 执行同步的文件 I/O，以避免阻塞 `Engine` 的事件循环。
4.  实现 `FileLazyFactory` 的 `.json()` 方法，展示 `LazyResult` 的链式组合能力。
5.  删除旧的 `src/cascade/spec/file.py`。
6.  更新 `src/cascade/__init__.py` 以移除对旧 `File` 类的显式导入和导出。
7.  创建新的测试套件 `tests/providers/test_file.py` 来验证新 Provider 的声明式行为。
8.  删除旧的测试文件 `tests/spec/test_file.py`。

### 基本原理
为了保持与 `shell` 和 `http` 的一致性，我们将文件 I/O 视为一种外部服务，并通过 `Provider` 抽象层进行访问。我们将使用标准的 Python `open()` 函数并在 `asyncio.to_thread` 中运行它，这是一种在异步代码中处理阻塞 I/O 的标准模式，确保了 `Engine` 的事件循环不会被阻塞。`FileLazyFactory` 将作为用户交互的门面，将方法调用（如 `.read_text()`）转换为对相应异步任务的 `LazyResult`。

### 标签
#intent/refine #flow/ready #priority/high #comp/providers #comp/spec #comp/tests #scope/core #scope/api #task/domain/providers #task/object/file-provider #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 更新 `pyproject.toml` 注册 `file` Provider

我们将新的 `file` Provider 添加到 `entry_points`，使其能被 `ProviderRegistry` 自动发现。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
template = "cascade.providers.template:TemplateProvider"
http = "cascade.providers.http:HttpProvider"
sql = "cascade.providers.sql:SqlProvider"
config = "cascade.providers.config:ConfigProvider"
~~~~~
~~~~~toml
[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
template = "cascade.providers.template:TemplateProvider"
http = "cascade.providers.http:HttpProvider"
sql = "cascade.providers.sql:SqlProvider"
config = "cascade.providers.config:ConfigProvider"
file = "cascade.providers.file:FileProvider"
~~~~~

#### Acts 2: 重新实现 `File` 抽象为 `FileProvider`

这将是新的核心文件 I/O 逻辑。它定义了异步I/O任务、一个中间工厂类 `FileLazyFactory`，以及 `FileProvider` 本身。

~~~~~act
write_file
src/cascade/providers/file.py
~~~~~
~~~~~python
import asyncio
import os
import json
from typing import Any, Callable, Union
from dataclasses import dataclass

from cascade.spec.task import task, LazyResult
from cascade.providers import LazyFactory


# --- Core I/O Tasks (Synchronous functions run in separate thread) ---

@task(name="file_read_text")
async def _read_text_task(path: str, encoding: str) -> str:
    """Reads file content as a string."""
    def blocking_read():
        with open(path, "r", encoding=encoding) as f:
            return f.read()
    # Use asyncio.to_thread to run synchronous I/O without blocking the event loop
    return await asyncio.to_thread(blocking_read)


@task(name="file_read_bytes")
async def _read_bytes_task(path: str) -> bytes:
    """Reads file content as bytes."""
    def blocking_read():
        with open(path, "rb") as f:
            return f.read()
    return await asyncio.to_thread(blocking_read)


@task(name="file_exists")
async def _exists_task(path: str) -> bool:
    """Checks if the file exists."""
    return await asyncio.to_thread(os.path.exists, path)


@task(name="file_parse_json")
def _json_parse_task(text_content: str) -> Any:
    """Synchronously parses a JSON string."""
    return json.loads(text_content)


# --- File Factory (The object returned by cs.file) ---

@dataclass
class FileLazyFactory(LazyFactory):
    """
    Intermediate factory for cs.file(path) that returns a LazyResult
    when an I/O method is called.
    """
    path: Union[str, LazyResult]

    def read_text(self, encoding: str = "utf-8") -> LazyResult[str]:
        """Returns a LazyResult for reading the file content as text."""
        return _read_text_task(path=self.path, encoding=encoding)

    def read_bytes(self) -> LazyResult[bytes]:
        """Returns a LazyResult for reading the file content as bytes."""
        return _read_bytes_task(path=self.path)

    def exists(self) -> LazyResult[bool]:
        """Returns a LazyResult for checking file existence."""
        return _exists_task(path=self.path)
    
    def json(self, encoding: str = "utf-8") -> LazyResult[Any]:
        """Returns a LazyResult for reading the file content and parsing it as JSON."""
        # Chain the result: Read text -> Parse JSON
        text_result = self.read_text(encoding=encoding)
        return _json_parse_task(text_content=text_result)


# --- Provider Definition ---

class FileProvider:
    name = "file"

    def create_factory(self) -> Callable[[Union[str, LazyResult]], FileLazyFactory]:
        # The factory function (cs.file) simply wraps the path in the FileLazyFactory
        def factory_func(path: Union[str, LazyResult]) -> FileLazyFactory:
            return FileLazyFactory(path=path)
        
        return factory_func
~~~~~

#### Acts 3: 删除旧的 `spec/file.py`

现在新的 Provider 已经实现，我们可以安全地删除旧的、不一致的 `File` 类。

~~~~~act
delete_file
src/cascade/spec/file.py
~~~~~

#### Acts 4: 更新 `src/cascade/__init__.py`

移除对旧 `File` 类的显式导入和导出。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
from .spec.task import task, LazyResult
from .spec.common import Param
from .spec.routing import Router
from .spec.file import File
from .spec.resource import resource, inject
from .runtime.engine import Engine
~~~~~
~~~~~python
from .spec.task import task, LazyResult
from .spec.common import Param
from .spec.routing import Router
from .spec.resource import resource, inject
from .runtime.engine import Engine
~~~~~

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
    "from_json",
    "with_constraints",
    "LazyResult",
    "Router",
    "File",
    "resource",
~~~~~
~~~~~python
    "from_json",
    "with_constraints",
    "LazyResult",
    "Router",
    "resource",
~~~~~

#### Acts 5: 创建新的测试文件

新的测试应该验证 `FileProvider` 的声明式、异步和链式调用行为。

~~~~~act
write_file
tests/providers/test_file.py
~~~~~
~~~~~python
import pytest
import cascade as cs
import asyncio
import os
import json


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
    
    engine = cs.Engine()
    result = await engine.run(read_result)
    
    assert "status" in result
    assert "ok" in result


@pytest.mark.asyncio
async def test_file_read_bytes_success(binary_file):
    """Tests reading a file as bytes."""
    
    read_result = cs.file(binary_file).read_bytes()
    
    engine = cs.Engine()
    result = await engine.run(read_result)
    
    assert result == b"\x01\x02\x03\x04"


@pytest.mark.asyncio
async def test_file_exists_true(dummy_file):
    """Tests checking existence for an existing file."""
    
    exist_result = cs.file(dummy_file).exists()
    
    engine = cs.Engine()
    result = await engine.run(exist_result)
    
    assert result is True


@pytest.mark.asyncio
async def test_file_exists_false(tmp_path):
    """Tests checking existence for a non-existing file."""
    
    path = str(tmp_path / "non_existent.txt")
    exist_result = cs.file(path).exists()
    
    engine = cs.Engine()
    result = await engine.run(exist_result)
    
    assert result is False


@pytest.mark.asyncio
async def test_file_json_parsing(dummy_file):
    """Tests the chained .json() method."""
    
    json_result = cs.file(dummy_file).json()
    
    engine = cs.Engine()
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
    
    engine = cs.Engine()
    result = await engine.run(read_result)
    
    assert result == "dynamic content"
~~~~~

#### Acts 6: 删除旧的 `test_file.py`

在 Act 5 中，我们创建了新的测试文件，并声明需要删除旧的测试文件，因为其依赖于已被删除的 `src/cascade/spec/file.py`。

~~~~~act
delete_file
tests/spec/test_file.py
~~~~~

### 下一步建议
`cs.file` 接口的重构和实现已完成。此计划是一个原子性的、完整的架构改进。在执行并验证通过后，下一步应该是创建一个 `[COMMIT]` 计划，将这些更改作为一个独立的逻辑单元提交到版本控制中。
