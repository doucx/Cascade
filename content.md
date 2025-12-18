# [WIP] fix: 修复 GraphBuilder 对列表依赖的解析限制导致的测试失败

### 错误分析
测试 `test_global_concurrency_limit` 失败的根本原因是 `GraphBuilder` 目前不支持深度遍历容器（如列表、字典）来查找 `LazyResult` 依赖。

在测试代码中：
```python
    wf = [task_a(1), task_b(2)]
    workflow = wrapper(wf)
```
`wrapper` 接收一个列表 `wf`。`GraphBuilder` 将这个列表视为一个单纯的字面量（Literal），而没有深入其中发现 `task_a(1)` 和 `task_b(2)` 是需要执行的依赖任务。结果是，`Engine` 只执行了 `wrapper`，而完全忽略了 `task_a` 和 `task_b`，导致测试观察到的执行时间仅为单次任务耗时（0.05s），而不是预期的串行耗时（0.1s）。

### 解决方案
修改测试用例，将依赖项作为独立的参数传递给 `wrapper` 任务。这样 `GraphBuilder` 就能正确识别它们并在图中建立依赖关系，从而确保 `task_a` 和 `task_b` 被调度执行。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/core #task/object/test-suite #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正测试用例中的依赖传递方式

~~~~~act
patch_file
tests/py/runtime/test_engine_concurrency.py
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_global_concurrency_limit(engine, mock_connector):
    @cs.task
    def task_a(x): return x
    
    @cs.task
    def task_b(x): return x

    wf = [task_a(1), task_b(2)]
    
    @cs.task
    def wrapper(results): return results
    workflow = wrapper(wf)

    payload = {
        "id": "global-limit",
        "scope": "global",
        "type": "concurrency",
        "params": {"limit": 1}
    }
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_global_concurrency_limit(engine, mock_connector):
    @cs.task
    def task_a(x): return x
    
    @cs.task
    def task_b(x): return x

    # Pass dependencies as separate arguments so GraphBuilder detects them
    @cs.task
    def wrapper(res_a, res_b): return [res_a, res_b]
    
    workflow = wrapper(task_a(1), task_b(2))

    payload = {
        "id": "global-limit",
        "scope": "global",
        "type": "concurrency",
        "params": {"limit": 1}
    }
~~~~~

### 下一步建议
测试通过后，我们将清理测试文件中的调试代码，并正式提交 Phase 3 的工作。
