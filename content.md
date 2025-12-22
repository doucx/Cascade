当然，我来修复这些测试错误。

这是一个连锁反应：上一步我们修改了 `cs-controller` 中核心函数的签名以接受 `backend` 参数，但忘记了更新调用这些函数的测试用例，导致了 `TypeError`。

## [WIP] fix: 更新测试用例以匹配新的控制器函数签名

### 错误分析
测试因 `TypeError: ... missing 1 required positional argument: 'backend'` 而失败。

在我上一个计划中，我修改了 `cascade.cli.controller.app` 模块中的 `_publish_pause` 和 `_publish_limit` 函数，为它们添加了 `backend: str` 参数。然而，位于 `tests/cli-controller/test_controller_app.py` 和 `tests/engine/e2e/test_e2e_cli_integration.py` 中的测试用例仍然使用旧的函数签名进行调用，没有传递这个新的、必需的参数，从而导致了类型错误。

### 用户需求
修复所有因函数签名不匹配而导致的 `TypeError`，使测试套件能够成功运行。

### 评论
这是一个在重构过程中很常见的疏漏。修复它很简单，只需将测试代码与被测代码的最新 API 保持同步即可。这也证明了我们的集成测试覆盖是有效的，能够及时捕捉到这类接口变更带来的破坏。

### 目标
1.  修改 `tests/cli-controller/test_controller_app.py` 中对 `_publish_pause` 的调用，为其传递 `backend="mqtt"` 参数。
2.  修改 `tests/engine/e2e/test_e2e_cli_integration.py` 中测试工具 `InProcessController.set_limit` 的实现，使其能够接受并传递 `backend` 参数给 `_publish_limit` 函数。

### 基本原理
我们将使用 `patch_file` 对两个测试文件进行精确修改。对于 `test_controller_app.py`，我们直接在函数调用处添加缺失的参数。对于 `test_e2e_cli_integration.py`，我们将更新测试辅助类的接口，使其与被测代码的接口保持一致，同时为 `backend` 参数提供默认值 `"mqtt"`，以确保现有测试的行为不变。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/cli #task/object/sqlite-connector #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 修复 `test_controller_app.py` 中的函数调用

我们将更新两个测试用例中对 `_publish_pause` 的调用。

~~~~~act
patch_file
tests/cli-controller/test_controller_app.py
~~~~~
~~~~~python
    await controller_app._publish_pause(
        scope="global", ttl=None, hostname="mqtt.test", port=1234
    )
~~~~~
~~~~~python
    await controller_app._publish_pause(
        scope="global", ttl=None, backend="mqtt", hostname="mqtt.test", port=1234
    )
~~~~~

~~~~~act
patch_file
tests/cli-controller/test_controller_app.py
~~~~~
~~~~~python
    await controller_app._publish_pause(
        scope="task:api_call", ttl=None, hostname="mqtt.test", port=1234
    )
~~~~~
~~~~~python
    await controller_app._publish_pause(
        scope="task:api_call",
        ttl=None,
        backend="mqtt",
        hostname="mqtt.test",
        port=1234,
    )
~~~~~

#### Acts 2: 修复 `test_e2e_cli_integration.py` 中的测试辅助工具

现在，我们更新 `InProcessController` 辅助类，使其正确传递 `backend` 参数。

~~~~~act
patch_file
tests/engine/e2e/test_e2e_cli_integration.py
~~~~~
~~~~~python
    async def set_limit(
        self,
        scope: str,
        rate: str | None = None,
        concurrency: int | None = None,
        ttl: int | None = None,
    ):
        """Directly calls the async logic, providing defaults for missing args."""
        await controller_app._publish_limit(
            scope=scope,
            concurrency=concurrency,
            rate=rate,
            ttl=ttl,
            hostname="localhost",  # Constant for test purposes
            port=1883,  # Constant for test purposes
        )
~~~~~
~~~~~python
    async def set_limit(
        self,
        scope: str,
        rate: str | None = None,
        concurrency: int | None = None,
        ttl: int | None = None,
        backend: str = "mqtt",
    ):
        """Directly calls the async logic, providing defaults for missing args."""
        await controller_app._publish_limit(
            scope=scope,
            concurrency=concurrency,
            rate=rate,
            ttl=ttl,
            backend=backend,
            hostname="localhost",  # Constant for test purposes
            port=1883,  # Constant for test purposes
        )
~~~~~

### 下一步建议
这些修复应该可以解决所有的 `TypeError`。请再次运行测试。一旦测试通过，我们就可以安全地继续进行 **步骤 4: [质量保证] 编写全面的端到端测试**，为我们新集成的 `sqlite` 后端添加专门的测试覆盖。
