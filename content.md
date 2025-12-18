## [WIP] You've hit a classic Python packaging issue. My apologies, in generating the plan to modularize the tests, I overlooked this crucial detail. The error message is perfectly clear and points directly to the cause.

### 错误分析

**`ImportError: attempted relative import with no known parent package`**

This error occurs because Python's import system, and by extension `pytest`, doesn't recognize the `tests/py/e2e/` directory as a package. When the test runner tries to process `from .harness import ...` in `test_e2e_control_plane.py`, it doesn't know what `.` (the current package) refers to.

To fix this, we must explicitly tell Python that the test directories are packages by adding empty `__init__.py` files to them. This allows Python to build a package tree and correctly resolve relative imports.

### 用户需求
The test suite must be correctly structured as a Python package so that tests can be collected and run without import errors.

### 评论
This is a fundamental requirement for a clean and maintainable test suite. Adding `__init__.py` files is a standard Python practice that enables modularity and proper namespacing within the test code, just as it does for production code.

### 目标
Add the necessary `__init__.py` files to the `tests/`, `tests/py/`, and `tests/py/e2e/` directories to transform them into a valid package structure.

### 基本原理
An `__init__.py` file, even if empty, signals to the Python interpreter that the directory containing it should be treated as a package. This enables relative imports between modules within that package and its sub-packages. By adding these files, we allow `test_e2e_control_plane.py` to correctly import from its sibling module, `harness.py`.

### 标签
#intent/fix #intent/tooling #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/package-structure #task/action/fix

---

### Script

#### Acts 1: Create `__init__.py` files to form a valid test package

We will create empty `__init__.py` files in the necessary directories to allow Python's import system to function correctly.

~~~~~act
write_file
tests/__init__.py
~~~~~
~~~~~python

~~~~~

~~~~~act
write_file
tests/py/__init__.py
~~~~~
~~~~~python

~~~~~

~~~~~act
write_file
tests/py/e2e/__init__.py
~~~~~
~~~~~python

~~~~~

### 下一步建议
After applying this plan, the `ImportError` will be resolved. Please run the tests again. They should now be collected successfully, and we can see if there are any remaining logical errors to fix.
