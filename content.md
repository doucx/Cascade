您的分析请求已收到。

测试结果**不正常**。所有测试用例都在其**设置（setup）阶段失败**，而不是在执行阶段。这是一个阻断性问题，必须在继续路线图之前解决。

我将生成一个计划来修复这个错误。

## [WIP] fix(test): 修复 pytest-asyncio 中异步 fixture 的弃用警告

### 错误分析
测试失败的根本原因是 `pytest.PytestRemovedIn9Warning`。该警告指出，一个测试请求了一个**异步 fixture** (`controller_connector`)，但 `pytest` 核心本身无法处理它。

具体分析如下：

1.  **问题的根源**: 我将 `controller_connector` fixture 定义为一个 `async def` 函数，并使用了 `yield`。这使其成为一个**异步生成器 (async generator)**。
2.  **`pytest` 的限制**: `pytest` 的原生 fixture 机制只能处理同步函数和同步生成器。当它遇到一个 `async def` fixture 时，它不知道如何去 `await` 其设置和拆卸部分。
3.  **`pytest-asyncio` 的角色**: `pytest-asyncio` 插件通过钩子（hook）来扩展 `pytest`，使其能够正确处理异步测试和异步 fixture。然而，在我们的案例中，这个钩子没有按预期工作，导致 `pytest` 的默认行为被触发。
4.  **弃用警告**: `pytest` 正在逐步弃用对“同步测试请求异步 fixture”这种模糊模式的支持。虽然我们的测试本身是异步的（标记为 `@pytest.mark.asyncio`），但 fixture 的处理流程触发了这个警告，这表明我们的 fixture 定义方式不是最健壮的。

### 用户需求
修复 `test_e2e_sqlite_connector.py` 中的测试设置错误，使其能够成功运行并通过。

### 评论
这个错误是 `pytest` 与 `pytest-asyncio` 交互时一个常见的微妙问题。最可靠、最符合 `pytest-asyncio` 最佳实践的解决方案是：将异步 fixture 重构为一个**同步 fixture**，并在其内部使用由 `pytest-asyncio` 提供的 `event_loop` fixture 来显式地运行异步的设置（setup）和拆卸（teardown）代码。

这种方法消除了模糊性：
-   从 `pytest` 的角度来看，`controller_connector` 是一个普通的同步生成器 fixture，它知道如何处理。
-   在 fixture 内部，我们获得了对当前 `asyncio` 事件循环的完全控制，可以安全地执行 `await connector.connect()` 和 `await connector.disconnect()`。

这将完全解决 `PytestRemovedIn9Warning` 警告，并使测试代码更加健壮和面向未来。

### 目标
1.  修改 `tests/engine/e2e/test_e2e_sqlite_connector.py` 文件。
2.  重构 `controller_connector` fixture，将其从 `async def` 更改为 `def`。
3.  将 `event_loop` fixture 注入到 `controller_connector` 中。
4.  使用 `event_loop.run_until_complete()` 来包装异步的 `connect()` 和 `disconnect()` 调用。

### 基本原理
本计划将使用一个 `patch_file` 操作来精确地替换 `test_e2e_sqlite_connector.py` 中有问题的 fixture 定义。`old_str` 将包含旧的 `async def` 实现，而 `new_str` 将包含新的、使用 `event_loop` 的同步实现。这是一种原子化且精确的修复方式。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #comp/connector-sqlite #concept/tooling #scope/dx #ai/instruct #task/domain/testing #task/object/async-fixture #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复异步 fixture 的定义

我们将 `controller_connector` fixture 从一个异步生成器重构为一个标准的同步生成器，并使用 `event_loop` fixture 来管理其内部的异步操作。

~~~~~act
patch_file
tests/engine/e2e/test_e2e_sqlite_connector.py
~~~~~
~~~~~python
@pytest.fixture
async def controller_connector(sqlite_db_path):
    """Provides a connector instance to act as the 'controller' CLI."""
    connector = SqliteConnector(db_path=str(sqlite_db_path))
    await connector.connect()
    yield connector
    await connector.disconnect()
~~~~~
~~~~~python
@pytest.fixture
def controller_connector(sqlite_db_path, event_loop):
    """
    Provides a connector instance to act as the 'controller' CLI.
    This is a sync fixture that manages an async resource.
    """
    connector = SqliteConnector(db_path=str(sqlite_db_path))
    event_loop.run_until_complete(connector.connect())
    yield connector
    event_loop.run_until_complete(connector.disconnect())
~~~~~

### 下一步建议
我们已经修复了测试代码中的阻断性错误。现在，我们应该重新运行测试以确认所有问题都已解决，并且 `SqliteConnector` 的行为符合预期。

一旦测试通过，我们就可以安全地继续执行路线图的**步骤 2: [性能优化] 增强 Unix Domain Socket (UDS) 信号机制**。
