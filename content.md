Excellent catch. You've pinpointed the exact line of failure. The error `assert 1 == 0` is the `pytest` representation of `assert result.exit_code == 0` failing because `result.exit_code` was `1`.

## [WIP] This is a classic and subtle error when testing asynchronous code.

### 错误分析

**根本原因：使用同步 Mock 模拟异步函数 (Sync Mock for Async Function)**

1.  **目标函数是异步的**: The function we are patching, `_publish_pause`, is an `async def` function.
2.  **`asyncio.run()` 的契约**: The `cs-controller pause` command uses `asyncio.run()` to execute it. `asyncio.run()` **must** be given a coroutine object (the result of calling an `async def` function).
3.  **Mock 类型不匹配**: Our test fixture, `mock_publish_pause`, uses `unittest.mock.MagicMock`. `MagicMock` is a **synchronous** mock. When it's called, it returns another `MagicMock` instance, not a coroutine.
4.  **运行时错误**: When `asyncio.run()` receives the synchronous mock object, it immediately fails with a `TypeError` because it wasn't given an awaitable.
5.  **測試失敗**: The `typer.testing.CliRunner` catches this `TypeError` inside the command, causing the command to exit with a non-zero status code (`1`).
6.  **断言失败**: The test's assertion, `assert result.exit_code == 0`, therefore fails, which you correctly identified as `assert 1 == 0`.

### 用户需求
The CLI test for `cs-controller` must correctly mock the asynchronous `_publish_pause` function so the test can pass and properly verify the command's behavior.

### 评论
This is a fantastic example of why understanding the nuances of `asyncio` testing is so important. The fix is simple, but it requires correctly identifying the mismatch between the asynchronous nature of the code and the synchronous nature of the mock being used.

### 目标
Modify the `mock_publish_pause` fixture in `tests/cli-controller/test_controller_cli.py` to use `unittest.mock.AsyncMock` instead of `MagicMock`.

### 基本原理
`unittest.mock.AsyncMock` is the correct tool for this job. It is specifically designed to mock `async` functions. When called, it returns an awaitable, which satisfies the contract of `asyncio.run()`. This will prevent the `TypeError`, allow the command to complete with an exit code of `0`, and enable our test to correctly assert that the function was called with the expected arguments.

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/async-mocking #task/action/fix

---

### Script

#### Acts 1: Fix the Mock Type in `test_controller_cli.py`

We will change the import from `MagicMock` to `AsyncMock` and update the fixture to use the correct mock type.

~~~~~act
patch_file
tests/cli-controller/test_controller_cli.py
~~~~~
~~~~~python
import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from cascade.cli.controller.app import app

runner = CliRunner()

@pytest.fixture
def mock_publish_pause():
    with patch("cascade.cli.controller.app._publish_pause", new_callable=MagicMock) as mock:
        yield mock

def test_pause_command_dispatches_correctly(mock_publish_pause):
    """
    Tests that the 'cs-controller pause' CLI command correctly parses arguments
    and calls the underlying business logic function.
    """
    # Act: Simulate command line invocation
    result = runner.invoke(app, ["pause", "task:my-task", "--ttl", "300"])

    # Assert: The command executed successfully and called our logic function
    assert result.exit_code == 0
    mock_publish_pause.assert_called_once()
    
    # Assert that arguments were parsed and passed correctly
    call_args = mock_publish_pause.call_args
    assert call_args.kwargs['scope'] == 'task:my-task'
    assert call_args.kwargs['ttl'] == 300
    assert call_args.kwargs['hostname'] == 'localhost' # Verifies default value
~~~~~
~~~~~python
import pytest
from typer.testing import CliRunner
from unittest.mock import patch, AsyncMock

from cascade.cli.controller.app import app

runner = CliRunner()

@pytest.fixture
def mock_publish_pause():
    with patch("cascade.cli.controller.app._publish_pause", new_callable=AsyncMock) as mock:
        yield mock

def test_pause_command_dispatches_correctly(mock_publish_pause):
    """
    Tests that the 'cs-controller pause' CLI command correctly parses arguments
    and calls the underlying business logic function.
    """
    # Act: Simulate command line invocation
    result = runner.invoke(app, ["pause", "task:my-task", "--ttl", "300"])

    # Assert: The command executed successfully and called our logic function
    assert result.exit_code == 0
    mock_publish_pause.assert_called_once()
    
    # Assert that arguments were parsed and passed correctly
    call_args = mock_publish_pause.call_args
    assert call_args.kwargs['scope'] == 'task:my-task'
    assert call_args.kwargs['ttl'] == 300
    assert call_args.kwargs['hostname'] == 'localhost' # Verifies default value
~~~~~

### 下一步建议
This should be the final fix required to get the entire test suite to a "green" state. Please run the tests again. Once they all pass, we can create a single `[COMMIT]` plan that incorporates all the testing improvements we've made.
