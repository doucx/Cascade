好的，根据执行计划，我将生成实现 `cs.File` 的计划。这是一个自包含的功能模块，旨在提供更优雅的文件系统交互方式。

## [WIP] feat: 引入文件系统一等公民 `cs.File`

### 用户需求
在 `Cascade` 核心规范中引入 `File` 类。该类应作为文件路径的声明式包装器，提供便捷的 I/O 方法（如 `read_text`, `write_text`），并能作为普通对象在任务间传递，从而使文件依赖关系更加明确。

### 评论
这是一个提升开发者体验 (DX) 的重要功能。它避免了用户在任务中反复编写 `with open(...)` 的样板代码，并且通过类型提示 (`f: cs.File`) 让任务的副作用（读取或写入文件）变得显式且自文档化。

### 目标
1.  创建 `src/cascade/spec/file.py`，实现 `File` 类及其 I/O 方法。
2.  在 `src/cascade/__init__.py` 中导出 `File` 类。
3.  创建 `tests/test_spec_file.py`，验证 `File` 类的功能及其在 Task 中的集成。

### 基本原理
`File` 类被设计为一个轻量级的包装器。它不改变 `Engine` 或 `Graph` 的核心逻辑（`Engine` 将其视为普通对象），但通过封装底层的 `open` 和 `os.path` 操作，为用户提供了一致且便利的 API。

### 标签
#intent/build #flow/ready #priority/medium #comp/spec #scope/core #ai/instruct #task/domain/core #task/object/file-wrapper #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 实现 `File` 类规范

创建包含读写和存在性检查逻辑的 `File` 类。

~~~~~act
write_file
src/cascade/spec/file.py
~~~~~
~~~~~python
import os
from typing import Union

class File:
    """
    A declarative wrapper for a file system path.
    
    It provides convenience methods for I/O operations and can be used
    to explicitly declare file dependencies in task signatures.
    """
    def __init__(self, path: Union[str, "File"]):
        self.path = str(path)

    def read_text(self, encoding="utf-8") -> str:
        """Reads the file content as a string."""
        with open(self.path, "r", encoding=encoding) as f:
            return f.read()

    def read_bytes(self) -> bytes:
        """Reads the file content as bytes."""
        with open(self.path, "rb") as f:
            return f.read()

    def write_text(self, data: str, encoding="utf-8") -> None:
        """
        Writes a string to the file. 
        Automatically creates parent directories if they don't exist.
        """
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "w", encoding=encoding) as f:
            f.write(data)

    def write_bytes(self, data: bytes) -> None:
        """
        Writes bytes to the file.
        Automatically creates parent directories if they don't exist.
        """
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "wb") as f:
            f.write(data)

    def exists(self) -> bool:
        """Checks if the file exists."""
        return os.path.exists(self.path)

    def __str__(self) -> str:
        return self.path

    def __repr__(self) -> str:
        return f"File('{self.path}')"
~~~~~

#### Acts 2: 公开 API

将 `File` 类添加到顶层包中，使其可以通过 `cascade.File` 访问。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
from .spec.task import task, Param, LazyResult
from .spec.resource import resource, inject
from .runtime.engine import Engine
~~~~~
~~~~~python
from .spec.task import task, Param, LazyResult
from .spec.file import File
from .spec.resource import resource, inject
from .runtime.engine import Engine
~~~~~

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
__all__ = [
    "task",
    "Param",
    "run",
    "dry_run",
    "LazyResult",
    "resource",
    "inject",
    "Engine",
    "override_resource",
    "shell",
]
~~~~~
~~~~~python
__all__ = [
    "task",
    "Param",
    "run",
    "dry_run",
    "LazyResult",
    "File",
    "resource",
    "inject",
    "Engine",
    "override_resource",
    "shell",
]
~~~~~

#### Acts 3: 添加测试

创建一个新的测试文件来验证 `File` 类的行为及其在工作流中的使用。

~~~~~act
write_file
tests/test_spec_file.py
~~~~~
~~~~~python
import os
import cascade as cs
from cascade.spec.file import File

def test_file_read_write_text(tmp_path):
    p = tmp_path / "hello.txt"
    f = File(str(p))

    # Test Write (should create parent dir if mostly empty, but here tmp_path exists)
    f.write_text("Hello World")
    assert p.read_text() == "Hello World"

    # Test Read
    assert f.read_text() == "Hello World"

def test_file_auto_makedirs(tmp_path):
    # Test that write operations create nested directories
    nested_path = tmp_path / "sub" / "dir" / "data.txt"
    f = File(str(nested_path))
    
    f.write_text("nested content")
    
    assert nested_path.exists()
    assert f.read_text() == "nested content"

def test_file_read_write_bytes(tmp_path):
    p = tmp_path / "data.bin"
    f = File(str(p))

    data = b"\x00\x01\x02"
    f.write_bytes(data)
    assert p.read_bytes() == data
    assert f.read_bytes() == data

def test_file_exists(tmp_path):
    p = tmp_path / "exist.txt"
    f = File(str(p))
    assert not f.exists()
    
    p.touch()
    assert f.exists()

def test_file_str_repr(tmp_path):
    f = File("my/path")
    assert str(f) == "my/path"
    assert repr(f) == "File('my/path')"
    
def test_file_integration_with_task(tmp_path):
    """
    Ensures that File objects can be passed through tasks seamlessly.
    """
    target = tmp_path / "config.json"
    target.write_text('{"foo": "bar"}')
    
    @cs.task
    def read_config(f: File) -> str:
        # Verify we received a File object and can use it
        assert isinstance(f, File)
        return f.read_text()
        
    file_obj = File(str(target))
    # Pass File object as argument
    task_res = read_config(file_obj)
    
    res = cs.run(task_res)
    assert res == '{"foo": "bar"}'
~~~~~

### 下一步建议
执行此计划后，我们将拥有功能完备的 `cs.File` 类。
接下来的逻辑步骤是实现执行计划中的第三项：**条件工作流 (`.run_if()`)**。这将大大增强 Cascade 处理复杂逻辑的能力。
