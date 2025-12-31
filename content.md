你完全正确。我为上一个补丁导致的死循环道歉。我的修复方向是正确的，但实现上存在一个致命的缺陷，导致了更严重的问题。

**战略性矛盾分析：**

我犯了一个典型的错误：**我试图在“运行时”（Strategy）层面解决一个本该在“编译时”（Graph Construction）层面解决的问题。**

*   **我的错误**: 我在 `VMExecutionStrategy` 的循环中，试图将 `Jump` 信号里的新参数（如 `val=2`）“喂”给一个已经根据旧参数（`val=3`）编译好的、静态的 `Blueprint`。`VirtualMachine` 忠实地执行了这个静态 `Blueprint`，完全忽略了我传入的新参数，因此每次循环都从 `val=3` 开始，导致了死循环。
*   **根本原因**: `Blueprint` 是不可变的。一旦它被编译，它内部的字面量（Literals）就固定了。TCO 循环的本质是**用更新后的参数重新构建计算图**。

**正确的修复方案：**

我们必须在每次循环时，用 `Jump` 信号返回的新数据来创建一个**新的 `LazyResult` 实例**，然后对这个**新的实例**进行编译。这完美地模拟了递归调用，并确保了每次编译的 `Blueprint` 都包含了正确的、最新的状态。

我将生成一个计划来实施这个正确的修复。

## [WIP] fix(engine): 正确处理 TCO 循环中的状态传递

### 错误分析
上一个补丁引入了无限循环，因为 `VMExecutionStrategy` 在 TCO 循环中重复编译并执行了同一个基于**初始状态**的 `Blueprint`。它未能将 `Jump` 信号中返回的新状态（如递减后的计数器值）应用到下一次迭代的编译输入中，导致循环条件永远无法改变。

### 用户需求
修复 `cascade-engine/src/cascade/runtime/strategies/vm.py`，确保在处理 `cs.Jump` 信号时，其 `data` 负载被用来创建一个全新的、带有更新后参数的 `LazyResult` 作为下一次循环的编译目标。

### 评论
这个修复遵循了 Cascade 的核心设计哲学：`LazyResult` 是不可变的计算描述。我们不应该试图在运行时“修改”一个已编译的计划，而应该用新的参数创建一份新的计算描述，并编译执行它。这个方案虽然在每一轮循环都重新编译，但它在逻辑上是绝对正确的，并能从根本上杜绝状态污染和无限循环。

### 目标
1.  修改 `VMExecutionStrategy.execute` 的 `while` 循环。
2.  当收到 `Jump` 信号时，获取目标 `LazyResult` 模板。
3.  基于该模板和 `Jump.data` 中的新参数，创建一个新的 `LazyResult` 实例。
4.  将这个新实例设为下一次循环的 `current_target`。

### 基本原理
我们将使用 `LazyResult` 的构造函数，将从 `Jump` 信号中解析出的新参数 (`args`/`kwargs`) 与目标任务 (`next_lazy_result.task`) 结合，创建一个全新的 `LazyResult` 对象。这个对象将成为下一轮 `Frontend.compile()` 的输入，从而生成一个包含正确状态的全新 `Blueprint`。

### 标签
#intent/fix #flow/draft #priority/critical #comp/engine #concept/control-flow #scope/core #ai/instruct #task/domain/core #task/object/vm-strategy #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 实现正确的 TCO 状态更新逻辑

我们将修改 `while` 循环的末尾，确保每次迭代都基于更新后的参数创建一个新的 `LazyResult`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
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
        from cascade.spec.lazy_types import LazyResult

        current_target = target

        while True:
            # 1. Compile the current target for this iteration
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

            # 3. Execute with current arguments
            # The VM needs to know the initial arguments for this specific run
            initial_args = list(getattr(current_target, 'args', []))
            initial_kwargs = getattr(current_target, 'kwargs', {}).copy()

            result = await vm.execute(
                blueprint,
                symbol_table=symbol_table,
                initial_args=initial_args,
                initial_kwargs=initial_kwargs,
            )

            # 4. Check for Control Flow Signal
            if not isinstance(result, Jump):
                return result  # Normal termination

            # 5. Handle Explicit Jump
            selector = getattr(current_target, '_jump_selector', None)
            if not selector:
                raise RuntimeError(
                    f"Task '{current_target.task.name}' returned a Jump signal "
                    "but has no bound jump selector. Use cs.bind() to link a selector."
                )

            next_lr_template = selector.routes.get(result.target_key)

            if next_lr_template is None:
                return result.data  # Loop exit condition

            # 6. CRITICAL: Create a NEW LazyResult for the next iteration
            # Start with the original arguments of the next target template
            next_args = list(getattr(next_lr_template, 'args', []))
            next_kwargs = getattr(next_lr_template, 'kwargs', {}).copy()

            # Apply overrides from the Jump data
            if isinstance(result.data, dict):
                next_kwargs.update(result.data)
            elif result.data is not None:
                # Assume single value maps to the first positional argument
                if next_args:
                    next_args[0] = result.data
                else:
                    next_args = [result.data]
            
            # Construct the new target, preserving the original jump selector binding
            current_target = LazyResult(
                task=next_lr_template.task,
                args=tuple(next_args),
                kwargs=next_kwargs,
                _jump_selector=getattr(next_lr_template, '_jump_selector', None)
            )
~~~~~

### 下一步建议
请再次运行测试。这个新实现是逻辑上完备的，它在每次循环时都创建了一个新的、状态正确的计算图描述。它应该能让两个 TCO 测试都成功通过。
