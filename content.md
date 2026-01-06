## [WIP] fix(tests): Adapt test mocks to Sync Kernel and Ref Protocol

### 错误分析

我们遇到了两类错误，都源于底层协议变更（Sync Kernel 和 Ref Protocol）与旧的测试 Mock/Helper 代码不兼容。

1.  **`test_resource_backpressure.py` 中的 `TypeError: 'Ref' and 'int'`**
    *   **原因**: `const_probe` 现在返回 `Ref` 对象（为了符合 Ref-Based 架构）。但是，测试中的 `mock_worker` 依然假设 `worker_payload["x"]` 是一个直接的 `int`。
    *   **分析**: 当 `const_probe` 产生 `x=10` 时，它实际上产生了一个 `Token(payload=Ref(meta={'scalar_value': 10}, ...))`。`Bleacher` 将此 `Ref` 传递给 `Worker`。`mock_worker` 尝试 `Ref + 1`，导致崩溃。
    *   **修复**: `mock_worker` 需要适配 Ref 协议。它应该检查输入是否为 `Ref`，如果是，则提取其值（在这个测试场景中，我们可以直接从 `meta['scalar_value']` 提取，或者为了更严谨，Mock 一个 Store 来 `get`）。但鉴于这是 `vm` 包的测试，我们可以简化处理：让 Mock Worker 能够解包 Ref。

2.  **`test_resource_contention.py` 中的 `TypeError: object dict can't be used in 'await' expression`**
    *   **原因**: 我们将 `const_probe` 等标准库函数改为了**同步函数** (`def`)。但是，在 `test_resource_contention.py` 中，我们使用了一个装饰器 `debug_wrapper` 来包裹这些函数，而这个装饰器被写成了 `async def wrapped(...)`，并且内部无条件地使用了 `await func(...)`。
    *   **分析**: 当 `Reactor` 看到 `debug_wrapper` 是一个协程函数时，它会 `await` 它。但在 wrapper 内部，它尝试 `await func(...)`。由于 `func`（如 `const_probe`）现在是同步的，它返回的是一个 `dict` 结果，而不是一个 Awaitable。于是报错 `dict can't be used in 'await' expression`。
    *   **修复**: 更新 `debug_wrapper`，使其能够智能地处理同步和异步被包装函数。或者简单地将其分为 `sync_debug_wrapper` 和 `async_debug_wrapper`。

### 用户需求
修复因架构迁移导致的测试套件崩溃，确保 CI/CD 绿灯。

### 评论
这些错误是典型的“重构阵痛”。当我们修改了底层契约（Sync vs Async, Value vs Ref）时，所有依赖旧契约的 Mock 和 Helper 都必须更新。这是 TDD 循环中不可避免且健康的一部分：红 -> 绿 -> 重构。

### 目标
1.  修改 `packages/cascade-vm/tests/integration/test_resource_backpressure.py` 中的 `mock_worker`，使其支持 `Ref` 输入。
2.  修改 `packages/cascade-compiler/tests/integration/test_resource_contention.py` 中的 `debug_wrapper`，使其支持同步函数调用。

### 基本原理
*   **Mock 适配**: 测试中的 Mock 对象必须模拟真实世界的行为。在 Ref-Based 架构中，Worker 总是接收 Ref。因此 Mock Worker 必须知道如何处理 Ref。
*   **Wrapper 通用性**: 测试工具（如 Debug Wrapper）应该对被包装函数的性质（同步/异步）保持透明或自适应，以避免引入人为的错误。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/test-harness #task/action/fix-mocks #task/state/continue

---

### Script

#### Acts 1: 修复 `test_resource_backpressure.py` 的 Mock Worker

让 `mock_worker` 能够处理 `Ref` 类型的输入。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
from cascade.std.probe.const import const_probe


# --- Mocks ---


def mock_worker(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    worker_input_token = inputs["worker_input"]
    worker_payload = worker_input_token.payload
    val = worker_payload["x"]
    return {"worker_result": Token(payload=val + 1)}


def noop_observer(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
~~~~~
~~~~~python.new
from cascade.std.probe.const import const_probe
from cascade.spec.physical.object import Ref


# --- Mocks ---


def mock_worker(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    worker_input_token = inputs["worker_input"]
    worker_payload = worker_input_token.payload
    
    # Handle Ref-based payload (v3.1)
    val = worker_payload["x"]
    if isinstance(val, Ref):
        # In this specific test, we know const_probe hoists scalar values.
        # So we can peek at meta. In a real worker, we'd use store.get().
        if "scalar_value" in val.meta:
            val = val.meta["scalar_value"]
        else:
            # Fallback for completeness, though test setup should ensure hoisting
            store = resources.get("system.object_store")
            val = store.get(val)

    return {"worker_result": Token(payload=val + 1)}


def noop_observer(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
~~~~~

#### Acts 2: 修复 `test_resource_contention.py` 的 Debug Wrapper

修改 `debug_wrapper` 以支持同步函数。由于 `Reactor` 现在根据函数是否为协程来决定调用方式，我们需要确保 wrapper 正确地反射了被包装函数的类型。
最好的办法是：如果被包装函数是同步的，返回一个同步 wrapper；如果是异步的，返回一个异步 wrapper。

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
    def debug_wrapper(func, name):
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            print(f"[MAN-START] {name}")
            try:
                result = await func(*args, **kwargs)
                print(f"[MAN-END  ] {name}")
                return result
            except Exception as e:
                print(f"[MAN-ERROR] {name}: {e}")
                raise

        return wrapped

    func_map = {}
~~~~~
~~~~~python.new
    def debug_wrapper(func, name):
        import inspect
        
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapped(*args, **kwargs):
                print(f"[MAN-START] {name}")
                try:
                    result = await func(*args, **kwargs)
                    print(f"[MAN-END  ] {name}")
                    return result
                except Exception as e:
                    print(f"[MAN-ERROR] {name}: {e}")
                    raise
            return async_wrapped
        else:
            @functools.wraps(func)
            def sync_wrapped(*args, **kwargs):
                print(f"[MAN-START] {name}")
                try:
                    result = func(*args, **kwargs)
                    print(f"[MAN-END  ] {name}")
                    return result
                except Exception as e:
                    print(f"[MAN-ERROR] {name}: {e}")
                    raise
            return sync_wrapped

    func_map = {}
~~~~~

### 下一步建议

修复这两个 Mock 问题后，主要的同步化障碍应该已被清除。
1.  **再次运行测试**: 验证修复是否有效。
2.  **清理旧代码**: 检查是否还有残留的 `async def` ICs 未被覆盖。
3.  **提交**: 如果测试通过，这将是一个标志性的提交，标志着 Cascade 正式进入 v3.1 时代。
