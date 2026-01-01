由于 `cascade-sdk` 的 `__getattr__` 实现过于激进，它捕获了所有未找到的属性访问（包括 Python 内部机制可能访问的 `__spec__`, `__path__` 等 dunder 属性），并将它们全部转发给了 `ProviderRegistry`。

在 `import cascade` 的初始化过程中，当执行 `from cascade.sdk import *` 时，Python 的导入机制可能会访问 `cascade.sdk` 的某些内部属性（如 `__spec__`）。由于这些属性不在 `_IMPORT_MAP` 中，`__getattr__` 将其误认为是动态 Provider 请求，从而触发了全量的 `_discover_entry_points()`。

这导致了以下致命的循环：
1. `import cascade` 开始初始化 -> 锁住 `cascade` 模块。
2. `cascade` 导入 `cascade.sdk`。
3. `cascade.sdk` 的 `__getattr__` 被某些内部属性访问触发。
4. `__getattr__` 调用 `registry.get()` -> 触发 `_discover_entry_points()`。
5. 注册表尝试加载所有 Provider，包括 `cascade-provider-ipfs`。
6. IPFS Provider 尝试 `from cascade.spec.task import task`。
7. 由于某种环境或路径解析原因（可能是因为 `cascade` 是命名空间包），这个导入在 `cascade` 尚未完全初始化时，回溯到了顶层的 `cascade` 模块并尝试查找 `task` 属性。
8. 此时 `cascade` 模块尚未完成 `from cascade.sdk import *`，因此没有 `task` 属性，导致 `AttributeError`。

**修复方案**：
## [WIP] 修改 `cascade/sdk.py` 的 `__getattr__` 方法，使其明确忽略所有以 `__` 开头的属性访问。这将切断上述循环的触发源。

## 计划
1. 修改 `packages/cascade-sdk/src/cascade/sdk.py`。
2. 在 `__getattr__` 开头添加检查：如果 `name.startswith("__")`，直接抛出 `AttributeError`。
3. 运行 `diagnose_providers.py` 验证修复。
4. 运行原始测试用例验证修复。

### Script

#### Acts 1: 修复 cascade/sdk.py

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/sdk.py
~~~~~
~~~~~python.old
def __getattr__(name: str) -> Any:
    # 1. Check if it's a known API member in our lazy map
    if name in _IMPORT_MAP:
        module_path, obj_name = _IMPORT_MAP[name]
        module = __import__(module_path, fromlist=[obj_name])
        return getattr(module, obj_name)

    # 2. Check if it's a dynamic provider (e.g., cs.read.text)
    # This maintains the v1.3 behavior of dynamic provider loading
    try:
        from cascade.providers.registry import registry

        return registry.get(name)
    except (ImportError, AttributeError):
        # Fallthrough to raise the standard AttributeError below
        pass

    raise AttributeError(f"module 'cascade' has no attribute '{name}'")
~~~~~
~~~~~python.new
def __getattr__(name: str) -> Any:
    # 0. Ignore internal dunder attributes to prevent recursion/side-effects
    if name.startswith("__"):
        raise AttributeError(f"module 'cascade' has no attribute '{name}'")

    # 1. Check if it's a known API member in our lazy map
    if name in _IMPORT_MAP:
        module_path, obj_name = _IMPORT_MAP[name]
        module = __import__(module_path, fromlist=[obj_name])
        return getattr(module, obj_name)

    # 2. Check if it's a dynamic provider (e.g., cs.read.text)
    # This maintains the v1.3 behavior of dynamic provider loading
    try:
        from cascade.providers.registry import registry

        return registry.get(name)
    except (ImportError, AttributeError):
        # Fallthrough to raise the standard AttributeError below
        pass

    raise AttributeError(f"module 'cascade' has no attribute '{name}'")
~~~~~

### 下一步建议

1.  再次运行诊断脚本以确认 Provider 加载不再有错误：
    ```bash
    python diagnose_providers.py
    ```
2.  运行 IPFS 集成测试：
    ```bash
    pytest packages/cascade-provider-ipfs/tests/integration/test_ipfs.py
    ```
