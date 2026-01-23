简要回答
我们已识别出导致测试失败的两个关键问题：`BridgedComputeService` 中缺乏对递归资源依赖解析的支持（导致 `TypeError`），以及 `ResourceContainer.get_provider` 抛出了错误的异常类型（导致 `KeyError` 而非预期的 `NameError`）。

我们将修复这两个问题，以确保依赖注入（DI）系统能够处理嵌套依赖，并提供正确的错误反馈。

## [WIP] fix(vm): implement recursive resource injection and standardize errors

### 错误分析

1.  **`TypeError: 'Inject' object is not subscriptable`**:
    *   **原因**: `BridgedComputeService._resolve_resource` 方法在实例化资源提供者（Provider）时，没有检查并注入该 Provider 本身所需的依赖。它直接无参数调用 `provider()`，导致 Provider 函数使用了其参数默认值（即 `Inject` 对象），从而在后续使用该参数时（如 `config['db_url']`）引发类型错误。
    *   **证据**: 测试 `test_di_end_to_end` 失败，堆栈指向 `resource = next(gen)` 调用了 `db_connection`，而 `db_connection` 接收到的 `config` 是 `Inject` 对象。

2.  **`KeyError: 'non_existent_db'`**:
    *   **原因**: 测试期望在请求不存在的资源时抛出 `NameError`，但 `ResourceContainer.get_provider` 直接通过字典键访问 `self._resource_providers[name]`，在键不存在时抛出的是 Python 原生的 `KeyError`。
    *   **证据**: 测试 `test_unregistered_resource_raises_error` 失败，捕获到 `KeyError` 而非预期的 `NameError`。

### 用户需求
修复 VM 适配层以支持嵌套的资源依赖注入，并确保在资源未注册时抛出符合规范的 `NameError`。

### 评论
这是一个关键的修复。由于 `cascade-vm` 是新的后端实现，它必须达到与旧版 Execution Graph 相同的功能完备性，特别是在 DI 这样核心的特性上。目前的实现对于简单的、无依赖的资源是有效的，但对于真实场景中常见的嵌套资源（如 DB 连接依赖 Config）则无法工作。

### 目标
1.  修改 `cascade-vm` 中的 `BridgedComputeService._resolve_resource`，使其能够检查 Provider 的签名并递归解析其依赖。
2.  修改 `cascade-runtime` 中的 `ResourceContainer.get_provider`，使其在资源未找到时抛出 `NameError`。

### 基本原理
1.  **递归解析**: 类似于 `ResourceContainer.setup` 的逻辑，我们需要在运行时通过反射（`inspect.signature`）来识别 Provider 的依赖，并在实例化之前先解决这些依赖。
2.  **异常一致性**: 保持 API 契约的一致性。如果某个东西是“必需但缺失的”，`NameError`（或自定义的 `DependencyMissingError`，但此处遵循现有测试约定）比底层的 `KeyError` 语义更准确。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/runtime #task/object/dependency-injection #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 ResourceContainer 的异常类型
首先，我们修改 `ResourceContainer.get_provider` 以抛出正确的异常。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/resources/container.py
~~~~~
~~~~~python.old
    def get_provider(self, name: str) -> Callable:
        provider = self._resource_providers[name]
        if isinstance(provider, ResourceDefinition):
            return provider.func
        return provider
~~~~~
~~~~~python.new
    def get_provider(self, name: str) -> Callable:
        if name not in self._resource_providers:
            raise NameError(f"Resource '{name}' is required but not registered.")

        provider = self._resource_providers[name]
        if isinstance(provider, ResourceDefinition):
            return provider.func
        return provider
~~~~~

#### Acts 2: 实现递归资源解析
接下来，我们升级 `BridgedComputeService` 以支持递归依赖注入。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/adapters.py
~~~~~
~~~~~python.old
    def _resolve_resource(self, inject_def: Inject, stack: ExitStack) -> Any:
        name = inject_def.resource_name

        # 1. Check Active Resources (Run Scope)
        if name in self.context.active_resources:
            return self.context.active_resources[name]

        # 2. Create Ephemeral Resource (Task Scope)
        # Note: We assume task-scoped resources here don't have complex recursive dependencies
        # for this adaptation layer.
        provider = self.context.resource_container.get_provider(name)

        if inspect.isgeneratorfunction(provider):
            gen = provider()
            try:
                resource = next(gen)
            except StopIteration:
                raise RuntimeError(f"Resource provider '{name}' yielded nothing.")

            # Register cleanup
            def cleanup():
                try:
                    next(gen)
                except StopIteration:
                    pass
                except Exception as e:
                    logger.warning(f"Error during teardown of resource '{name}': {e}")

            stack.callback(cleanup)
            return resource
        else:
            return provider()
~~~~~
~~~~~python.new
    def _resolve_resource(self, inject_def: Inject, stack: ExitStack) -> Any:
        name = inject_def.resource_name

        # 1. Check Active Resources (Run Scope)
        if name in self.context.active_resources:
            return self.context.active_resources[name]

        # 2. Create Ephemeral Resource (Task Scope)
        provider = self.context.resource_container.get_provider(name)

        # 3. Recursively Resolve Dependencies for the Provider
        sig = inspect.signature(provider)
        deps = {}
        for param_name, param in sig.parameters.items():
            if isinstance(param.default, Inject):
                deps[param_name] = self._resolve_resource(param.default, stack)

        # 4. Instantiate
        if inspect.isgeneratorfunction(provider):
            gen = provider(**deps)
            try:
                resource = next(gen)
            except StopIteration:
                raise RuntimeError(f"Resource provider '{name}' yielded nothing.")

            # Register cleanup
            def cleanup():
                try:
                    next(gen)
                except StopIteration:
                    pass
                except Exception as e:
                    logger.warning(f"Error during teardown of resource '{name}': {e}")

            stack.callback(cleanup)
            return resource
        else:
            return provider(**deps)
~~~~~

### 下一步建议
现在我们已经修复了两个核心问题。接下来的步骤是运行集成测试以验证修复是否有效。如果这些测试通过，我们将确信 VM 后端的 DI 系统已经具备了处理复杂依赖关系的能力。
