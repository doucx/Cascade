## [WIP] refactor(runtime): 在 Engine 中实现尾调用优化 (TCO) 与分级资源管理

### 错误分析
无（这是基于 TDD 的实现，针对已知的失败测试）。

### 用户需求
1.  让 `Engine` 能够自动展开并执行任务返回的 `LazyResult`，通过循环而非递归实现，以支持无限深度的 Agent 循环。
2.  实现基于 Scope 的资源管理，确保在 TCO 循环中，`scope="task"` 的资源能被及时回收，防止资源泄漏。

### 评论
这是一个核心架构变更。它将 `Engine.run` 从单一的“构建-执行”过程转变为一个“持续求值”的循环。这不仅解决了递归深度问题，也为未来的长时间运行 Agent 奠定了基础。

### 目标
1.  修改 `Engine.register` 以保留 `ResourceDefinition` 元数据（scope）。
2.  重构 `Engine.run`，引入 `while` 循环处理返回的 `LazyResult`。
3.  重构资源设置逻辑，区分 `run_stack` (全局) 和 `step_stack` (局部)。

### 基本原理
通过将执行逻辑包裹在 `while True` 循环中，我们能够检测每次执行的结果。如果结果是 `LazyResult`，我们将其作为新的 `target` 进入下一次迭代，而不是直接返回。同时，我们在每次迭代中引入一个独立的 `ExitStack` 来管理局部资源，确保单步资源在迭代结束时释放，而全局资源在整个 `run` 中保持活跃。

## 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/engine-loop #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 Engine 实现以支持 TCO 和 Scope 资源

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
from typing import Any, Dict, Optional, Generator, Callable, List, Type
from uuid import uuid4
from contextlib import ExitStack

from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.spec.constraint import GlobalConstraint
~~~~~
~~~~~python
from typing import Any, Dict, Optional, Generator, Callable, List, Type, Union
from uuid import uuid4
from contextlib import ExitStack

from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.constraint import GlobalConstraint
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        self._wakeup_event = asyncio.Event()
        self.constraint_manager.set_wakeup_callback(self._wakeup_event.set)

        self._resource_providers: Dict[str, Callable] = {}

        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
~~~~~
~~~~~python
        self._wakeup_event = asyncio.Event()
        self.constraint_manager.set_wakeup_callback(self._wakeup_event.set)

        self._resource_providers: Dict[str, Union[Callable, ResourceDefinition]] = {}

        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def register(self, resource_def: ResourceDefinition):
        self._resource_providers[resource_def.name] = resource_def.func

    def get_resource_provider(self, name: str) -> Callable:
        return self._resource_providers[name]

    def override_resource_provider(self, name: str, new_provider: Any):
        if isinstance(new_provider, ResourceDefinition):
            new_provider = new_provider.func
        self._resource_providers[name] = new_provider

    async def run(self, target: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
        start_time = time.time()

        # Robustly determine target name
        if hasattr(target, "task"):
            target_name = getattr(target.task, "name", "unknown")
        elif hasattr(target, "factory"):
            target_name = f"map({getattr(target.factory, 'name', 'unknown')})"
        else:
            target_name = "unknown"

        # Initialize State Backend first (no side effects)
        state_backend = self.state_backend_cls(run_id=run_id)

        try:
            # 1. Establish Infrastructure Connection FIRST
            # This ensures we are ready to transmit telemetry and receive constraints
            # BEFORE we announce the run starting or execute any logic.
            if self.connector:
                await self.connector.connect()
                self.bus.publish(ConnectorConnected(run_id=run_id))
                # Subscribe to constraint updates immediately.
                # This gives the connector a chance to receive retained messages (like global pause)
                # before we enter the execution loop.
                await self.connector.subscribe(
                    "cascade/constraints/#", self._on_constraint_update
                )

            # 2. Publish Lifecycle Event
            # Now that the connector is active, this event will be successfully transmitted.
            self.bus.publish(
                RunStarted(run_id=run_id, target_tasks=[target_name], params=params or {})
            )

            with ExitStack() as stack:
                initial_graph = build_graph(target)
                required_resources = self._scan_for_resources(initial_graph)
                active_resources = self._setup_resources(
                    required_resources, stack, run_id
                )

                final_result = await self._execute_graph(
                    target, params or {}, active_resources, run_id, state_backend
                )

            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(run_id=run_id, status="Succeeded", duration=duration)
            )
            return final_result

        except Exception as e:
~~~~~
~~~~~python
    def register(self, resource_def: ResourceDefinition):
        # We store the full ResourceDefinition to preserve metadata like scope.
        self._resource_providers[resource_def.name] = resource_def

    def get_resource_provider(self, name: str) -> Callable:
        provider = self._resource_providers[name]
        if isinstance(provider, ResourceDefinition):
            return provider.func
        return provider

    def override_resource_provider(self, name: str, new_provider: Any):
        # When overriding, we might lose metadata if a raw function is passed,
        # but that's acceptable for testing overrides.
        self._resource_providers[name] = new_provider

    async def run(self, target: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
        start_time = time.time()

        # Robustly determine initial target name for logging
        if hasattr(target, "task"):
            target_name = getattr(target.task, "name", "unknown")
        elif hasattr(target, "factory"):
            target_name = f"map({getattr(target.factory, 'name', 'unknown')})"
        else:
            target_name = "unknown"

        # Initialize State Backend first (no side effects)
        state_backend = self.state_backend_cls(run_id=run_id)

        try:
            # 1. Establish Infrastructure Connection FIRST
            if self.connector:
                await self.connector.connect()
                self.bus.publish(ConnectorConnected(run_id=run_id))
                await self.connector.subscribe(
                    "cascade/constraints/#", self._on_constraint_update
                )

            # 2. Publish Lifecycle Event
            self.bus.publish(
                RunStarted(
                    run_id=run_id, target_tasks=[target_name], params=params or {}
                )
            )

            # TCO Loop: We keep executing as long as the result is a LazyResult
            current_target = target
            
            # The global stack holds "run" scoped resources
            with ExitStack() as run_stack:
                active_resources: Dict[str, Any] = {}

                while True:
                    # The step stack holds "task" (step) scoped resources
                    with ExitStack() as step_stack:
                        # 1. Build graph for current target
                        graph = build_graph(current_target)
                        
                        # 2. Setup Resources (mixed scope)
                        required_resources = self._scan_for_resources(graph)
                        self._setup_resources(
                            required_resources, 
                            active_resources, 
                            run_stack, 
                            step_stack, 
                            run_id
                        )

                        # 3. Execute
                        result = await self._execute_graph(
                            current_target, params or {}, active_resources, run_id, state_backend
                        )

                    # 4. Check for Tail Call (LazyResult)
                    if isinstance(result, (LazyResult, MappedLazyResult)):
                        current_target = result
                        # Continue loop. 
                        # 'step_stack' has exited, releasing step-scoped resources.
                        # 'run_stack' remains open.
                        # 'active_resources' still holds run-scoped instances.
                    else:
                        final_result = result
                        break

            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(run_id=run_id, status="Succeeded", duration=duration)
            )
            return final_result

        except Exception as e:
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def _setup_resources(
        self, required_names: set[str], stack: ExitStack, run_id: str
    ) -> Dict[str, Any]:
        active: Dict[str, Any] = {}

        def get_or_create(name: str):
            if name in active:
                return active[name]
            provider = self._resource_providers.get(name)
            if not provider:
                raise NameError(f"Resource '{name}' is required but not registered.")
            sig = inspect.signature(provider)
            deps = {
                p_name: get_or_create(p.default.resource_name)
                for p_name, p in sig.parameters.items()
                if isinstance(p.default, Inject)
            }
            gen = provider(**deps)
            instance = next(gen)
            active[name] = instance
            self.bus.publish(ResourceAcquired(run_id=run_id, resource_name=name))
            stack.callback(self._teardown_resource, gen, run_id, name)
            return instance

        for name in required_names:
            get_or_create(name)
        return active
~~~~~
~~~~~python
    def _setup_resources(
        self,
        required_names: set[str],
        active_resources: Dict[str, Any],
        run_stack: ExitStack,
        step_stack: ExitStack,
        run_id: str,
    ) -> None:
        """
        Initializes required resources that are not yet active.
        Decides whether to put them in run_stack or step_stack based on scope.
        Updates active_resources in-place.
        """

        def get_or_create(name: str):
            if name in active_resources:
                return active_resources[name]
            
            provider_entry = self._resource_providers.get(name)
            if not provider_entry:
                raise NameError(f"Resource '{name}' is required but not registered.")
            
            # Determine scope and func
            scope = "run"
            func = provider_entry
            if isinstance(provider_entry, ResourceDefinition):
                scope = provider_entry.scope
                func = provider_entry.func
            
            # Recursive dependency resolution
            sig = inspect.signature(func)
            deps = {
                p_name: get_or_create(p.default.resource_name)
                for p_name, p in sig.parameters.items()
                if isinstance(p.default, Inject)
            }
            
            # Instantiate
            gen = func(**deps)
            instance = next(gen)
            
            # Register in active dict
            active_resources[name] = instance
            self.bus.publish(ResourceAcquired(run_id=run_id, resource_name=name))
            
            # Register teardown in appropriate stack
            target_stack = step_stack if scope == "task" else run_stack
            
            def cleanup():
                self._teardown_resource(gen, run_id, name)
                # Important: remove from active_resources so it can be re-created if needed later
                active_resources.pop(name, None)

            target_stack.callback(cleanup)
            return instance

        for name in required_names:
            get_or_create(name)
~~~~~

### 下一步建议
运行测试。预期所有测试（包括之前的和新加的）都应该通过。
