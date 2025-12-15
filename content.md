这是对上一轮执行结果的修复计划。

## [WIP] fix: 修复 LocalExecutor 测试及资源覆写逻辑

### 错误分析
1.  **`tests/test_adapters.py` 失败**:
    *   原因: `LocalExecutor.execute` 的签名在上一轮重构中增加了 `resource_context` 参数，但旧的单元测试未同步更新，导致 `TypeError`。
    *   修复: 更新测试调用，传入空的 `resource_context={}`。

2.  **`tests/test_di_and_resources.py` 失败**:
    *   原因: 在 `test_resource_override` 中，传递给 `override_resource` 的对象是经 `@resource` 装饰后的 `ResourceDefinition` 实例，而非原始函数。`Engine.override_resource_provider` 直接存储了该实例，导致后续 `inspect.signature` 检查时抛出 `TypeError: ... is not a callable object`。
    *   修复: 修改 `Engine.override_resource_provider` 方法，增加类型检查逻辑。如果传入的是 `ResourceDefinition` 实例，自动解包并存储其内部的 `.func` 属性。

### 用户需求
修复当前的测试失败，确保依赖注入系统的核心逻辑和测试工具能正常工作。

### 评论
这些是重构过程中常见的集成问题。修复它们将验证我们的 DI 系统能够正确处理各种输入形式（原始函数或装饰后的对象），提升系统的健壮性。

### 目标
1.  更新 `tests/test_adapters.py` 以适配新的执行器接口。
2.  增强 `Engine.override_resource_provider` 的容错性，使其能处理 `ResourceDefinition`。

### 基本原理
通过在 `Engine` 层做适配，我们可以简化 `override_resource` 的使用，让用户在测试中既可以传入普通函数，也可以传入 `@resource` 对象，提供更好的开发者体验 (DX)。

### 标签
#intent/fix #flow/ready #priority/high
#comp/runtime #comp/tests
#concept/dependency-injection
#scope/core
#task/domain/core #task/object/dependency-injection #task/action/fix
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 修复 LocalExecutor 测试

更新旧的测试用例以匹配新的 API 签名。

~~~~~act
patch_file
tests/test_adapters.py
~~~~~
~~~~~python
    upstream_results = {
        "x": 5,
        "y": 10
    }
    
    executor = LocalExecutor()
    result = executor.execute(node_add, graph, upstream_results)
    
    assert result == 15
~~~~~
~~~~~python
    upstream_results = {
        "x": 5,
        "y": 10
    }
    
    executor = LocalExecutor()
    result = executor.execute(node_add, graph, upstream_results, resource_context={})
    
    assert result == 15
~~~~~

#### Acts 2: 增强 Engine 的资源覆写逻辑

修改 `override_resource_provider` 以支持 `ResourceDefinition` 对象。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def get_resource_provider(self, name: str) -> Callable:
        return self._resource_providers[name]

    def override_resource_provider(self, name: str, new_provider: Callable):
        self._resource_providers[name] = new_provider

    def run(self, target: LazyResult, params: Optional[Dict[str, Any]] = None) -> Any:
~~~~~
~~~~~python
    def get_resource_provider(self, name: str) -> Callable:
        return self._resource_providers[name]

    def override_resource_provider(self, name: str, new_provider: Any):
        # Unwrap ResourceDefinition if provided
        if isinstance(new_provider, ResourceDefinition):
            new_provider = new_provider.func
        self._resource_providers[name] = new_provider

    def run(self, target: LazyResult, params: Optional[Dict[str, Any]] = None) -> Any:
~~~~~

### 下一步建议
运行测试 `pytest`，确认所有测试（包括新写的 DI 测试）全部通过。之后，我们将继续进行 DI 系统的完善工作，添加 `ResourceAcquired` 和 `ResourceReleased` 事件以提升可观测性。
