这是由于测试中使用的 `MockExecutor` 为了方便控制时序，没有执行真实的任务函数，而是直接返回了固定格式的字符串 `Result for {task_name}`。因此，最终结果不是字符串拼接的结果，而是 `Result for task_c`。

我将修正测试断言以匹配 `MockExecutor` 的行为。

## [WIP] fix(test): 修正集成测试断言以匹配 MockExecutor 行为

### 错误分析
**错误信息**: `AssertionError: assert 'Result for task_c' == 'C after B after A'`
**原因**: 在 `test_engine_constraints.py` 中，使用了 `MockExecutor` 来替代真实的执行器。`MockExecutor` 的实现逻辑是忽略任务函数和参数，固定返回 `f"Result for {node.name}"`。因此，`task_c` 的返回值是 `"Result for task_c"`，而不是业务逻辑预期的 `"C after B after A"`。
**结论**: 测试的控制流逻辑（暂停/恢复）已经通过验证（前面的断言都通过了），仅最后的返回值断言需要修正。

### 用户需求
修复 `tests/py/runtime/test_engine_constraints.py` 中的测试失败。

### 评论
这是一个简单的测试代码修正，不涉及业务逻辑变更。

### 目标
修改 `test_engine_pauses_and_resumes_specific_task` 中的断言，使其与 `MockExecutor` 的实际输出一致。

### 基本原理
将 `assert final_result == "C after B after A"` 修改为 `assert final_result == "Result for task_c"`。

### 标签
#intent/fix #flow/ready #priority/high
#comp/tests
#ai/instruct
#task/domain/control #task/object/constraint-system #task/action/bug-fix #task/state/continue

---
### Script

#### Acts 1: 修正测试断言

~~~~~act
patch_file
tests/py/runtime/test_engine_constraints.py
~~~~~
~~~~~python
    # 9. Verify the final result
    final_result = await run_task
    assert final_result == "C after B after A"
~~~~~
~~~~~python
    # 9. Verify the final result
    final_result = await run_task
    # Note: Since we use MockExecutor, the result is the fixed string it returns,
    # not the result of the actual task function.
    assert final_result == "Result for task_c"
~~~~~

### 下一步建议
测试修正后，请重新运行测试。如果通过，我们将继续按照原定计划，进入 **里程碑 3.2: 并发管理 (Concurrency Management)** 的开发。
