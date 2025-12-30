You are absolutely right. My apologies.

My previous fix was incomplete. While it correctly exposed the explicit API members, it broke the expected behavior for handling *non-existent* attributes. The test has correctly caught this regression.

The test expects a standard `AttributeError: module 'cascade' has no attribute '...'`, but because my modified `__getattr__` directly calls `registry.get(name)` without catching its specific exception, we are leaking the provider system's internal error message: `AttributeError: Cascade provider '...' not found.`.

I will now correct this by reintroducing the `try...except` block in `__getattr__`, which is the correct pattern to translate a lookup failure in the provider system into a standard module-level `AttributeError`.

## [WIP] fix(sdk): Refine `__getattr__` to raise a standard AttributeError

### 错误分析
在之前的修复中，我简化了 `packages/cascade-sdk/src/cascade/__init__.py` 中的 `__getattr__` 函数。这个简化版本直接调用 `registry.get(name)` 并允许其抛出的 `AttributeError` (来自于 `ProviderRegistry`) 冒泡。

然而，新添加的测试 `test_accessing_non_existent_attribute_raises_attribute_error` 明确要求，当访问一个完全不存在的属性时，`cascade` 模块应该表现得像一个标准的 Python 模块，即抛出一个带有 `module '...' has no attribute '...'` 信息的 `AttributeError`。

当前的实现泄露了 provider 系统的内部错误信息 (`Cascade provider '...' not found.`)，这违反了封装原则，并导致了测试断言失败。

### 用户需求
用户要求修复 `__getattr__` 的行为，使其在 provider 未找到时能抛出标准的、符合 Python 规范的 `AttributeError`，从而使新编写的集成测试能够通过。

### 评论
这是一个非常好的测试用例，它保护了模块的公共接口行为，确保了开发者体验 (DX) 的一致性。一个模块在找不到属性时不应该暴露其内部的查找机制。这个修复将使 `cascade` 模块的行为更加健壮和可预测。

### 目标
1.  修改 `packages/cascade-sdk/src/cascade/__init__.py` 中的 `__getattr__` 函数。
2.  在该函数中，使用 `try...except AttributeError` 块来捕获由 `registry.get(name)` 抛出的异常。
3.  在 `except` 块中，抛出一个新的、带有标准模块错误信息的 `AttributeError`。
4.  确保所有测试，包括新添加的 `test_public_api_imports.py`，都能通过。

### 基本原理
`__getattr__` 作为一个钩子，其职责应该是在其负责的查找机制（这里是 provider registry）失败时，无缝地回退到标准的 Python 行为。通过捕获 provider registry 抛出的特定 `AttributeError`，并将其转换为一个通用的、描述模块属性缺失的 `AttributeError`，我们遵循了最小意外原则，并满足了测试用例所定义的行为契约。

### 标签
#intent/fix #flow/ready #priority/high #comp/sdk #scope/dx #ai/refine #task/domain/testing #task/object/api-surface #task/action/stabilization #task/state/continue

---
### Script

#### Acts 1: [GREEN] 修正 `__getattr__` 的异常处理逻辑

我们将恢复 `try...except` 结构，以确保在 provider 未找到时能抛出正确的 `AttributeError`。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python.old
def __getattr__(name: str) -> Any:
    """
    Dynamically loads providers from the registry when they are accessed as attributes
    on the `cascade` module (e.g., `cs.read.text`).
    """
    from .providers.registry import registry

    # This will raise an AttributeError for names that are not registered providers,
    # which is the correct behavior. We no longer need a try/except block that
    # could mask other import-related issues.
    return registry.get(name)
~~~~~
~~~~~python.new
def __getattr__(name: str) -> Any:
    """
    Dynamically loads providers from the registry when they are accessed as attributes
    on the `cascade` module (e.g., `cs.read.text`).
    """
    from .providers.registry import registry

    try:
        # Attempt to resolve the name as a provider.
        return registry.get(name)
    except AttributeError:
        # If the provider registry doesn't know the name, we raise the standard
        # module-level AttributeError to maintain expected Python behavior.
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
~~~~~

### 下一步建议
我们已经修复了 `__getattr__` 的逻辑。现在，请再次运行 `pytest packages/cascade-sdk/`。这一次，两个测试用例都应该能成功通过。如果测试通过，我将准备一个 `[COMMIT]` 计划来提交这些修复。
