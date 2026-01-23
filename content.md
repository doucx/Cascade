简要回答
测试失败是因为 `BridgedComputeService` 在创建和销毁资源时**没有发布相应的生命周期事件** (`ResourceAcquired`, `ResourceReleased`)。虽然资源本身的创建逻辑（递归注入）已经修复，但 VM 后端需要显式地通过 EventBus 广播这些事件，以便测试（以及遥测系统）能够观测到资源的生命周期。

我们将修改 `BridgedComputeService._resolve_resource` 方法，使其在资源实例化成功后发布 `ResourceAcquired` 事件，并在资源清理时发布 `ResourceReleased` 事件。

## [WIP] fix(vm): publish resource lifecycle events in bridged compute service

### 错误分析
测试 `test_resource_events` 失败，断言错误 `AssertionError: assert 'config' in []` 表明事件列表中没有任何 `ResourceAcquired` 事件。这证实了资源虽然被正确创建和使用（stdout 显示了 SETUP/TEARDOWN 日志），但 VM 适配层遗漏了事件发布的逻辑。

### 用户需求
确保 VM 后端在处理资源注入时，能够像 Graph 后端一样发布完整的生命周期事件，以满足可观测性和测试需求。

### 评论
这是一个“一致性”修复。VM 后端必须模仿 Graph 后端的行为，包括副作用（如事件发布）。我们可以通过 `ExecutionContext` 间接访问 `ResourceContainer` 上的 `EventBus` 来实现这一点，而无需修改大量构造函数签名。

### 目标
1.  在 `packages/cascade-vm/src/cascade/vm/compute/adapters.py` 中引入 `ResourceAcquired` 和 `ResourceReleased` 事件。
2.  修改 `_resolve_resource` 方法，从上下文获取 EventBus，并在适当的时机发布事件。

### 基本原理
资源容器 (`ResourceContainer`) 持有 `EventBus`。`BridgedComputeService` 持有 `ExecutionContext`，而后者持有 `ResourceContainer`。我们可以利用这个链条来获取 Bus 并发布事件。对于非生成器（普通函数）资源，我们也应注册一个仅用于发布 Released 事件的 cleanup 回调，以保持语义完整性。

### 标签
#intent/fix #flow/ready #priority/medium #comp/vm #concept/observability #scope/core #ai/instruct #task/domain/runtime #task/object/resource-events #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 添加事件发布逻辑
修改 `BridgedComputeService` 以发布资源事件。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/adapters.py
~~~~~
~~~~~python.old
from cascade.spec.dsl.resources import Inject
from cascade.spec.physical.nodes import Token
from cascade.spec.runtime.storage import ObjectStore
from cascade.spec.runtime.interfaces import Executor
from ..registry import CodeRegistry
from cascade.spec.runtime import ComputeRequest, ExecutionContext

logger = logging.getLogger(__name__)
~~~~~
~~~~~python.new
from cascade.spec.dsl.resources import Inject
from cascade.spec.physical.nodes import Token
from cascade.spec.runtime.storage import ObjectStore
from cascade.spec.runtime.interfaces import Executor
from ..registry import CodeRegistry
from cascade.spec.runtime import ComputeRequest, ExecutionContext
from cascade.bus.events import ResourceAcquired, ResourceReleased

logger = logging.getLogger(__name__)
~~~~~

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

        # Access bus for event publishing
        # ResourceContainer has the bus, and Context has the container
        bus = getattr(self.context.resource_container, "bus", None)
        run_id = self.context.run_id

        # 4. Instantiate
        resource = None
        if inspect.isgeneratorfunction(provider):
            gen = provider(**deps)
            try:
                resource = next(gen)
            except StopIteration:
                raise RuntimeError(f"Resource provider '{name}' yielded nothing.")

            if bus:
                bus.publish(ResourceAcquired(run_id=run_id, resource_name=name))

            # Register cleanup
            def cleanup():
                try:
                    next(gen)
                except StopIteration:
                    pass
                except Exception as e:
                    logger.warning(f"Error during teardown of resource '{name}': {e}")
                
                if bus:
                    bus.publish(ResourceReleased(run_id=run_id, resource_name=name))

            stack.callback(cleanup)
            return resource
        else:
            resource = provider(**deps)
            
            if bus:
                bus.publish(ResourceAcquired(run_id=run_id, resource_name=name))

            # Even for non-generators, we register a callback to emit the Released event
            # when the scope (stack) exits.
            def cleanup_event():
                if bus:
                    bus.publish(ResourceReleased(run_id=run_id, resource_name=name))
            
            stack.callback(cleanup_event)
            return resource
~~~~~

### 下一步建议
这次修复后，`ResourceAcquired` 和 `ResourceReleased` 事件应该能正确发出，从而让 `test_resource_events` 通过。请运行测试进行验证。
