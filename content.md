好的，我来处理这个测试失败。

这是一个经典的输出流问题。应用程序将它的输出打印到了标准错误（`stderr`），而我们的测试却在标准输出（`stdout`）中寻找结果。

## [WIP] fix: 修正 CLI 测试以断言正确的输出流 (stderr)

### 错误分析
`test_set_and_status_sqlite` 和 `test_resume_sqlite` 两个测试用例失败，断言错误为 `AssertionError: assert '...' in ''`。这表明 `typer.testing.CliRunner` 捕获到的 `result.stdout` 是一个空字符串。

经过分析 `packages/cascade-cli-observer/src/cascade/cli/observer/app.py` 的代码，我发现其 `rich.Console` 实例被硬编码初始化为向 `stderr` 输出：
`console = Console(stderr=True)`

因此，`cs-observer status` 命令的所有可视输出，包括我们期望的约束表格，都被发送到了标准错误流。而测试用例错误地断言了 `result.stdout`，导致了失败。

### 用户需求
修复 `test_e2e_cli_sqlite_backend.py` 中的断言，使其能够正确验证 `cs-observer` 的输出，从而让测试通过。

### 评论
这个修复很简单，但它强调了编写测试时的一个重要细节：必须了解并验证应用程序实际使用的输出流。将 UI 和元信息输出到 `stderr` 是一种常见的 CLI 设计模式，我们的测试应该遵循这一模式。

### 目标
修改 `tests/cli/e2e/test_e2e_cli_sqlite_backend.py` 文件中失败的两个测试用例，将所有对 `result_status.stdout` 的断言更改为对 `result_status.stderr` 的断言。

### 基本原理
我们将使用 `patch_file` 对测试文件进行精确修改。通过将断言目标从 `.stdout` 更改为 `.stderr`，测试将与被测应用的实际行为保持一致，从而能够正确验证其功能。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/cli #task/object/sqlite-connector #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 修正 `test_set_and_status_sqlite` 的断言

我们将 `stdout` 更改为 `stderr`。

~~~~~act
patch_file
tests/cli/e2e/test_e2e_cli_sqlite_backend.py
~~~~~
~~~~~python
    # 2. Check the status
    result_status = runner.invoke(observer_app, ["status", "--backend", "sqlite"])
    assert result_status.exit_code == 0
    assert "global" in result_status.stdout
    assert "rate_limit" in result_status.stdout
    assert "{'rate': '10/s'}" in result_status.stdout
~~~~~
~~~~~python
    # 2. Check the status
    result_status = runner.invoke(observer_app, ["status", "--backend", "sqlite"])
    assert result_status.exit_code == 0
    assert "global" in result_status.stderr
    assert "rate_limit" in result_status.stderr
    assert "{'rate': '10/s'}" in result_status.stderr
~~~~~

#### Acts 2: 修正 `test_resume_sqlite` 的断言

同样，我们将 `stdout` 更改为 `stderr`。

~~~~~act
patch_file
tests/cli/e2e/test_e2e_cli_sqlite_backend.py
~~~~~
~~~~~python
    # 3. Check the status and verify it's gone
    result_status = runner.invoke(observer_app, ["status", "--backend", "sqlite"])
    assert result_status.exit_code == 0
    assert "No active constraints found" in result_status.stdout
    assert "task:api" not in result_status.stdout
~~~~~
~~~~~python
    # 3. Check the status and verify it's gone
    result_status = runner.invoke(observer_app, ["status", "--backend", "sqlite"])
    assert result_status.exit_code == 0
    assert "No active constraints found" in result_status.stderr
    assert "task:api" not in result_status.stderr
~~~~~

### 下一步建议
修复了测试断言后，请重新运行测试套件。测试应该会全部通过。

一旦确认所有测试都已通过，我们就可以放心地将整个 `SqliteConnector` 功能（包括代码实现和所有测试）作为一个原子单元进行提交。如果你同意，我将准备一个 `[COMMIT]` 计划。
