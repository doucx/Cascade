I will fix the test by changing the incorrect attribute access to the correct one. The fundamental strategy of inspecting the data model instead of the UI output remains sound; only the implementation detail was flawed.

## [WIP] fix(testing): Correct the API path for inspecting Typer app parameters

### 用户需求
Fix the `AttributeError` in the `test_cli_generator_from_context` test.

### 评论
This is a direct correction of a previous error. By using the correct internal API path, we can finally make the test robust and independent of UI rendering, as was the original intent.

### 目标
1.  Locate the line in `test_cli_generator_from_context` that causes the `AttributeError`.
2.  Replace `app.registered_cli.params` with the correct attribute path: `app.registered_commands[0].params`.

### 基本原理
The `typer.Typer` object maintains a list of registered command objects. Our `create_cli` function registers a single, primary command. This command object, accessible as the first element in `app.registered_commands`, contains a `.params` attribute which is a list of the configured `click.Parameter` objects. By patching the test to use this correct path, we can successfully inspect the command's data structure and validate our logic.

### 标签
#intent/fix #flow/ready #priority/critical #comp/sdk #comp/tests #scope/dx #ai/instruct

---
### Script

#### Acts 1: Patch the test with the correct Typer API

We will apply a precise patch to fix the incorrect attribute access in the test.

~~~~~act
patch_file
packages/cascade-sdk/tests/tools/test_cli.py
~~~~~
~~~~~python
    # 4. 验证参数定义 (Robust method: Inspect data, not UI)
    # Instead of checking the --help string, we inspect the Typer app's
    # internal configuration. This is resilient to formatting changes.
    params = {p.name: p for p in app.registered_cli.params}
    assert "name" in params
~~~~~
~~~~~python
    # 4. 验证参数定义 (Robust method: Inspect data, not UI)
    # Instead of checking the --help string, we inspect the Typer app's
    # internal configuration. This is resilient to formatting changes.
    # The main command is the first registered one.
    params = {p.name: p for p in app.registered_commands[0].params}
    assert "name" in params
~~~~~
