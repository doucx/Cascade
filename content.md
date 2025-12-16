这是一个非常经典的异步编程错误。

### 错误分析

错误 `RuntimeError: asyncio.run() cannot be called from a running event loop` 发生的原因是：

1.  **环境**: 你的测试使用了 `@pytest.mark.asyncio` (通过 `pytest-aiohttp`)。这意味着 `pytest` 已经为你创建并启动了一个 `asyncio` 事件循环来运行测试函数。
2.  **冲突**: 在测试内部，你调用了 `cs.run()`。
3.  **实现**: 查看 `src/cascade/__init__.py`，`cs.run` 的实现是：
    ```python
    def run(...):
        # ...
        return asyncio.run(engine.run(...)) 
    ```
4.  **根本原因**: `asyncio.run()` 的设计初衷是作为**同步**程序的入口点。它会尝试创建一个**新**的事件循环。如果检测到当前线程已经有一个正在运行的循环（你的测试环境就是这种情况），它就会抛出这个错误，以防止嵌套循环带来的复杂性。

### 解决方案

在已经处于异步上下文（如 `async def` 测试函数或 FastAPI 路由）中时，你不应该使用 `cs.run()` 这个便利封装。

你应该直接使用更底层的 `Engine` API，并 `await` 它的 `run` 方法。这正好符合 `Cascade` 的分层设计：`cs.run` 针对脚本用户，`Engine` 针对集成和高级用户。

我将生成一个计划来更新测试代码，改用 `Engine` 直接运行。

## [WIP] fix: 修复测试中的嵌套事件循环错误

### 用户需求
修复 `tests/test_http.py` 中因在异步测试环境下调用 `cs.run()` (内部使用 `asyncio.run()`) 而导致的 `RuntimeError`。

### 评论
这是一个常见的误区。在 `pytest-asyncio` 环境中，我们已经是“原生异步”的了，因此不需要（也不能）再次启动一个新的事件循环。直接 `await engine.run()` 是正确且更高效的做法。这同时也验证了 `Cascade` 的 `Engine` API 可以被无缝集成到现有的异步应用中。

### 目标
修改 `tests/test_http.py`，将所有 `cs.run(...)` 调用替换为 `await cs.Engine().run(...)`。

### 基本原理
`cs.run` 是一个为同步入口点设计的便利函数。在异步测试中，我们需要手动实例化 `Engine` 并以此执行工作流，从而复用现有的事件循环。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/async #scope/dx #ai/instruct #task/domain/testing #task/object/event-loop #task/action/fix #task/state/continue #task/status/active

---

### Script

#### Acts 1: 更新 `test_http.py` 以使用 `Engine`

我们将修改两个测试函数，不再使用 `cs.run`，而是实例化 `cs.Engine` 并 `await` 其运行结果。

~~~~~act
patch_file
tests/test_http.py
~~~~~
~~~~~python
    final_result = process_user(api_response)

    # 3. Run and Assert
    result = cs.run(final_result)
    assert result == "cascade"
~~~~~
~~~~~python
    final_result = process_user(api_response)

    # 3. Run and Assert
    # Since we are already in an async test loop, we use the Engine directly
    # instead of cs.run() which tries to create a new loop via asyncio.run()
    engine = cs.Engine()
    result = await engine.run(final_result)
    assert result == "cascade"
~~~~~

~~~~~act
patch_file
tests/test_http.py
~~~~~
~~~~~python
    final_status = get_status(api_response)
    
    # 3. Run and Assert
    result = cs.run(final_status, params={"username": "dynamic_user"})
    assert result == "ok"
~~~~~
~~~~~python
    final_status = get_status(api_response)
    
    # 3. Run and Assert
    engine = cs.Engine()
    result = await engine.run(final_status, params={"username": "dynamic_user"})
    assert result == "ok"
~~~~~

### 下一步建议
这次修改后，测试应该能够通过。请再次运行 `pytest`。如果通过，我们将完成 `cs.http` Provider 的所有工作，可以进行提交。
