My deepest apologies. You've caught me in a subtle but clear error. The `repr()` of the object becomes a string, and when that string is put into a dictionary which is then printed, the string value gets its own quotes.

My assertion was wrong.

- My assertion expected: `{'param': Const(42)}` (the object itself)
- The code produced: `{'param': 'Const(42)'}` (a string representation of the object)

I will fix my own mistake immediately.

## [WIP] fix(tests): Correct assertion string for repr output

### 错误分析
我在上一步修复 `test_console_subscriber_renders_correctly` 时，虽然更新了事件的创建，但在更新断言时犯了一个错误。`DryRunConsoleSubscriber` 的 `on_node` 方法使用 `repr(v)` 来格式化 `input_bindings` 中的值，这会将 `Constant(42)`对象转换为字符串 `'Const(42)'`。当包含这个字符串的字典被打印时，这个字符串值会带上它自己的单引号。我的断言字符串 `assert "Bindings: {'param': Const(42)}"` 遗漏了这些单引号，导致 `AssertionError`。

### 用户需求
修复 `test_preview.py` 中错误的断言，使测试通过。

### 评论
这是一个微小但关键的细节错误。通过这次修正，测试将能正确匹配 `repr()` 嵌套在字典中并被字符串化后的实际输出。

### 目标
1.  将 `test_console_subscriber_renders_correctly` 中的断言字符串修正为 `assert "Bindings: {'param': 'Const(42)'}" in captured.out`。

### 基本原理
精确匹配 `print` 函数将一个包含字符串值的字典转换为其最终文本表示形式时的行为。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/sdk #ai/instruct #task/domain/testing #task/object/unit-test #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 `test_preview.py` 中的断言

~~~~~act
patch_file
tests/sdk/tools/test_preview.py
~~~~~
~~~~~python
    captured = capsys.readouterr()
    assert "[1/2]" in captured.out
    assert "my_task" in captured.out
    assert "Bindings: {'param': Const(42)}" in captured.out
~~~~~
~~~~~python
    captured = capsys.readouterr()
    assert "[1/2]" in captured.out
    assert "my_task" in captured.out
    assert "Bindings: {'param': 'Const(42)'}" in captured.out
~~~~~

### 下一步建议
这一次，我非常有信心这是最后一个需要修复的问题。请运行 `pytest`，如果所有测试都通过，我将立即生成 `[COMMIT]` 计划。
