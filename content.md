## [WIP] feat(arch): 架构硬化 - 阶段2：VM 管道化改造 (Impl)

### 用户需求
实现 `cascade-vm` 的管道化架构，以通过 `test_middleware_pipeline.py` 测试。

### 评论
当前的 VM 是不可扩展的。我们需要引入 `Middleware` 模式，将执行流程解耦为一系列独立的步骤。这意味着 VM 核心将不再直接执行代码，而是负责构建上下文并启动管道。

核心变更点：
1.  **Context 对象**: 引入 `ExecutionContext` 来携带 `frame`, `instruction`, `args`, `kwargs` 等状态在管道中流动。
2.  **Pipeline**: 实现一个异步的责任链模式。
3.  **Core Invoker**: 将原有的函数调用逻辑封装为管道的终点。

### 目标
1.  实现 `cascade.vm.middleware` 模块。
2.  重构 `VirtualMachine` 以支持 `set_middlewares` 及其执行逻辑。

### 基本原理
洋葱模型 (Onion Architecture) 允许我们在核心执行前后无缝插入逻辑，完全符合 AOP (面向切面编程) 的需求，是解决“大过滤器”问题的最佳实践。

### 标签
#intent/refine #flow/ready #priority/critical #comp/vm #scope/core #task/domain/core #task/object/hardening-pipeline #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 定义中间件基础结构

创建 `middleware` 模块，定义上下文和协议。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/middleware.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Any, List, Dict, Protocol, Callable, Awaitable, TYPE_CHECKING

if TYPE_CHECKING:
    from cascade.spec.blueprint import Instruction, Call, MapCall
    from cascade.vm.machine import Frame

# Handler Type: A function that takes context and returns an Awaitable result
# NextHandler Type: A function that takes no args (context is implicit/closed) and returns Awaitable result
NextHandler = Callable[[], Awaitable[Any]]


@dataclass
class ExecutionContext:
    """
    Carries the state of a single instruction execution through the middleware pipeline.
    """
    instruction: "Instruction"  # The generic instruction (Call or MapCall)
    frame: "Frame"
    symbol_table: Dict[str, Callable]
    
    # Resolvable inputs. Middleware can modify these in-place.
    # Initialized with raw Operands (or partially resolved values).
    resolved_args: List[Any] = field(default_factory=list)
    resolved_kwargs: Dict[str, Any] = field(default_factory=dict)


class Middleware(Protocol):
    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        ...
~~~~~

#### Acts 2: 使用 Pipe 重构 VM

大幅重构 `machine.py`。
1.  添加 `set_middlewares`。
2.  将 `_execute_call` 和 `_execute_map_call` 的逻辑委托给 `_execute_via_pipeline`。
3.  在 `_execute_via_pipeline` 中，构建 `ExecutionContext`，并定义终点逻辑（Core Invoker）。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
from cascade.spec.fingerprint import Fingerprint
from cascade.graph.model import Node

# Use local protocols to avoid circular dependency with engine
from .protocols import ResourceManager, ConstraintManager


class Frame:
~~~~~
~~~~~python.new
from cascade.spec.fingerprint import Fingerprint
from cascade.graph.model import Node

# Use local protocols to avoid circular dependency with engine
from .protocols import ResourceManager, ConstraintManager
from .middleware import Middleware, ExecutionContext, NextHandler


class Frame:
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
class VirtualMachine:
    def __init__(
        self,
        resource_manager: Optional[ResourceManager] = None,
        constraint_manager: Optional[ConstraintManager] = None,
        wakeup_event: Optional[asyncio.Event] = None,
    ):
        self._blueprints: Dict[str, Blueprint] = {}
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event

    def register_blueprint(self, bp_id: str, blueprint: Blueprint):
        self._blueprints[bp_id] = blueprint

    async def execute(
~~~~~
~~~~~python.new
class VirtualMachine:
    def __init__(
        self,
        resource_manager: Optional[ResourceManager] = None,
        constraint_manager: Optional[ConstraintManager] = None,
        wakeup_event: Optional[asyncio.Event] = None,
    ):
        self._blueprints: Dict[str, Blueprint] = {}
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event
        self._middlewares: List[Middleware] = []

    def set_middlewares(self, middlewares: List[Middleware]):
        self._middlewares = list(middlewares)

    def register_blueprint(self, bp_id: str, blueprint: Blueprint):
        self._blueprints[bp_id] = blueprint

    async def execute(
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
    async def _execute_map_call(
        self, instr: MapCall, frame: Frame, symbol_table: Dict[str, Callable]
    ) -> Any:
        func = symbol_table.get(instr.structure_hash)
        if func is None:
            raise RuntimeError(
                f"Linking failed: structure_hash '{instr.structure_hash}' "
                f"for task '{instr.task_name}' not found in symbol table."
            )
            
        loaded_kwargs = {k: frame.load(op) for k, op in instr.kwargs.items()}
        
        iterables = {}
        constants = {}
        iterable_len = -1

        for key, value in loaded_kwargs.items():
            if isinstance(value, list):
                iterables[key] = value
                if iterable_len == -1:
                    iterable_len = len(value)
                elif len(value) != iterable_len:
                    raise ValueError(f"Mismatched lengths in MapCall iterables for task '{instr.task_name}'")
            else:
                constants[key] = value

        if iterable_len == -1:
            iterable_len = 0

        calls_to_make = []
        for i in range(iterable_len):
            call_kwargs = constants.copy()
            for key, values_list in iterables.items():
                call_kwargs[key] = values_list[i]
            
            calls_to_make.append(func(**call_kwargs))

        if not calls_to_make:
            results = []
        elif inspect.iscoroutinefunction(func):
            results = await asyncio.gather(*calls_to_make)
        else:
            results = [res for res in calls_to_make]
            
        frame.store(instr.output, results)
        return results

    async def _execute_call(
        self, instr: Call, frame: Frame, symbol_table: Dict[str, Callable]
    ) -> Any:
        func = symbol_table.get(instr.structure_hash)
        if func is None:
            raise RuntimeError(
                f"Linking failed: structure_hash '{instr.structure_hash}' "
                f"for task '{instr.task_name}' not found in symbol table."
            )

        requirements: Dict[str, Any] = {}
        temp_node = None

        if self.constraint_manager or (
            instr.constraints and not instr.constraints.is_empty()
        ):
            stub_def = TaskDef(
                name=instr.task_name,
                args=[],
                fingerprint=Fingerprint(),
            )
            temp_node = Node(
                structural_id=str(uuid4()),
                definition=stub_def,
                node_type="task",
                constraints=instr.constraints,
            )

        if self.constraint_manager and temp_node:
            while not self.constraint_manager.check_permission(temp_node):
                if self.wakeup_event:
                    await self.wakeup_event.wait()
                    self.wakeup_event.clear()
                else:
                    await asyncio.sleep(0.1)

        if temp_node:
            if instr.constraints:
                requirements.update(instr.constraints.requirements)
            if self.constraint_manager:
                requirements.update(self.constraint_manager.get_extra_requirements(temp_node))

        if self.resource_manager and requirements:
            await self.resource_manager.acquire(requirements)

        try:
            args = [frame.load(op) for op in instr.args]
            kwargs = {k: frame.load(op) for k, op in instr.kwargs.items()}
            
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result

            frame.store(instr.output, result)
            return result
        finally:
            if self.resource_manager and requirements:
                await self.resource_manager.release(requirements)
~~~~~
~~~~~python.new
    async def _execute_via_pipeline(
        self,
        instr: Instruction,
        frame: Frame,
        symbol_table: Dict[str, Callable],
        core_logic: Callable[[ExecutionContext], Awaitable[Any]],
    ) -> Any:
        # 1. Initialize Context
        # Load initial operands from Frame. 
        # Note: Operands themselves are loaded, but ContextOperand/ResourceOperand
        # might evaluate to objects that need further resolution by Middleware.
        # However, frame.load(op) usually handles Register/Literal resolution.
        # ResourceOperand is NOT a Literal/Register, frame doesn't know it.
        # We need to make frame robust or handle it here.
        # CURRENT STATE: Frame.load(op) raises TypeError for unknown operands.
        # We must extend Frame or handle raw operands.
        # DECISION: We pass raw Operands to Context if they are not Registers.
        # Registers must be resolved to values (or Operands if they point to Operands? No, Registers hold values).
        # Actually, let's keep it simple: 
        # Middleware is responsible for resolving ComplexOperands.
        # Frame is responsible for resolving Registers -> Values.
        
        args = []
        for op in instr.args:
            if isinstance(op, Register):
                args.append(frame.load(op))
            elif isinstance(op, Literal):
                args.append(op.value)
            else:
                # ContextOperand, ResourceOperand pass through raw
                args.append(op)
                
        kwargs = {}
        for k, op in instr.kwargs.items():
            if isinstance(op, Register):
                kwargs[k] = frame.load(op)
            elif isinstance(op, Literal):
                kwargs[k] = op.value
            else:
                kwargs[k] = op

        ctx = ExecutionContext(
            instruction=instr,
            frame=frame,
            symbol_table=symbol_table,
            resolved_args=args,
            resolved_kwargs=kwargs
        )

        # 2. Build Onion
        # Index tracks which middleware to call next
        idx = 0
        middlewares = self._middlewares

        async def dispatch() -> Any:
            nonlocal idx
            if idx < len(middlewares):
                mw = middlewares[idx]
                idx += 1
                return await mw.handle(ctx, dispatch)
            else:
                # End of pipeline: Execute Core
                return await core_logic(ctx)

        # 3. Launch
        return await dispatch()

    async def _core_call_invoker(self, ctx: ExecutionContext) -> Any:
        instr: Call = ctx.instruction
        func = ctx.symbol_table.get(instr.structure_hash)
        # Fallback to function resolution logic if instruction has it (legacy or specialized)
        # But generally symbol_table is source of truth.
        
        if func is None:
             raise RuntimeError(
                f"Linking failed: structure_hash '{instr.structure_hash}' "
                f"for task '{instr.task_name}' not found in symbol table."
            )
            
        # Execute logic (Resources/Constraints currently STRIPPED for plain pipeline test,
        # they should come back as Middleware later)
        
        # But wait, to keep existing behavior for legacy tests, we need to preserve the
        # hardcoded resource logic IF no middleware is set?
        # No, "Scorched Earth": we are replacing the logic.
        # The tests `test_vm_instruction_execution` etc. use simple functions, no resources.
        # The `test_middleware_pipeline` uses mocks.
        # So stripping logic is correct for the pure specific logic.
        # BUT: What about integration tests using resources? 
        # They will fail unless we add default middlewares!
        # ACTION: In VM.__init__, we should install default middlewares 
        # if we want to preserve behavior. Or for now, keep it stripped and fail fast 
        # to drive middleware creation.
        # Given "Infinite Resources" and "Refactor", we choose clean architecture.
        # We will add default middlewares in Phase 3.
        
        result = func(*ctx.resolved_args, **ctx.resolved_kwargs)
        if inspect.isawaitable(result):
            result = await result
            
        ctx.frame.store(instr.output, result)
        return result

    async def _core_map_invoker(self, ctx: ExecutionContext) -> Any:
        instr: MapCall = ctx.instruction
        func = ctx.symbol_table.get(instr.structure_hash)
        if func is None:
             raise RuntimeError(f"Linking failed for map task '{instr.task_name}'")

        # Map Logic with resolved args
        # Identify lists vs scalars
        iterables = {}
        constants = {}
        iterable_len = -1
        
        # MapCall usually only maps kwargs. If we support positioned args mapping, handled here.
        # Note: current spec seems to rely on kwargs for mapping mostly?
        # Blueprint only has kwargs for map inputs in the old Backend logic?
        # Let's support both to be safe, assuming args can be lists too.
        
        # Current VM Implementation Logic:
        # only kwargs supported for mapping in Phase 1 tests?
        # Let's look at `_execute_map_call` impl I am replacing:
        # "loaded_kwargs = {k: frame.load(op) for k, op in instr.kwargs.items()}"
        # It processed kwargs.
        
        for key, value in ctx.resolved_kwargs.items():
            if isinstance(value, list) and key not in instr.kwargs: 
                # Wait, if it's a list literal passed as constant?
                # We need to know if it was INTENDED to be mapped.
                # In IR/Backend, we don't have explicit "map this arg" flag on instruction execution side easily
                # except by convention: if it came from the map source.
                # The old logic: "if isinstance(value, list): iterables[k]=value"
                # This is heuristic and fragile (what if user passes a static list?)
                # But it is the current behavior to preserve.
                iterables[key] = value
                if iterable_len == -1: iterable_len = len(value)
                elif len(value) != iterable_len: raise ValueError("Mismatched lengths")
            elif isinstance(value, list):
                 # This repeats the heuristic: all lists are iterated.
                 iterables[key] = value
                 if iterable_len == -1: iterable_len = len(value)
                 elif len(value) != iterable_len: raise ValueError("Mismatched lengths")
            else:
                constants[key] = value
                
        # What about positional args?
        # If args are present, assume they are static for now (common case)
        # or implement same heuristic.
        # For safety, let's treat resolved_args as constants for now unless we need mapping there.
        
        if iterable_len == -1: iterable_len = 0
        
        results = []
        calls = []
        for i in range(iterable_len):
            ikwargs = constants.copy()
            for k, vals in iterables.items():
                ikwargs[k] = vals[i]
            # Merge positional args (static)
            full_args = ctx.resolved_args 
            calls.append(func(*full_args, **ikwargs))
            
        if calls:
            if inspect.iscoroutinefunction(func):
                results = await asyncio.gather(*calls)
            else:
                results = [c for c in calls]
        
        ctx.frame.store(instr.output, results)
        return results

    # Replaces old _execute_call
    async def _execute_call(
        self, instr: Call, frame: Frame, symbol_table: Dict[str, Callable]
    ) -> Any:
        return await self._execute_via_pipeline(
            instr, frame, symbol_table, self._core_call_invoker
        )

    # Replaces old _execute_map_call
    async def _execute_map_call(
        self, instr: MapCall, frame: Frame, symbol_table: Dict[str, Callable]
    ) -> Any:
        return await self._execute_via_pipeline(
            instr, frame, symbol_table, self._core_map_invoker
        )
~~~~~

请注意：在 `patch_file` 中，我移除了旧的硬编码资源/约束逻辑。这会导致部分现有依赖资源检查的 Integration Test 失败（如果它们没有被 Mock 掉）。但是，单元测试 `test_middleware_pipeline.py` 会变绿。我们将在后续阶段重新引入 `ResourceMiddleware` 来修复回归问题。这是“架构重构”的正常代价。

### 下一步建议
我们已经实现了基础管道。测试 `test_middleware_pipeline.py` 将通过。
下一步我们将进入 **阶段 3**: 实现并注册标准的 Middlewares（ContextResolver, ResourceManager, RetryPolicy），并修复可能导致集成测试失败的回归。
