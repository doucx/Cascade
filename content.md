好的，这是最稳妥的排查方式。我们不能盲目猜测，必须通过可观测的证据来定位问题。

我们将分两步进行“插桩”调试：

1.  **在源代码中插桩**：确认代码是否真的捕获了异常并尝试调用 `bus.error`。
2.  **在测试中插桩**：确认 Mock 对象的状态和调用记录。

## [WIP] chore(debug): 为鲁棒性测试添加调试日志

### 用户需求
在 `RateLimitConstraintHandler` 的异常处理逻辑和测试用例中添加临时调试日志，以排查 Mock 断言失败的根本原因。

### 评论
这种“探针”式修改是临时的，旨在获取运行时信息。一旦问题解决，我们将回滚这些修改。

### 目标
1.  修改 `handlers.py`，在捕获异常时打印调试信息。
2.  修改 `test_e2e_robustness.py`，打印 Mock 对象的详细调用记录。

### 基本原理
通过对比控制台输出（stdout）中的调试信息，我们可以区分以下两种情况：
1.  **逻辑未触发**: 如果没看到 `handlers.py` 的日志，说明异常捕获逻辑根本没执行。
2.  **Mock 失效**: 如果看到了日志但测试断言失败，说明 Mock 对象注入的位置不对，或者被测试代码引用的是另一个 `bus` 实例。

### 标签
#intent/tooling #flow/ready #priority/high #comp/debug #scope/core #ai/instruct #task/domain/debugging #task/action/instrument #task/state/continue

---

### Script

#### Acts 1: 在 `handlers.py` 中添加调试日志

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/constraints/handlers.py
~~~~~
~~~~~python
    except (ValueError, TypeError) as e:
        bus.error(
            "constraint.parse.error",
            constraint_type="rate_limit",
            raw_value=rate_str,
            error=str(e),
        )
        # Return a safe default (e.g., 1 token per second) to prevent crashes
~~~~~
~~~~~python
    except (ValueError, TypeError) as e:
        print(f"DEBUG: Caught exception in _parse_rate_string: {e}")
        bus.error(
            "constraint.parse.error",
            constraint_type="rate_limit",
            raw_value=rate_str,
            error=str(e),
        )
        # Return a safe default (e.g., 1 token per second) to prevent crashes
~~~~~

#### Acts 2: 在测试中打印 Mock 状态

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
        error=ANY,
    )
~~~~~
~~~~~python
    # 5. Assert that a UI error was logged
    # Give the engine a moment to process the bad message
    await asyncio.sleep(0.01)
    print(f"DEBUG: Mock calls: {mock_ui_bus.error.call_args_list}")
    mock_ui_bus.error.assert_called_once_with(
        "constraint.parse.error",
        constraint_type="rate_limit",
        raw_value="this-is-not-a-valid-rate",
        error=ANY,
    )
~~~~~

### 下一步建议

请运行测试并观察输出。

*   **情况 A**: 如果你看不到 `DEBUG: Caught exception...`，说明 `_parse_rate_string` 没有被调用，或者是传入的参数没有触发 `ValueError`。这可能是因为 Mock Connector 没有正确触发回调。
*   **情况 B**: 如果你看到了 `DEBUG: Caught exception...`，但 `Mock calls` 是空的 `[]`，说明代码调用的是**真正的 `bus` 对象**，而不是你的 Mock 对象。这意味着 `monkeypatch` 注入失败，或者模块导入顺序有问题。

根据输出结果，我们将制定下一步修复计划。
