简要回答
好的，我将执行第二阶段和第三阶段，通过重构 `BridgedComputeService` 来实现智能参数绑定和依赖注入。

## [WIP] refactor(vm): 实现智能参数绑定与依赖注入

### 用户需求
修复计算适配层无法解析 `Inject` 对象（如数据库连接）和系统参数（如 `params_context`）的问题。

### 评论
当前 `BridgedComputeService` 仅支持简单的位置参数和关键字参数映射，无法处理现代 Cascade 任务定义中的高级特性。通过引入基于 `inspect` 的反射绑定机制，我们可以动态解析 `Inject` 默认值，并从 `ResourceContainer` 中按需加载资源，从而填补“Adapter Gap”。

### 目标
1.  在 `BridgedComputeService` 中引入 `inspect` 和 `Inject` 依赖。
2.  实现 `_bind_execution_arguments` 方法，支持位置/关键字映射、系统上下文注入和 `Inject` 解析。
3.  实现 `_resolve_resource` 方法，从上下文的 `active_resources` 或 `resource_container` 获取资源实例，并正确管理生命周期。
4.  重构 `_process_request` 方法，使用 `ExitStack` 管理任务级资源的生命周期，并使用新的绑定逻辑执行函数。

### 基本原理
我们采用“贪婪匹配 + 回退”的策略来绑定参数：优先使用显式传递的输入，其次匹配系统上下文（`params_context`），最后解析 `Inject` 定义的资源。为了防止资源泄漏（特别是像数据库连接这样的生成器资源），我们在每个请求的处理周期内引入 `ExitStack`。

### 标签
#intent/refine #flow/ready #priority/high #comp/vm #concept/di #scope/core #task/domain/compute #task/object/adapter-layer #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 导入必要依赖

我们需要 `inspect` 模块来检查函数签名，`ExitStack` 来管理资源清理，以及 `Inject` 类来识别注入点。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/adapters.py
~~~~~
~~~~~python.old
import asyncio
import inspect
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

from cascade.spec.physical.nodes import Token
from cascade.spec.runtime.storage import ObjectStore
from cascade.spec.runtime.interfaces import Executor
from ..registry import CodeRegistry
from cascade.spec.runtime import ComputeRequest, ExecutionContext

logger = logging.getLogger(__name__)
~~~~~
~~~~~python.new
import asyncio
import inspect
import logging
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

from cascade.spec.dsl.resources import Inject
from cascade.spec.physical.nodes import Token
from cascade.spec.runtime.storage import ObjectStore
from cascade.spec.runtime.interfaces import Executor
from ..registry import CodeRegistry
from cascade.spec.runtime import ComputeRequest, ExecutionContext

logger = logging.getLogger(__name__)
~~~~~

#### Acts 2: 重构 _process_request 和实现智能绑定

这是核心变更。我们将 `_process_request` 包裹在 `ExitStack` 中，并用新的 `_bind_execution_arguments` 和 `_resolve_resource` 替换旧的参数解析逻辑。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/adapters.py
~~~~~
~~~~~python.old
    async def _process_request(self, request: ComputeRequest) -> None:
        try:
            # 1. Resolve Inputs (Dereference Refs)
            # The ObjectStore protocol dictates that get() returns the actual object.
            inputs: Dict[str, Any] = {
                key: self.store.get(ref) for key, ref in request.input_refs.items()
            }
            args, kwargs = self._resolve_arguments(inputs)

            # 2. Resolve Code
            func = self.registry.get(request.code_hash)

            # 3. Construct Proxy Node for Executor
            # We inspect the function to determine execution properties
            is_async = inspect.iscoroutinefunction(func)

            # If the function is wrapped by @task, it might have a 'mode' attribute
            mode = getattr(func, "mode", "blocking")
            name = getattr(func, "__name__", "unknown_task")

            proxy_node = ProxyNode(
                name=name, definition=ProxyDef(is_async=is_async, mode=mode)
            )

            # 4. Delegate Execution to Runtime Executor
            # This allows the Runtime to manage thread pools, constraints, etc.
            result = await self.executor.execute(proxy_node, func, args, kwargs)  # type: ignore

        except Exception as e:
            logger.exception(
                f"Computation failed for request on code {request.code_hash}"
            )
            result = e
        finally:
            self._active_count -= 1

        # 5. Store Result and Prepare Token
        result_ref = self.store.put(result)
        result_token = Token(payload=result_ref, trace=request.trace)

        # 6. Report Completion
        await self.outbound_queue.put((request.reply_to_nid, result_token))

        # 7. Signal Wakeup
        if self._wakeup_event:
            self._wakeup_event.set()

    def _resolve_arguments(
        self, inputs: Dict[str, Any]
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # Helper to convert dict inputs back to *args and **kwargs
        args_map: Dict[int, Any] = {}
        kwargs: Dict[str, Any] = {}

        for k, v in inputs.items():
            if k.isdigit():
                args_map[int(k)] = v
            else:
                kwargs[k] = v

        args: List[Any] = []
        if args_map:
            max_idx = max(args_map.keys())
            args = [None] * (max_idx + 1)
            for idx, val in args_map.items():
                args[idx] = val

        return args, kwargs
~~~~~
~~~~~python.new
    async def _process_request(self, request: ComputeRequest) -> None:
        try:
            with ExitStack() as stack:
                # 1. Resolve Inputs (Dereference Refs)
                raw_inputs: Dict[str, Any] = {
                    key: self.store.get(ref) for key, ref in request.input_refs.items()
                }

                # 2. Resolve Code
                func = self.registry.get(request.code_hash)

                # 3. Smart Binding & Injection
                args, kwargs = self._bind_execution_arguments(func, raw_inputs, stack)

                # 4. Construct Proxy Node
                is_async = inspect.iscoroutinefunction(func)
                mode = getattr(func, "mode", "blocking")
                name = getattr(func, "__name__", "unknown_task")

                proxy_node = ProxyNode(
                    name=name, definition=ProxyDef(is_async=is_async, mode=mode)
                )

                # 5. Delegate Execution
                result = await self.executor.execute(proxy_node, func, args, kwargs)  # type: ignore

        except Exception as e:
            logger.exception(
                f"Computation failed for request on code {request.code_hash}"
            )
            result = e
        finally:
            self._active_count -= 1

        # 6. Store Result and Report
        result_ref = self.store.put(result)
        result_token = Token(payload=result_ref, trace=request.trace)

        await self.outbound_queue.put((request.reply_to_nid, result_token))

        if self._wakeup_event:
            self._wakeup_event.set()

    def _bind_execution_arguments(
        self, func: Any, raw_inputs: Dict[str, Any], stack: ExitStack
    ) -> Tuple[List[Any], Dict[str, Any]]:
        sig = inspect.signature(func)
        final_kwargs: Dict[str, Any] = {}

        # Pre-process inputs
        pos_inputs = {int(k): v for k, v in raw_inputs.items() if k.isdigit()}
        kw_inputs = {k: v for k, v in raw_inputs.items() if not k.isdigit()}

        for i, param in enumerate(sig.parameters.values()):
            # A. Try Keyword Input
            if param.name in kw_inputs:
                final_kwargs[param.name] = kw_inputs[param.name]
                continue

            # B. Try Positional Input
            if i in pos_inputs:
                final_kwargs[param.name] = pos_inputs[i]
                continue

            # C. System Context
            if param.name == "params_context":
                final_kwargs[param.name] = self.context.params
                continue

            # D. Dependency Injection
            if isinstance(param.default, Inject):
                final_kwargs[param.name] = self._resolve_resource(param.default, stack)
                continue

            # E. Default Value (implicitly handled by Python call if missing from final_kwargs)

        # Split into args/kwargs to respect POSITIONAL_ONLY
        call_args = []
        call_kwargs = {}

        for param in sig.parameters.values():
            if param.name in final_kwargs:
                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    call_args.append(final_kwargs[param.name])
                else:
                    call_kwargs[param.name] = final_kwargs[param.name]

        return call_args, call_kwargs

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

### 下一步建议

我们已经完成了所有的核心代码重构。逻辑已经覆盖了从基础架构连接到智能参数解析的全链路。

建议进行**第四阶段：验证与测试**。可以运行集成测试来验证修复是否生效。
- `pytest packages/cascade-library/tests/integration/test_helpers.py`
- `pytest packages/cascade-runtime/tests/integration/test_engine_inputs.py`
