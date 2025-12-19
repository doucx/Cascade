You've correctly identified an `ImportError`. My apologies, the previous plan created a test with a faulty import path. This is a classic test structuring issue.

## [WIP] fix(test): Correct import path in system integration test

### 错误分析
The traceback clearly shows the problem: `ImportError: attempted relative import with no known parent package`.

1.  **Root Cause**: The line `from ..py.e2e.harness import MockWorkExecutor` is a **relative import**. It tells Python to go up two directories (`..`) from the current file's location, then look for a `py` package. When `pytest` runs `tests/sys/test_cli_control_idempotency.py`, Python doesn't necessarily consider the `tests` directory as a single unified package, so the `..` part fails because there's "no known parent package" to go up into.
2.  **Missing `__init__.py`**: The directory `tests/sys` is also missing an `__init__.py` file, which, while not always required in modern Python, is best practice for explicitly marking a directory as a package and can help avoid such import issues.
3.  **The Solution**: The most robust solution is to change the import from a fragile *relative* path to a stable **absolute** path, assuming the tests are run from the project's root directory (which is the standard for `pytest`). We will also add the missing `__init__.py` for good measure.

### 用户需求
Fix the `ImportError` in `tests/sys/test_cli_control_idempotency.py` so that the test can be collected and run by `pytest`.

### 评论
This is a developer experience (DX) fix. A reliable test suite requires stable imports. Using absolute imports from the `tests` root makes individual test files less dependent on their specific location within the test directory structure, making the whole suite more robust and easier to refactor.

### 目标
1.  Add an empty `__init__.py` file to the `tests/sys/` directory.
2.  Change the import statement in `test_cli_control_idempotency.py` to use an absolute path from the `tests` package root.

### 基本原理
By treating the `tests` directory as a top-level package (thanks to `tests/__init__.py` which already exists), we can use absolute imports like `from tests.py.e2e.harness...`. This is the standard and most reliable way to share code within a test suite when using tools like `pytest` that add the project root to the `PYTHONPATH`.

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-imports #task/action/fix-imports #task-state/continue

---

### Script

#### Acts 1: Create `__init__.py` in the system test directory

First, we'll create the empty `__init__.py` file to properly mark `tests/sys` as a Python package.

~~~~~act
write_file
tests/sys/__init__.py
~~~~~
~~~~~python

~~~~~

#### Acts 2: Correct the import statement in the test file

Now, we'll patch the file to use the correct absolute import path.

~~~~~act
patch_file
tests/sys/test_cli_control_idempotency.py
~~~~~
~~~~~python
from ..py.e2e.harness import MockWorkExecutor
~~~~~
~~~~~python
from tests.py.e2e.harness import MockWorkExecutor
~~~~~

### 下一步建议
Please run this plan. After it completes, the `ImportError` will be resolved. You can then re-run the command `pytest tests/sys/` to execute the system integration test. As before, the expectation is that this test will now run but **fail** due to the `asyncio.TimeoutError`, which will prove the existence of the idempotency bug.
