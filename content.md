简要回答：
同意。这是将 VM 从原型转变为生产级引擎的关键一步。我们将遵循“正规军”流程，先完善基础设施，再装配业务逻辑，并同步更新集成测试以反映正确的装配模式。

## [WIP] feat: Implement VM Middleware Pipeline and Standard Middlewares

### 用户需求
目前 `cascade-vm` 的 `VirtualMachine` 是一个仅能执行基本函数调用的原型。为了支持 Cascade 的高级特性（依赖注入、资源管理、重试策略、权限控制），需要将其改造为基于 **中间件管道 (Middleware Pipeline)** 的架构。同时，需要实现一组标准中间件来处理特定的业务逻辑。

### 评论
这个改动是“架构硬化”的核心。它将复杂的横切关注点（如重试、资源）从单一的执行循环中解耦出来，放入独立的、可组合的中间件中。这不仅提高了代码的可维护性，也为未来支持分布式追踪、计费等特性打下了基础。

### 目标
1.  **基础设施**: 在 `cascade.vm.middleware` 中定义 `Middleware`, `ExecutionContext`, `NextHandler` 等核心协议。
2.  **标准实现**: 实现 `ArgumentResolutionMiddleware`, `ConstraintMiddleware`, `ResourceLifecycleMiddleware`, `RetryMiddleware`。
3.  **VM 升级**: 改造 `VirtualMachine` 以支持管道执行，并支持通过 `set_middlewares` 进行配置。
4.  **策略集成**: 更新 `VMExecutionStrategy`，使其在执行前正确装配管道。
5.  **测试对齐**: 更新 `test_vm_capabilities.py`，使其显式装配中间件，而非依赖不存在的“魔法”上下文传递。

### 基本原理
我们将采用经典的洋葱模型（Onion Model）来实现管道。每个中间件可以决定是在调用 `next_handler()` 之前（Pre-process）还是之后（Post-process）执行逻辑，或者完全拦截执行（如重试逻辑）。`ExecutionContext` 作为管道中传递的数据载体，负责携带指令、栈帧以及解析中的参数。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/vm #concept/middleware #scope/core #ai/instruct #task/domain/core #task/object/pipeline #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 定义中间件基础设施

首先，我们在 `cascade.vm.middleware` 包中定义核心协议。这为后续的实现提供了类型契约。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/middleware.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Any, List, Dict, Protocol, Callable, Awaitable, TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from cascade.spec.blueprint import Instruction
    from cascade.vm.machine import Frame

# Handler Type: A function that takes no args (context is implicit/closed over) and returns Awaitable result
NextHandler = Callable[[], Awaitable[Any]]


@dataclass
class ExecutionContext:
    """
    Carries the state of a single instruction execution through the middleware pipeline.
    """
    instruction: "Instruction"
    frame: "Frame"
    symbol_table: Dict[str, Callable]
    
    # Resolvable inputs. Middleware can modify these in-place.
    # The pipeline starts with these populated from the instruction's operands.
    resolved_args: List[Any] = field(default_factory=list)
    resolved_kwargs: Dict[str, Any] = field(default_factory=dict)
    
    # Shared storage for middlewares to pass data down the line (e.g. dynamic constraints)
    metadata: Dict[str, Any] = field(default_factory=dict)


class Middleware(Protocol):
    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        ...
~~~~~

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/middleware/__init__.py
~~~~~
~~~~~python
from .middleware import Middleware, ExecutionContext, NextHandler

__all__ = ["Middleware", "ExecutionContext", "NextHandler"]
~~~~~

#### Acts 2: 实现标准中间件

接下来，我们实现四个核心的标准中间件。注意 `ResourceLifecycleMiddleware` 和 `ConstraintMiddleware` 依赖于我们在 `cascade.runtime` 中定义的管理器协议（这里通过 `cascade.vm.protocols` 引用）。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/middleware/standard.py
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict, Optional
from cascade.spec.blueprint import ResourceOperand, ContextOperand
from cascade.vm.middleware import Middleware, ExecutionContext, NextHandler
from cascade.vm.protocols import ResourceManager, ConstraintManager

class ArgumentResolutionMiddleware(Middleware):
    def __init__(self, resource_context: Dict[str, Any], global_context: Dict[str, Any]):
        self.resource_context = resource_context
        self.global_context = global_context 

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

    def _resolve(self, val: Any) -> Any:
        if isinstance(val, ResourceOperand):
            if val.name not in self.resource_context:
                raise ValueError(f"Resource '{val.name}' not found in active resources.")
            return self.resource_context[val.name]
        
        if isinstance(val, ContextOperand):
            # Currently only 'params' scope makes sense for simple context
            if val.scope == 'params':
                return self.global_context.get(val.key)
            return None
            
        return val


class ConstraintMiddleware(Middleware):
    def __init__(self, manager: Optional[ConstraintManager]):
        self.manager = manager

    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        if not self.manager:
            return await next_handler()

        instr = ctx.instruction
        
        # In a real implementation with a strongly typed ConstraintManager, 
        # we would pass the instruction metadata directly.
        # However, the current ConstraintManager expects a 'Node' object.
        # We construct a minimal shim to satisfy the protocol.
        from cascade.graph.model import Node
        from cascade.spec.ir.models import TaskDef
        from cascade.spec.fingerprint import Fingerprint
        from uuid import uuid4
        
        # Shim construction
        shim_node = Node(
            structural_id=str(uuid4()), 
            definition=TaskDef(name=instr.task_name, args=[], fingerprint=Fingerprint()),
            constraints=instr.constraints # Legacy support
        )
        
        # Poll for permission (e.g. Rate Limits)
        while not self.manager.check_permission(shim_node):
            await asyncio.sleep(0.1) 
            
        # Get extra requirements (e.g. Concurrency Slots) to be acquired by ResourceMiddleware
        extras = self.manager.get_extra_requirements(shim_node)
        if extras:
            ctx.metadata["dynamic_requirements"] = extras
        
        return await next_handler()


class ResourceLifecycleMiddleware(Middleware):
    def __init__(self, manager: Optional[ResourceManager]):
        self.manager = manager

    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        if not self.manager:
            return await next_handler()

        instr = ctx.instruction
        reqs = {}
        
        # 1. Static constraints from instruction policy
        if instr.policy and instr.policy.resources:
            reqs.update(instr.policy.resources)
        elif instr.constraints: # Legacy fallback
            reqs.update(instr.constraints.requirements)
            
        # 2. Dynamic requirements from upstream middleware (e.g. ConstraintMiddleware)
        if "dynamic_requirements" in ctx.metadata:
            reqs.update(ctx.metadata["dynamic_requirements"])

        if not reqs:
            return await next_handler()

        # Acquire-Execute-Release Pattern
        await self.manager.acquire(reqs)
        try:
            return await next_handler()
        finally:
            await self.manager.release(reqs)


class RetryMiddleware(Middleware):
    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        policy = ctx.instruction.policy
        if not policy or not policy.retry:
            return await next_handler()

        spec = policy.retry
        # attempts is current retry count (0 means initial run)
        # max_attempts is allowed retries
        current_attempt = 0
        max_retries = spec.max_attempts
        delay = spec.delay
        
        last_error = None
        
        # Loop: Initial execution (attempt 0) + Retries
        while True:
            try:
                return await next_handler()
            except Exception as e:
                if current_attempt < max_retries:
                    current_attempt += 1
                    last_error = e
                    # TODO: Integrate with ObservabilityMiddleware for events
                    await asyncio.sleep(delay)
                    delay *= spec.backoff
                else:
                    raise e
~~~~~

#### Acts 3: 升级 VirtualMachine

现在我们将新的管道逻辑集成到 VM 核心中。这将替换旧的直接执行逻辑。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
# Use local protocols to avoid circular dependency with engine
from .protocols import ResourceManager, ConstraintManager
from .middleware import Middleware, ExecutionContext, NextHandler


class Frame:
~~~~~
~~~~~python.new
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
    def set_middlewares(self, middlewares: List[Middleware]):
        self._middlewares = list(middlewares)

    def register_blueprint(self, bp_id: str, blueprint: Blueprint):
        self._blueprints[bp_id] = blueprint

    async def execute(
        self,
        blueprint: Blueprint,
        symbol_table: Dict[str, Callable],
        initial_args: Optional[List[Any]] = None,
        initial_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        current_blueprint = blueprint
        current_symbol_table = symbol_table

        frame = Frame(current_blueprint.register_count)
        self._load_inputs(
            frame, current_blueprint, initial_args or [], initial_kwargs or {}
        )

        while True:
~~~~~
~~~~~python.new
    def set_middlewares(self, middlewares: List[Middleware]):
        self._middlewares = list(middlewares)

    def register_blueprint(self, bp_id: str, blueprint: Blueprint):
        self._blueprints[bp_id] = blueprint

    async def execute(
        self,
        blueprint: Blueprint,
        symbol_table: Dict[str, Callable],
        initial_args: Optional[List[Any]] = None,
        initial_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        current_blueprint = blueprint
        current_symbol_table = symbol_table

        frame = Frame(current_blueprint.register_count)
        self._load_inputs(
            frame, current_blueprint, initial_args or [], initial_kwargs or {}
        )

        while True:
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
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
        args = []
        for op in instr.args:
            if isinstance(op, Register):
                args.append(frame.load(op))
            elif isinstance(op, Literal):
                args.append(op.value)
            else:
                # ContextOperand, ResourceOperand pass through raw for Middleware
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
        idx = 0
        middlewares = self._middlewares

        async def dispatch() -> Any:
            nonlocal idx
            if idx < len(middlewares):
                mw = middlewares[idx]
                idx += 1
                return await mw.handle(ctx, dispatch)
            else:
                return await core_logic(ctx)

        # 3. Launch
        return await dispatch()

    async def _core_call_invoker(self, ctx: ExecutionContext) -> Any:
        instr: Call = ctx.instruction
        func = ctx.symbol_table.get(instr.structure_hash)
        
        if func is None:
             raise RuntimeError(
                f"Linking failed: structure_hash '{instr.structure_hash}' "
                f"for task '{instr.task_name}' not found in symbol table."
            )
            
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

        iterables = {}
        constants = {}
        iterable_len = -1
        
        # Simplified heuristic: lists are iterables, others are constants
        for key, value in ctx.resolved_kwargs.items():
            if isinstance(value, list):
                 iterables[key] = value
                 if iterable_len == -1: iterable_len = len(value)
                 elif len(value) != iterable_len: raise ValueError("Mismatched lengths")
            else:
                constants[key] = value
        
        if iterable_len == -1: iterable_len = 0
        
        calls = []
        for i in range(iterable_len):
            ikwargs = constants.copy()
            for k, vals in iterables.items():
                ikwargs[k] = vals[i]
            # Use static positional args
            calls.append(func(*ctx.resolved_args, **ikwargs))
            
        results = []
        if calls:
            if inspect.iscoroutinefunction(func):
                results = await asyncio.gather(*calls)
            else:
                results = [c for c in calls]
        
        ctx.frame.store(instr.output, results)
        return results
~~~~~

#### Acts 4: 配置 VMExecutionStrategy

在 Engine 层面，我们现在需要显式地装配这些中间件。这是将 `Engine` 的运行时状态（`active_resources`, `params`）注入到 `VM` 中的关键点。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
        vm = VirtualMachine(
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            wakeup_event=self.wakeup_event,
        )
        
        # Configure Middleware Pipeline (Order matters!)
        # Outer -> Inner
        vm.set_middlewares([
            # 1. Arguments must be resolved first so others see values (e.g. dynamic constraints?)
            # Actually, standard is: Retry -> Resource -> Execute.
            # Argument Resolution usually happens right before Core execution?
            # Or at the very beginning so Retry sees resolved args? 
            # Args might contain resources which need to be acquired? 
            # No, ResourceOperand just looks up an ALREADY active resource.
            # Resource acquisition (Lifecycle) is for compute resources (CPU/GPU) claimed by the task metadata.
            
            RetryMiddleware(),
            ResourceLifecycleMiddleware(self.resource_manager),
            ConstraintMiddleware(self.constraint_manager),
            ArgumentResolutionMiddleware(active_resources, params),
        ])

        if isinstance(target, MappedLazyResult):
~~~~~
~~~~~python.new
        vm = VirtualMachine(
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            wakeup_event=self.wakeup_event,
        )
        
        # Configure Middleware Pipeline (Order matters!)
        # Order: Retry (Outer) -> Constraints -> Resources -> Resolution -> Core execution (Inner)
        vm.set_middlewares([
            RetryMiddleware(),
            ConstraintMiddleware(self.constraint_manager),
            ResourceLifecycleMiddleware(self.resource_manager),
            ArgumentResolutionMiddleware(active_resources, params),
        ])

        if isinstance(target, MappedLazyResult):
~~~~~

#### Acts 5: 修复集成测试

最后，我们更新 `test_vm_capabilities.py`。我们移除了对不存在的 `context_data` 参数的依赖，转而使用正确的 `set_middlewares` 模式进行测试配置。这更符合我们现在的架构设计。

~~~~~act
write_file
packages/cascade-vm/tests/integration/test_vm_capabilities.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock

from cascade.spec.blueprint import Blueprint, Call, Register, ContextOperand, ResourceOperand, ExecutionPolicy, RetryPolicySpec
from cascade.vm import VirtualMachine
from cascade.vm.middleware.standard import (
    ArgumentResolutionMiddleware, 
    RetryMiddleware
)

# --- Helpers ---

class InMemoryResourceManager:
    """A minimal resource manager for testing VM integration."""
    def __init__(self, resources):
        self.resources = resources
        self.acquired = []

    async def acquire(self, requirements):
        self.acquired.append(("acquire", requirements))

    async def release(self, requirements):
        self.acquired.append(("release", requirements))
    
    def get_resource(self, name):
        return self.resources.get(name)

# --- Tests ---

@pytest.mark.asyncio
async def test_vm_resolves_context_operands():
    """
    Validation: VM should replace ContextOperand('params', 'x') with current value
    using the ArgumentResolutionMiddleware.
    """
    vm = VirtualMachine()
    
    # Configure Middleware with explicit context
    global_context = {"env": "prod"}
    active_resources = {}
    
    vm.set_middlewares([
        ArgumentResolutionMiddleware(active_resources, global_context)
    ])
    
    def task_fn(env_name):
        return f"Env is {env_name}"

    symbol_table = {"hash_task": task_fn}
    
    instr = Call(
        output=Register(0),
        task_name="read_env",
        structure_hash="hash_task",
        args=[ContextOperand(scope="params", key="env")],
        kwargs={}
    )
    bp = Blueprint(instructions=[instr], register_count=1)

    result = await vm.execute(bp, symbol_table)
    
    assert result == "Env is prod"


@pytest.mark.asyncio
async def test_vm_resolves_resource_operands():
    """
    Validation: VM should resolve ResourceOperand('db') to an actual object.
    """
    db_obj = MagicMock()
    db_obj.query.return_value = "query_result"
    
    vm = VirtualMachine()
    
    # Configure Middleware for injection
    active_resources = {"db": db_obj}
    vm.set_middlewares([
        ArgumentResolutionMiddleware(active_resources, global_context={})
    ])
    
    def task_fn(db):
        return db.query()

    symbol_table = {"hash_db": task_fn}
    
    instr = Call(
        output=Register(0),
        task_name="use_db",
        structure_hash="hash_db",
        args=[ResourceOperand(name="db")],
        kwargs={}
    )
    bp = Blueprint(instructions=[instr], register_count=1)

    result = await vm.execute(bp, symbol_table)
    
    assert result == "query_result"


@pytest.mark.asyncio
async def test_vm_enforces_retry_policy():
    """
    Validation: VM should auto-retry on failure if policy is set.
    """
    vm = VirtualMachine()
    vm.set_middlewares([RetryMiddleware()])
    
    # Mock function: fails once, then succeeds
    func_mock = MagicMock(side_effect=[ValueError("Boom"), "Success"])
    
    policy = ExecutionPolicy(retry=RetryPolicySpec(max_attempts=2, delay=0.01))
    
    instr = Call(
        output=Register(0),
        task_name="flaky",
        structure_hash="hash_flaky",
        policy=policy,
        args=[], kwargs={}
    )
    bp = Blueprint(instructions=[instr], register_count=1)
    
    result = await vm.execute(bp, {"hash_flaky": func_mock})
    
    assert result == "Success"
    assert func_mock.call_count == 2
~~~~~

### 下一步建议
我们已经完成了 VM 管道化改造，使其具备了承载复杂业务逻辑的能力。现在，我们可以在 `cascade-engine` 中开始移除旧的 `NodeProcessor` 中的胶水代码，并完全依赖新的 VM 执行路径。建议下一步：
1. 更新 `test_middleware_pipeline.py`，因为我们已经实现了真正的 Middleware 和 ExecutionContext，测试中不在需要 mock 这些类。
2. 运行所有集成测试，确保新架构在真实负载下的稳定性。
