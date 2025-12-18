System check:
- Recent refactor: Moved `messaging_bus` from `cascade.runtime.subscribers` (local import alias) to `cascade.common.messaging.bus` (direct import).
- Test Failure: `test_e2e_linear_workflow` and `test_e2e_failure_propagation` fail to find the expected calls on the mock object.
- Root Cause: `HumanReadableLogSubscriber` in `cascade/runtime/subscribers.py` imports `bus` using `from cascade.common.messaging import bus`. When `test_end_to_end.py` monkeypatches `cascade.common.messaging.bus`, it *should* work if the module uses the name `cascade.common.messaging.bus`.

However, let's look at `subscribers.py` again (from my internal knowledge of the previous Act):
```python
from cascade.common.messaging import bus
# ...
class HumanReadableLogSubscriber:
    def on_run_started(self, event):
        bus.info(...)
```

And the test patches:
```python
monkeypatch.setattr("cascade.common.messaging.bus", mock_bus)
```

The issue is likely how `bus` is imported in `subscribers.py`. Since it's imported as `from ... import bus`, the `subscribers.py` module holds a *reference* to the original `bus` object. Monkeypatching `cascade.common.messaging.bus` changes the object in the *source* module, but `subscribers.py` might still be holding onto the *old reference* if it was imported before the patch was applied (which is likely, given module caching).

**Correction**: To robustly patch a name imported with `from ... import ...`, we should patch it *where it is used*, i.e., in `cascade.runtime.subscribers`.

Let's check `subscribers.py` imports again.
It has: `from cascade.common.messaging import bus`

So inside `cascade.runtime.subscribers`, the variable is named `bus`.
Therefore, the monkeypatch should target `cascade.runtime.subscribers.bus`.

Wait, the original code had: `from ..messaging.bus import bus as messaging_bus`.
The test patched `cascade.runtime.subscribers.messaging_bus`.

My previous fix changed the patch to `cascade.common.messaging.bus`. This updates the *source*, but `cascade.runtime.subscribers` has already imported it.

**Strategy**: Patch the object in the module where it is being *consumed*. This is the standard rule for `unittest.mock` / `monkeypatch`: "Patch where it's used, not where it's defined."

So I need to patch `cascade.runtime.subscribers.bus`.

## [WIP] test(fix): Correctly patch the consumed bus object in subscribers module

### 错误分析
集成测试 `test_end_to_end.py` 失败是因为 monkeypatch 的目标不正确。

在 `cascade/runtime/subscribers.py` 中，我们使用了 `from cascade.common.messaging import bus`。这意味着 `subscribers` 模块在其命名空间中拥有一个名为 `bus` 的引用，指向导入时的 `MessageBus` 对象。

当我们执行 `monkeypatch.setattr("cascade.common.messaging.bus", mock_bus)` 时，我们替换了 `cascade.common.messaging` 模块中的 `bus`。但是，如果 `subscribers` 模块已经被加载（这在运行其他测试时很可能已经发生），它仍然持有对原始对象的引用。

根据 Python Mock 的黄金法则：“在对象被使用的地方进行 Patch，而不是在它被定义的地方”。

因此，我们需要 patch `cascade.runtime.subscribers` 模块中的 `bus` 变量。

### 用户需求
修复集成测试中的 Mock 逻辑，使其能够拦截到 `HumanReadableLogSubscriber` 发出的消息。

### 评论
这是一个经典的 Python 测试陷阱。修正这个 Patch 路径后，测试应该就能通过了。这也提醒我们，虽然架构解耦了，但在 Python 的动态特性下，测试替身的注入点依然需要精确。

### 目标
1.  修改 `tests/py/integration/test_end_to_end.py`。
2.  将 Patch 目标从 `cascade.common.messaging.bus` 更改为 `cascade.runtime.subscribers.bus`。

### 基本原理
Patch file direct edit.

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/integration-test #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修正 Monkeypatch 目标

~~~~~act
patch_file
tests/py/integration/test_end_to_end.py
~~~~~
~~~~~python
@pytest.fixture
def mock_messaging_bus(monkeypatch):
    """Mocks the global messaging bus and returns the mock object."""
    mock_bus = MagicMock()
    # Correctly patch the new global bus in cascade-common
    monkeypatch.setattr("cascade.common.messaging.bus", mock_bus)
    return mock_bus
~~~~~
~~~~~python
@pytest.fixture
def mock_messaging_bus(monkeypatch):
    """Mocks the global messaging bus and returns the mock object."""
    mock_bus = MagicMock()
    # Patch the bus WHERE IT IS USED, not where it is defined.
    # subscribers.py does: from cascade.common.messaging import bus
    monkeypatch.setattr("cascade.runtime.subscribers.bus", mock_bus)
    return mock_bus
~~~~~

### 下一步建议
Please run `pytest` again. This should resolve the reference issue.
