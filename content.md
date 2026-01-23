好的，我将执行“修复基础”计划。我将创建 `SignatureBinder` 组件，并重构 `BridgedComputeService` 以使用它，从而修复参数绑定和资源注入的逻辑缺陷。

## [WIP] refactor(vm): 重构计算适配层的参数绑定与资源注入逻辑

### 错误分析
当前 `BridgedComputeService` 中的参数绑定算法（`_bind_execution_arguments`）是手动实现的，存在严重缺陷：
1.  **`*args` 处理错误**: 对于混合了位置参数、关键字参数和 `*args` 的函数，手动迭代容易丢失边界，导致参数被重复消费或错位。
2.  **注入逻辑耦合**: `Inject` 解析仅针对默认参数生效，无法处理通过 DSL 显式传递的 `Inject` 对象（即“穿透”问题）。
3.  **维护困难**: 复杂的绑定逻辑与业务逻辑耦合在 `adapters.py` 中，难以测试和扩展。

解决方案是引入 `SignatureBinder`，利用 Python 标准库 `inspect.Signature.bind` 来处理绑定，并在此基础上实现递归资源解析。

### 用户需求
修复 `cascade-vm` 中 `BridgedComputeService` 的参数绑定逻辑缺陷和资源注入穿透问题。具体要求包括：
1.  建立 `SignatureBinder` 组件，使用 `inspect.Signature.bind` 替代手动迭代。
2.  实现递归资源解析器，处理 `Inject` 对象。
3.  重构 `BridgedComputeService` 以使用新组件。

### 评论
通过引入 `SignatureBinder`，我们将利用 Python 标准库的强大功能来规范化参数绑定，并统一处理资源解析，显著提升系统的健壮性。这是一个“偿还技术债务”的关键步骤，为后续更复杂的计算任务打下坚实基础。

### 目标
1.  创建 `packages/cascade-vm/src/cascade/vm/compute/binding.py`，包含 `SignatureBinder` 类。
2.  在 `SignatureBinder` 中实现标准的参数绑定和递归资源解析逻辑。
3.  修改 `packages/cascade-vm/src/cascade/vm/compute/adapters.py`，移除旧的绑定逻辑，改为使用 `SignatureBinder`。

### 基本原理
-   **标准库优于手写逻辑**: `inspect.Signature.bind` 是处理 Python 函数参数调用的权威方式，能够正确处理位置参数、关键字参数、默认值和变长参数。
-   **关注点分离**: 将复杂的绑定和注入逻辑从 `ComputeService` 中剥离，使代码更易于测试和维护。
-   **统一资源解析**: 通过递归扫描 `BoundArguments`，确保无论资源是通过默认值注入还是显式传递，都能被正确解析。

### 标签
#intent/refine #flow/ready #priority/high
#comp/runtime #concept/executor
#ai/instruct
#task/domain/runtime
#task/object/compute-adapter
#task/action/refactor
#task/state/begin

---

### Script

#### Acts 1: 创建 SignatureBinder 组件

我们将创建一个新的模块 `binding.py`，封装参数绑定和资源解析的核心逻辑。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/compute/binding.py
~~~~~
~~~~~python
import inspect
import logging
from contextlib import ExitStack
from typing import Any, Dict, List, Tuple, Callable

from cascade.spec.dsl.resources import Inject
from cascade.spec.runtime import ExecutionContext
from cascade.bus.events import ResourceAcquired, ResourceReleased

logger = logging.getLogger(__name__)


class SignatureBinder:
    def __init__(self, func: Callable, context: ExecutionContext):
        self.func = func
        self.sig = inspect.signature(func)
        self.context = context

    def bind_and_resolve(
        self, raw_inputs: Dict[str, Any], stack: ExitStack
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # 1. Input Standardization
        args_list = []
        kwargs_dict = {}

        # Extract positional args (integer keys)
        pos_keys = sorted([int(k) for k in raw_inputs.keys() if k.isdigit()])
        if pos_keys:
            max_idx = pos_keys[-1]
            # Fill logic: assume inputs are dense 0..N
            args_list = [raw_inputs.get(str(i)) for i in range(max_idx + 1)]

        # Extract keyword args
        kwargs_dict = {k: v for k, v in raw_inputs.items() if not k.isdigit()}

        # 2. System Parameter Injection
        # Ensure 'params_context' is available if requested by signature
        if "params_context" in self.sig.parameters and "params_context" not in kwargs_dict:
            kwargs_dict["params_context"] = self.context.params

        # 3. Bind
        # This handles *args and **kwargs mapping automatically using Python's standard logic
        try:
            bound = self.sig.bind(*args_list, **kwargs_dict)
        except TypeError as e:
            # Add context to error
            raise TypeError(f"Failed to bind arguments for function '{self.func.__name__}': {e}") from e

        # Apply defaults (including Inject defaults)
        bound.apply_defaults()

        # 4. Recursive Resolution
        # We iterate over bound.arguments and resolve any Inject instances
        for name, value in bound.arguments.items():
            resolved = self._resolve_value(value, stack)
            # bound.arguments is a MutableMapping, we can update it in place
            if resolved is not value:
                bound.arguments[name] = resolved

        # bound.args and bound.kwargs reflect the updated bound.arguments
        return bound.args, bound.kwargs

    def _resolve_value(self, value: Any, stack: ExitStack) -> Any:
        if isinstance(value, Inject):
            return self._resolve_resource(value, stack)
        return value

    def _resolve_resource(self, inject_def: Inject, stack: ExitStack) -> Any:
        name = inject_def.resource_name

        # 1. Check Active Resources (Run Scope)
        if name in self.context.active_resources:
            return self.context.active_resources[name]

        # 2. Create Ephemeral Resource (Task Scope)
        # Assuming resource_container is available on context
        if not hasattr(self.context, "resource_container"):
             raise RuntimeError("Context missing 'resource_container', cannot resolve resources.")
             
        provider = self.context.resource_container.get_provider(name)

        # 3. Recursively Resolve Dependencies for the Provider
        sig = inspect.signature(provider)
        deps = {}
        for param_name, param in sig.parameters.items():
            if isinstance(param.default, Inject):
                deps[param_name] = self._resolve_resource(param.default, stack)

        # Access bus for event publishing
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

            def cleanup_event():
                if bus:
                    bus.publish(ResourceReleased(run_id=run_id, resource_name=name))

            stack.callback(cleanup_event)
            return resource
~~~~~

#### Acts 2: 更新 BridgedComputeService

我们将更新 `adapters.py`，移除旧的 `_bind_execution_arguments` 和 `_resolve_resource` 方法，并使用 `SignatureBinder` 来处理请求。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/adapters.py
~~~~~
~~~~~python.old
from cascade.spec.runtime.interfaces import Executor
from ..registry import CodeRegistry
from cascade.spec.runtime import ComputeRequest, ExecutionContext
from cascade.bus.events import ResourceAcquired, ResourceReleased

logger = logging.getLogger(__name__)
~~~~~
~~~~~python.new
from cascade.spec.runtime.interfaces import Executor
from ..registry import CodeRegistry
from cascade.spec.runtime import ComputeRequest, ExecutionContext
from cascade.bus.events import ResourceAcquired, ResourceReleased
from .binding import SignatureBinder

logger = logging.getLogger(__name__)
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/adapters.py
~~~~~
~~~~~python.old
                # 3. Smart Binding & Injection
                args, kwargs = self._bind_execution_arguments(func, raw_inputs, stack)

                # 4. Construct Proxy Node
~~~~~
~~~~~python.new
                # 3. Smart Binding & Injection
                binder = SignatureBinder(func, self.context)
                args, kwargs = binder.bind_and_resolve(raw_inputs, stack)

                # 4. Construct Proxy Node
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/adapters.py
~~~~~
~~~~~python.old
        if self._wakeup_event:
            self._wakeup_event.set()

    def _bind_execution_arguments(
        self, func: Any, raw_inputs: Dict[str, Any], stack: ExitStack
    ) -> Tuple[List[Any], Dict[str, Any]]:
        sig = inspect.signature(func)

        # Prepare Inputs
        # pos_inputs: index -> value
        pos_inputs = {int(k): v for k, v in raw_inputs.items() if k.isdigit()}
        # kw_inputs: name -> value (mutable, we will pop from it)
        kw_inputs = {k: v for k, v in raw_inputs.items() if not k.isdigit()}

        final_args: List[Any] = []
        final_kwargs: Dict[str, Any] = {}

        next_pos_idx = 0

        for param in sig.parameters.values():
            # --- 1. Special Handling: Inject / System Context ---
            # These are handled regardless of Parameter Kind (except maybe VAR_*)
            injected_value = None
            has_injection = False

            if param.name == "params_context":
                injected_value = self.context.params
                has_injection = True
            elif isinstance(param.default, Inject):
                injected_value = self._resolve_resource(param.default, stack)
                has_injection = True

            if has_injection:
                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    final_args.append(injected_value)
                elif param.kind in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                ):
                    final_kwargs[param.name] = injected_value
                # VAR_POSITIONAL / VAR_KEYWORD usually don't have Inject defaults, ignoring.
                continue

            # --- 2. Standard Parameter Handling ---

            if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                # Must take from positional inputs
                if next_pos_idx in pos_inputs:
                    final_args.append(pos_inputs[next_pos_idx])
                    next_pos_idx += 1
                elif param.default is not inspect.Parameter.empty:
                    final_args.append(param.default)
                else:
                    # Let Python raise the error if missing
                    pass

            elif param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                # Priority: Keyword -> Positional
                if param.name in kw_inputs:
                    final_kwargs[param.name] = kw_inputs.pop(param.name)
                elif next_pos_idx in pos_inputs:
                    final_args.append(pos_inputs[next_pos_idx])
                    next_pos_idx += 1
                elif param.default is not inspect.Parameter.empty:
                    # Python will use default
                    pass

            elif param.kind == inspect.Parameter.VAR_POSITIONAL:  # *args
                # Consume ALL remaining positional inputs
                # We need to find all keys >= next_pos_idx
                sorted_keys = sorted(
                    [k for k in pos_inputs.keys() if k >= next_pos_idx]
                )
                for k in sorted_keys:
                    final_args.append(pos_inputs[k])
                # Advance index to avoid re-consumption
                if sorted_keys:
                    next_pos_idx = sorted_keys[-1] + 1

            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                if param.name in kw_inputs:
                    final_kwargs[param.name] = kw_inputs.pop(param.name)
                # else default or error

            elif param.kind == inspect.Parameter.VAR_KEYWORD:  # **kwargs
                # Consume ALL remaining keyword inputs
                # kw_inputs is being popped, so whatever is left goes here
                final_kwargs.update(kw_inputs)
                kw_inputs.clear()

        return final_args, final_kwargs

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
~~~~~python.new
        if self._wakeup_event:
            self._wakeup_event.set()
~~~~~

### 下一步建议
我们已经重构了核心的计算适配层。下一步建议：
1.  **验证测试**: 运行相关测试（如 `test_sql.py` 和 `test_helpers.py`）以验证重构是否成功修复了参数绑定和资源注入问题，并确保没有引入回归。
2.  **清理**: 如果 `adapters.py` 还有未使用的 import（如 `Inject`），可以进一步清理。
3.  **扩展**: 考虑在 `SignatureBinder` 中增加对更多类型注解的支持，或优化资源解析的缓存策略。
