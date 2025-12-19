Excellent catch. You've uncovered a bug in the *test's cleanup logic itself*. The `stderr` output is unambiguous: `No such option: --scope`.

This means our test is failing for a trivial reason (incorrect command-line usage) before it even gets to test the actual complex concurrency bug we're hunting. We must fix this to get a real signal from our test.

## [WIP] fix(test): Correct `cs-controller resume` command usage in system test

### 错误分析
The error `No such option: --scope` arises because the `cs-controller resume` command is defined with `scope` as a positional `Argument`, not a named `Option`.

-   **Incorrect Usage (in the test's `finally` block)**: `cs-controller resume --scope global`
-   **Correct Usage (as per `typer` definition)**: `cs-controller resume global`

The test is attempting to pass the scope as an option (`--scope ...`), which the Typer application correctly rejects. This crash in the cleanup phase prevents the test from running to completion and reporting the *real* failure we are looking for (the timeout).

### 用户需求
The system integration test must use the correct command-line syntax for all its operations, including the cleanup phase, so that it can run to completion and provide a valid result regarding the idempotency issue.

### 评论
This is a simple but critical fix. A failing test is only useful if it fails for the right reason. By correcting this syntax error, we ensure that the test's failure (or success) is a true reflection of the `Engine`'s behavior, not a distraction caused by a typo in the test setup.

### 目标
Modify the `finally` block in `tests/sys/test_cli_control_idempotency.py` to use the correct positional argument format for the `cs-controller resume` command.

### 基本原理
The fix involves changing the command string to match the CLI's public interface as defined in its source code. This will resolve the `Typer` parsing error and allow the test to execute its main logic and cleanup procedures correctly.

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/cli-idempotency #task/action/fix-cli-call #task/state/continue

---

### Script

#### Acts 1: Correct the CLI call in the test's cleanup block

We will patch the test file to use the correct command syntax.

~~~~~act
patch_file
tests/sys/test_cli_control_idempotency.py
~~~~~
~~~~~python
        # And clear the constraint for other tests
        await run_cli_command("cs-controller resume --scope global")
~~~~~
~~~~~python
        # And clear the constraint for other tests
        await run_cli_command("cs-controller resume global")
~~~~~

### 下一步建议
Please execute this plan. After the fix is applied, run `pytest tests/sys/` again.

With this syntax error resolved, we now expect the test to fail with the `asyncio.TimeoutError` we originally intended to see. This will be our true "red light", confirming the idempotency bug exists and is ready to be fixed.
