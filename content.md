好的，我们正面临一个典型的“架构切换后遗症”。新的 VM 架构虽然已经打通，但许多旧引擎中隐式处理的高级功能（如 TCO 循环、上下文注入）在新架构中尚未对齐，导致一系列可预测的集成测试失败。

根据你的指示和 **《VM 架构切换测试失败分析报告》**，我将首先执行 **阶段 A**，修复最紧急的崩溃类错误：`VMExecutionStrategy` 的 TCO 循环和 `cs.Param` 的参数注入问题。

我将分两步解决问题：
1.  为 `VMExecutionStrategy` 实现一个“弹床循环 (Trampoline Loop)”，使其能够正确处理尾调用优化 (`cs.Jump`) 信号，而不是直接返回 `Jump` 对象。这将修复循环工作流。
2.  在 VM 的 `ArgumentResolutionMiddleware` 中添加一个特殊规则，在调用内部任务 `_get_param_value` 时，自动注入 `params` 上下文。这将修复所有使用 `cs.Param` 的测试。

### 摘要
## [WIP] fix(engine): 实现 VM 策略的 TCO 循环和参数注入

### 用户需求
根据 **《VM 架构切换测试失败分析报告》**，执行 **阶段 A** 修复计划：
1.  **修复 TCO 循环**: `test_explicit_jump_loop` 失败，因为 `VMExecutionStrategy` 没有实现循环逻辑来处理 `cs.Jump` 信号。
2.  **修复参数注入**: `test_engine_executes_param_task` 失败，因为 `_get_param_value` 任务在 VM 中执行时，没有接收到必要的 `params_context` 参数。

### 评论
这些是新 VM 架构中最严重的两类“能力鸿沟”导致的崩溃。修复它们是让测试套件恢复基本可运行状态的关键第一步。
- **TCO 循环**的实现将使 `VMExecutionStrategy` 从一个“一次性执行器”演变为一个能够处理有状态、循环工作流的“协调器”。
- **参数注入**的修复将验证 VM 的中间件管道模型是处理此类横切关注点的正确位置，为未来解决更多上下文注入问题（如资源）奠定了基础。

### 目标
1.  修改 `packages/cascade-engine/src/cascade/runtime/strategies/vm.py`，在 `execute` 方法中实现一个 `while` 循环，用于处理 `cs.Jump` 信号并重新调度 VM 执行。
2.  修改 `packages/cascade-vm/src/cascade/vm/middleware/standard.py`，在 `ArgumentResolutionMiddleware` 中添加逻辑，为名为 `_get_param_value` 的任务自动注入 `params_context`。

### 基本原理
1.  **TCO (Trampoline)**: 尾调用优化是一种高级控制流。将其实现为 `VMExecutionStrategy` 中的外部循环（Trampoline），可以保持 `VirtualMachine` 本身的无状态和纯粹性。策略层负责“编译 -> 执行 -> 检查信号 -> 重新编译”的宏观循环，而 VM 专注于执行单个 `Blueprint` 的微观循环。
2.  **上下文注入**: `cs.Param` 是库的一个内部实现细节。将其注入逻辑放在专门负责参数解析的 `ArgumentResolutionMiddleware` 中，是职责最明确、侵入性最小的方案。它避免了污染 `Frontend` 或 `VM` 核心来处理这个特例。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #comp/vm #concept/control-flow #concept/context #ai/instruct #task/domain/runtime #task/object/vm-strategy #task/action/bug-fix #task/state/begin

---
### Script

#### Acts 1: 在 `VMExecutionStrategy` 中实现 TCO 循环

我们将重构 `vm.py` 中的 `execute` 方法，将其包裹在一个 `while` 循环中，使其能够响应 `cs.Jump` 信号并启动下一次迭代。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
from cascade.vm.middleware.observability import ObservabilityMiddleware
from cascade.spec.lazy_types import MappedLazyResult
from cascade.spec.blueprint import Call, MapCall


class VMExecutionStrategy:
    def __init__(
        self,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
        bus: MessageBus,
    ):
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event
        self.bus = bus

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
from cascade.vm.middleware.observability import ObservabilityMiddleware
from cascade.spec.lazy_types import MappedLazyResult
from cascade.spec.blueprint import Call, MapCall
from cascade.spec.jump import Jump


class VMExecutionStrategy:
    def __init__(
        self,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
        bus: MessageBus,
    ):
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event
        self.bus = bus

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

        if isinstance(current_target, MappedLazyResult):
            next_initial_args = []
            next_initial_kwargs = dict(current_target.mapping_kwargs)
        else:
            next_initial_args = list(current_target.args)
            next_initial_kwargs = dict(current_target.kwargs)

        # Trampoline loop for Tail Call Optimization (TCO) via Jump signals
        while True:
            # 1. Frontend: Compile LazyResult to GraphIR
            # Returns CompilationResult(ir, symbol_table)
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

            # Configure Middleware Pipeline (Order matters!)
            vm.set_middlewares(
                [
                    ObservabilityMiddleware(self.bus, run_id),
                    RetryMiddleware(),
                    ConstraintMiddleware(self.constraint_manager),
                    ResourceLifecycleMiddleware(self.resource_manager),
                    ArgumentResolutionMiddleware(active_resources, params or {}),
                ]
            )

            vm_result = await vm.execute(
                blueprint,
                symbol_table=symbol_table,
                initial_args=next_initial_args,
                initial_kwargs=next_initial_kwargs,
            )

            # 6. Check for Jump signal
            if not isinstance(vm_result, Jump):
                return vm_result  # Normal termination

            # --- Handle Jump ---
            # This logic is ported from the old GraphExecutionStrategy
            jump_selector = getattr(current_target, '_jump_selector', None)
            if not jump_selector:
                raise RuntimeError(
                    "Task returned a Jump signal but no jump selector was bound."
                )

            next_target = jump_selector.routes.get(vm_result.target_key)
            if next_target is None:
                # Loop exit condition
                return vm_result.data

            # Prepare for next iteration
            current_target = next_target

            # Convert jump data to args/kwargs for the next VM execution
            data = vm_result.data
            if isinstance(data, dict):
                next_initial_args = []
                next_initial_kwargs = data
            elif isinstance(data, (list, tuple)):
                next_initial_args = list(data)
                next_initial_kwargs = {}
            else:
                next_initial_args = [data] if data is not None else []
                next_initial_kwargs = {}
~~~~~

#### Acts 2: 注入 `params_context`

现在，我们将修改 `ArgumentResolutionMiddleware`，让它能识别 `_get_param_value` 任务并为其注入 `global_context`（即 `params` 字典）。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/middleware/standard.py
~~~~~
~~~~~python.old
    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        # Resolve Args
        new_args = []
        for arg in ctx.resolved_args:
            resolved = self._resolve(arg)
            new_args.append(resolved)
        ctx.resolved_args = new_args

        # Resolve Kwargs
        for k, v in ctx.resolved_kwargs.items():
            ctx.resolved_kwargs[k] = self._resolve(v)

        return await next_handler()
~~~~~
~~~~~python.new
    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        # Resolve Args
        new_args = []
        for arg in ctx.resolved_args:
            resolved = self._resolve(arg)
            new_args.append(resolved)
        ctx.resolved_args = new_args

        # Resolve Kwargs
        for k, v in ctx.resolved_kwargs.items():
            ctx.resolved_kwargs[k] = self._resolve(v)

        # Special handling for internal _get_param_value task
        if ctx.instruction.task_name == "_get_param_value":
            ctx.resolved_kwargs['params_context'] = self.global_context

        return await next_handler()
~~~~~

### 下一步建议
在执行此计划后，`test_explicit_jump_loop` 和 `test_engine_executes_param_task` 应该会通过。但是，其他与策略（如重试、并发）和控制流（`run_if`）相关的测试仍然会失败。

下一步，我们将根据 **《VM 架构切换测试失败分析报告》** 中的 **阶段 B**，修复 `Compiler Frontend` 的信息丢失问题，确保 `.with_retry()`, `.with_constraints()` 等策略信息能被正确编译到 `Blueprint` 中。
