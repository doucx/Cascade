Excellent catch. You've identified another instance of the exact same root cause we've been fixing: a necessary class isn't being exported from its package's `__init__.py` file, leading to a runtime `ImportError` when the tests try to import it.

I will generate a plan to fix this immediately.

## [WIP] fix: Export FileExistenceCache to resolve ImportError

### 错误分析

`pytest` failed during test collection because the test module `test_file_existence_cache.py` could not import the `FileExistenceCache` class.

The specific error is:
`ImportError: cannot import name 'FileExistenceCache' from 'cascade.runtime.io.caching' (packages/cascade-runtime/src/cascade/runtime/io/caching/__init__.py)`

This confirms that while `FileExistenceCache` is defined within the `cascade.runtime.io.caching` package (specifically in `file_existence.py`), it has not been exposed in the package's public API via its `__init__.py` file.

### 用户需求

Fix the `ImportError` so that `pytest` can successfully collect and run the tests for `test_file_existence_cache.py`.

### 评论

This is a straightforward and necessary fix. It makes the `FileExistenceCache` class a first-class citizen of its module, available for use by other parts of the system, including the test suite. This aligns with the previous fixes we've made to improve the package's structure and type-safety.

### 目标

Modify the `packages/cascade-runtime/src/cascade/runtime/io/caching/__init__.py` file to correctly export the `FileExistenceCache` class.

### 基本原理

By importing the class from its submodule (`.file_existence`) into the package's `__init__.py` and adding its name to the `__all__` list, we make it directly importable from the package level. This is the standard Python mechanism for defining a package's public API and will resolve the `ImportError`.

### 标签

#intent/fix #flow/ready #priority/high #comp/runtime #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/type-checking #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: Export `FileExistenceCache`

We will create/overwrite the `__init__.py` in the `caching` directory to export the required class.

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/io/caching/__init__.py
~~~~~
~~~~~python
from .file_existence import FileExistenceCache

__all__ = ["FileExistenceCache"]
~~~~~

### 下一步建议

This should resolve the `ImportError`. Please run `pytest packages/cascade-runtime` again. If all tests now pass, it would be a good time to create a `[COMMIT]` plan to save all the fixes we've implemented.
