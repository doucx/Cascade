好的，分析完毕。两个失败点都非常清晰，并且暴露了我上一个补丁中的逻辑缺陷。

1.  **`TypeError`**: 第一个测试失败是因为我的代码过于严格，强制要求 `cs.Jump` 的 `data` 负载必须是字典。`counter` 任务返回的是一个整数，这是一种完全合法的使用方式，我的代码没有正确处理。
2.  **无限循环**: 第二个测试进入死循环，是因为在准备下一次循环时，我只传递了 `Jump` 信号中的**增量**参数（如 `{'acc': 1}`），而完全**丢弃**了任务原始的其他参数（如 `limit=3`）。这导致 `accumulator` 任务在第二次调用时缺少 `limit` 参数，使得 `acc < limit` 的判断逻辑失效，从而无限循环。

我将生成一个修复计划，同时解决这两个问题。

## [WIP] fix(engine): 修复 VM 策略的 TCO 循环逻辑

### 错误分析
1.  **类型错误**: `VMExecutionStrategy` 中的 TCO 循环逻辑在处理 `cs.Jump` 信号时，错误地假设其 `data` 负载永远是字典，当接收到单个值（如整数）时会抛出 `TypeError`。
2.  **状态丢失**: 在准备 TCO 循环的下一次迭代时，策略未能将 `Jump` 信号中的覆盖参数与任务原始的参数进行合并。这导致了状态丢失（例如，`limit` 参数丢失），引发了无限循环。

### 用户需求
修复 `cascade-engine/src/cascade/runtime/strategies/vm.py`，使其 TCO 循环能够：
1.  正确处理非字典类型的 `Jump` 数据负载。
2.  在循环迭代之间正确地合并和传递所有任务参数。

### 评论
这次修复至关重要，它使 `VMExecutionStrategy` 的 TCO 实现更加健壮，并与旧的、经过验证的 `GraphExecutionStrategy` 的行为对齐。通过正确地合并状态，我们确保了有状态的循环（如 `accumulator`）能够按预期收敛并终止。

### 目标
1.  修改 `VMExecutionStrategy.execute` 的循环体，在准备下一次迭代时，将 `current_target` 的原始参数与 `Jump` 信号中的覆盖参数正确合并。
2.  增加对非字典 `Jump.data` 的处理逻辑，将其视为对任务第一个位置参数的覆盖。

### 基本原理
我们将修改 `while` 循环的逻辑。在每次迭代开始时，我们会从 `current_target` 加载完整的 `args` 和 `kwargs`。然后，我们会应用上一次 `Jump` 提供的覆盖值。在处理 `Jump` 返回值时，我们会区分 `dict` 和非 `dict` 类型的数据，并相应地设置下一次迭代的 `args` 或 `kwargs` 覆盖。

### 标签
#intent/fix #flow/draft #priority/critical #comp/engine #concept/control-flow #scope/core #ai/instruct #task/domain/core #task/object/vm-strategy #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修复 VMExecutionStrategy 中的循环和参数传递逻辑

我们将应用一个补丁来修正 `execute` 方法，使其能够正确处理 TCO 循环中的状态传递。

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
        from cascade.spec.jump import Jump

        current_target = target
        next_input_overrides: Optional[Dict[str, Any]] = None

        while True:
            # 1. Frontend: Compile LazyResult to GraphIR
            compilation_result = Frontend.compile(current_target)
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
            
            vm.set_middlewares([
                ObservabilityMiddleware(self.bus, run_id),
                RetryMiddleware(),
                ConstraintMiddleware(self.constraint_manager),
                ResourceLifecycleMiddleware(self.resource_manager),
                ArgumentResolutionMiddleware(active_resources, params),
            ])
            
            # Use overrides from previous Jump if available
            initial_kwargs = next_input_overrides or {}
            next_input_overrides = None

            result = await vm.execute(
                blueprint,
                symbol_table=symbol_table,
                initial_args=[],  # Jumps primarily work with kwargs for clarity
                initial_kwargs=initial_kwargs,
            )

            # 5. Check for Control Flow Signal
            if not isinstance(result, Jump):
                return result  # Normal termination

            # 6. Handle Explicit Jump
            selector = getattr(current_target, '_jump_selector', None)
            if not selector:
                raise RuntimeError(
                    f"Task '{current_target.task.name}' returned a Jump signal "
                    "but has no bound jump selector. Use cs.bind() to link a selector."
                )

            next_lazy_result = selector.routes.get(result.target_key)

            if next_lazy_result is None:
                # Loop exit condition
                return result.data

            # 7. Prepare for next iteration
            current_target = next_lazy_result
            
            # Prepare input overrides for the next loop
            if isinstance(result.data, dict):
                next_input_overrides = result.data
            elif result.data is not None:
                # Non-dict data is passed as the first positional argument
                # In the VM, this means we need to know which register to populate
                # For simplicity, we will pass it as a special kwarg and let
                # the VM/middleware handle it. Or, for TCO, it's often a dict.
                # The old strategy passed it as {"0": ...}, but VM doesn't use that.
                # The test case `accumulator` passes a dict. Let's stick to dicts.
                # This might require adjusting the `counter` test if it relies on positional.
                # Let's assume for now Jump data is a dict of kwargs.
                raise TypeError("Jump data for VM-based TCO must be a dictionary.")
            else:
                next_input_overrides = {}
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
        from cascade.spec.jump import Jump

        current_target = target
        next_args_override: Optional[List[Any]] = None
        next_kwargs_override: Optional[Dict[str, Any]] = None

        while True:
            # 1. Compile (every loop, as target object might change)
            compilation_result = Frontend.compile(current_target)
            graph_ir = compilation_result.ir
            symbol_table = compilation_result.symbol_table
            execution_plan = Optimizer.optimize(graph_ir)
            blueprint = Backend.compile(graph_ir, execution_plan)

            # 2. Prepare VM and Middleware
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

            # 3. Prepare Inputs for this iteration
            # Start with the original args/kwargs from the LazyResult
            initial_args = list(getattr(current_target, 'args', []))
            initial_kwargs = getattr(current_target, 'kwargs', {}).copy()

            # Apply overrides from the previous Jump
            if next_args_override is not None:
                initial_args = next_args_override
            if next_kwargs_override is not None:
                initial_kwargs.update(next_kwargs_override)
            
            # Clear overrides for the next potential loop
            next_args_override, next_kwargs_override = None, None

            # 4. Execute
            result = await vm.execute(
                blueprint,
                symbol_table=symbol_table,
                initial_args=initial_args,
                initial_kwargs=initial_kwargs,
            )

            # 5. Check for Control Flow Signal
            if not isinstance(result, Jump):
                return result  # Normal termination

            # 6. Handle Explicit Jump
            selector = getattr(current_target, '_jump_selector', None)
            if not selector:
                raise RuntimeError(
                    f"Task '{current_target.task.name}' returned a Jump signal "
                    "but has no bound jump selector. Use cs.bind() to link a selector."
                )

            next_lazy_result = selector.routes.get(result.target_key)

            if next_lazy_result is None:
                return result.data  # Loop exit condition

            # 7. Prepare for next iteration
            current_target = next_lazy_result
            if isinstance(result.data, dict):
                next_kwargs_override = result.data
            elif result.data is not None:
                # Assume single value maps to the first positional argument
                next_args_override = [result.data]
~~~~~

### 下一步建议
请重新运行测试套件。这次的逻辑更加完善，应该能够正确处理两种 TCO 场景，使测试全部通过。
