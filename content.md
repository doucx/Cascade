好的，我们已经成功进入了 **RED** 状态。测试失败的原因正如预期：`VMExecutionStrategy` 目前是一个线性的“一次性执行器”，它将任务返回的 `Jump` 对象错误地当作最终结果，而没有实现处理控制流循环的“trampoline”机制。

现在，我们将遵循**方案 A**，在 `VMExecutionStrategy` 中实现这个循环，让测试变绿。

## [WIP] feat(engine): 在 VM 策略中实现 TCO 循环以处理 Jump 信号

### 用户需求
修改 `cascade-engine/src/cascade/runtime/strategies/vm.py` 文件，使其能够正确处理任务返回的 `cs.Jump` 对象，实现尾调用优化（TCO）和状态机循环。

### 评论
这次重构的核心是将 `VMExecutionStrategy.execute` 方法从一个简单的线性流程，改造为一个包含 `while` 循环的状态机。这个循环将负责解释 `Jump` 信号，更新下一个迭代的输入参数，并重新调用 VM，从而模拟 TCO。为了性能，我们还将引入一个本地编译缓存，避免在循环中重复编译相同的 `LazyResult` 结构。

### 目标
1.  在 `VMExecutionStrategy.execute` 中实现一个 `while True` 循环。
2.  在循环内部，检查 VM 的返回值。
3.  如果返回的是 `Jump` 对象，则根据其 `target_key` 找到下一个要执行的任务，并将其 `data` 作为下一次循环的输入。
4.  如果 `Jump` 的目标是退出，或返回值不是 `Jump`，则终止循环并返回最终结果。
5.  实现一个简单的编译缓存，以优化循环性能。

### 基本原理
通过将控制流逻辑保留在 `Strategy` 层，我们维持了 `VirtualMachine` 的纯粹性——它只关心执行指令集。`Strategy` 扮演了“协调者”的角色，它驱动 VM 并解释 VM 的高级输出（如 `Jump` 信号），这符合我们分层架构的设计理念。

### 标签
#intent/refine #flow/draft #priority/critical #comp/engine #concept/control-flow #scope/core #ai/instruct #task/domain/core #task/object/vm-strategy #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修改 `VMExecutionStrategy` 以支持 TCO 循环

我们将用一个包含 `while` 循环和 `Jump` 处理逻辑的新版本，替换掉 `vm.py` 中现有的 `execute` 方法。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        # 1. Frontend: Compile LazyResult to GraphIR
        # Returns CompilationResult(ir, symbol_table)
        compilation_result = Frontend.compile(target)
        graph_ir = compilation_result.ir
        symbol_table = compilation_result.symbol_table

        # 2. Optimizer: Schedule GraphIR to ExecutionPlan
        execution_plan = Optimizer.optimize(graph_ir)

        # 3. Backend: Generate Blueprint from GraphIR + ExecutionPlan
        blueprint = Backend.compile(graph_ir, execution_plan)

        # 4. Runtime: Execute Blueprint on VM
        vm = VirtualMachine(
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            wakeup_event=self.wakeup_event,
        )
        
        # Configure Middleware Pipeline (Order matters!)
        # Onion Layer:
        # 1. Observability (Outermost): Logs everything including retries? 
        #    Note: Does Observability log individual attempts? 
        #    If Retry is inner, Observability sees one "Task" execution which might take long.
        #    If Retry is outer, Observability sees each attempt as a "Task"? No, that's not right.
        #    Correct nesting:
        #    [Observability] -> [Retry] -> [Constraints] -> [Resources] -> [Resolve] -> [Core]
        #    This way, Observability records the *Total* time for the task (including retries).
        #    The RetryMiddleware itself should emit TaskRetrying events (TODO).
        
        vm.set_middlewares([
            ObservabilityMiddleware(self.bus, run_id),
            RetryMiddleware(),
            ConstraintMiddleware(self.constraint_manager),
            ResourceLifecycleMiddleware(self.resource_manager),
            ArgumentResolutionMiddleware(active_resources, params),
        ])

        if isinstance(target, MappedLazyResult):
            initial_args = []
            initial_kwargs = dict(target.mapping_kwargs)
        else:
            initial_args = list(target.args)
            initial_kwargs = dict(target.kwargs)
        
        return await vm.execute(
            blueprint,
            symbol_table=symbol_table,
            initial_args=initial_args,
            initial_kwargs=initial_kwargs,
        )
~~~~~
~~~~~python.new
    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        current_target = target
        next_input_overrides: Optional[Dict[str, Any]] = None
        local_compilation_cache: Dict[str, Any] = {}

        while True:
            # 1. Compilation Stage (with caching)
            if current_target._uuid in local_compilation_cache:
                compilation_result, blueprint = local_compilation_cache[current_target._uuid]
            else:
                compilation_result = Frontend.compile(current_target)
                graph_ir = compilation_result.ir
                execution_plan = Optimizer.optimize(graph_ir)
                blueprint = Backend.compile(graph_ir, execution_plan)
                local_compilation_cache[current_target._uuid] = (compilation_result, blueprint)

            # 2. Prepare Inputs for this Iteration
            # Start with static bindings from the LazyResult
            if isinstance(current_target, MappedLazyResult):
                initial_args: List[Any] = []
                initial_kwargs: Dict[str, Any] = dict(current_target.mapping_kwargs)
            else:
                initial_args = list(current_target.args)
                initial_kwargs = dict(current_target.kwargs)

            # Apply overrides from the previous Jump signal
            if next_input_overrides:
                for key, value in next_input_overrides.items():
                    if key.isdigit():
                        idx = int(key)
                        while len(initial_args) <= idx:
                            initial_args.append(None)
                        initial_args[idx] = value
                    else:
                        initial_kwargs[key] = value
                next_input_overrides = None  # Consume overrides

            # 3. VM Execution
            vm = VirtualMachine(
                resource_manager=self.resource_manager,
                constraint_manager=self.constraint_manager,
                wakeup_event=self.wakeup_event,
            )
            
            vm.set_middlewares([
                ObservabilityMiddleware(self.bus, run_id),
                RetryMiddleware(),
                ConstraintMiddleware(self.constraint_manager),
                ResourceLifecycleMiddleware(self.resource_manager),
                ArgumentResolutionMiddleware(active_resources, params),
            ])

            result = await vm.execute(
                blueprint,
                symbol_table=compilation_result.symbol_table,
                initial_args=initial_args,
                initial_kwargs=initial_kwargs,
            )

            # 4. Result Interpretation (The Trampoline Logic)
            if isinstance(result, Jump):
                selector = getattr(current_target, '_jump_selector', None)
                if not selector:
                    raise RuntimeError(
                        f"Task '{current_target.task.name}' returned a Jump signal but has no bound 'select_jump'."
                    )
                
                next_target = selector.routes.get(result.target_key)
                
                if next_target is None:
                    # Loop exit condition (e.g., jump_selector has {'exit': None})
                    return result.data
                
                # Prepare for the next iteration
                current_target = next_target
                if isinstance(result.data, dict):
                    next_input_overrides = result.data
                elif result.data is not None:
                    # Positional override for single return value
                    next_input_overrides = {"0": result.data}
                else:
                    next_input_overrides = {}
                
                # Continue to the next loop iteration
                continue
            else:
                # Normal termination, not a Jump signal
                return result
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
from cascade.spec.lazy_types import MappedLazyResult
from cascade.spec.blueprint import Call, MapCall
~~~~~
~~~~~python.new
from cascade.spec.lazy_types import MappedLazyResult
from cascade.spec.blueprint import Call, MapCall
from cascade.spec.jump import Jump
from typing import List, Optional
~~~~~

### 下一步建议
现在，我们已经将 `VMExecutionStrategy` 改造为了一个能够处理 `Jump` 信号的循环执行器。请再次运行测试套件，这次我们期望看到所有测试都通过。
