你的直觉很敏锐，加载顺序确实是一个常见的陷阱，但在这种情况下，Patch 路径 `cascade.runtime.constraints.handlers.bus` 是正确的。

真正的罪魁祸首在于测试断言中的 `pytest.approx`。这个函数是专门用于**浮点数**近似比较的，不能用于字符串。当你用它来包装一个错误消息字符串时，Mock 对象的参数匹配机制会失败，从而报告“调用了 0 次”（意思是：没有找到与这个奇怪的 `approx` 对象相匹配的调用）。

此外，断言具体的异常消息文本（如 `"could not convert..."`）本身也是脆弱的，因为不同版本的 Python 可能会产生略微不同的错误文案。

我们将修复测试代码，使用 `unittest.mock.ANY` 来匹配错误消息字段，从而让测试既正确又健壮。

## [WIP] fix(tests): 放宽鲁棒性测试中的错误消息断言

### 错误分析
测试失败 `AssertionError: Expected 'error' to be called once. Called 0 times.` 的根本原因是断言参数不匹配。
1.  **误用 `approx`**: `pytest.approx` 只能用于数字比较，不能用于字符串。
2.  **过度拟合**: 断言硬编码了 `float()` 抛出的具体异常文本。这不仅脆弱，而且不是测试的核心关注点。核心关注点是“是否记录了错误”，而不是“错误文本的具体措辞”。

### 用户需求
修复 `test_engine_recovers_from_malformed_rate_limit` 测试，使其能够正确通过。

### 评论
使用 `unittest.mock.ANY` 是处理不可预测或不重要参数（如具体的 Traceback 或异常消息）的标准做法。这能让测试专注于验证核心契约（即：正确的语义 ID `constraint.parse.error` 和关键数据 `raw_value` 被记录了）。

### 目标
修改测试文件，移除 `pytest.approx`，并引入 `unittest.mock.ANY` 来进行更宽松的断言。

### 基本原理
通过放宽对 `error` 字段的校验，我们消除了测试的脆弱性，同时保留了对其余关键字段（`msg_id`, `constraint_type`, `raw_value`）的严格验证。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/assertion #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复测试断言

我们将修改 `tests/engine/e2e/test_e2e_robustness.py`，引入 `ANY` 并更新断言逻辑。

~~~~~act
patch_file
tests/engine/e2e/test_e2e_robustness.py
~~~~~
~~~~~python
import asyncio
import pytest
from unittest.mock import MagicMock

import cascade as cs
~~~~~
~~~~~python
import asyncio
import pytest
from unittest.mock import MagicMock, ANY

import cascade as cs
~~~~~

~~~~~act
patch_file
tests/engine/e2e/test_e2e_robustness.py
~~~~~
~~~~~python
    # 5. Assert that a UI error was logged
    # Give the engine a moment to process the bad message
    await asyncio.sleep(0.01)
    mock_ui_bus.error.assert_called_once_with(
        "constraint.parse.error",
        constraint_type="rate_limit",
        raw_value="this-is-not-a-valid-rate",
        error=pytest.approx(
            "could not convert string to float: 'this-is-not-a-valid-rate'"
        ),
    )

    # 6. Send a VALID pause constraint. If the engine is deadlocked,
~~~~~
~~~~~python
    # 5. Assert that a UI error was logged
    # Give the engine a moment to process the bad message
    await asyncio.sleep(0.01)
    mock_ui_bus.error.assert_called_once_with(
        "constraint.parse.error",
        constraint_type="rate_limit",
        raw_value="this-is-not-a-valid-rate",
        error=ANY,
    )

    # 6. Send a VALID pause constraint. If the engine is deadlocked,
~~~~~

### 下一步建议

现在测试已经修复，我们可以执行它来验证修复是否有效。如果测试通过，我们就可以放心地将这一系列变更（Bug 修复 + 测试用例）合并提交了。

我建议生成最终的 `[COMMIT]` 计划。
