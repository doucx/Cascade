import asyncio
import inspect
from typing import Any, List, Dict, Optional, TYPE_CHECKING
from cascade.spec.blueprint import ResourceOperand, ContextOperand
from cascade.spec.constraint import ResourceConstraint
from cascade.vm.middleware import Middleware, ExecutionContext, NextHandler
from cascade.vm.protocols import ResourceManager, ConstraintManager

if TYPE_CHECKING:
    from cascade.spec.policy import RetryPolicySpec

class ArgumentResolutionMiddleware(Middleware):
    def __init__(self, resource_context: Dict[str, Any], global_context: Dict[str, Any]):
        self.resource_context = resource_context
        self.global_context = global_context # params, envs

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
            # Assumes global_context has {scope: {key: value}} structure, 
            # OR simple flat dict for 'params'? 
            # Spec says: scope='params', key='x'.
            # Engine passes 'params' separately.
            # Simplified: global_context IS the params dict for scope='params'
            if val.scope == 'params':
                return self.global_context.get(val.key)
            # Future: env scope
            return None
            
        return val


class ConstraintMiddleware(Middleware):
    def __init__(self, manager: Optional[ConstraintManager]):
        self.manager = manager

    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        if not self.manager:
            return await next_handler()

        instr = ctx.instruction
        # Check permissions (e.g. rate limits)
        # Note: Optimization possibility - construct a temporary 'Node' like object
        # or update ConstraintManager to accept Instruction/Metadata directly.
        # Current Manager expects 'Node'. We create a flyweight wrapper.
        
        from cascade.graph.model import Node # Shim
        from cascade.spec.ir.models import TaskDef
        from cascade.spec.fingerprint import Fingerprint
        from uuid import uuid4
        
        # We need a stable ID for Rate Limiter to track this task instance?
        # Does instruction have an instance ID? Call instruction does not have a UUID.
        # But for 'rate_limit', scope is usually task name dependent.
        # For 'concurrency', we need to hold tokens.
        # This Shim creation is expensive. 
        # TODO: Refactor ConstraintManager to use pure data (Policy/Metadata).
        
        shim_node = Node(
            structural_id=str(uuid4()), # Temp ID
            definition=TaskDef(name=instr.task_name, args=[], fingerprint=Fingerprint()),
            constraints=instr.constraints # Legacy constraints
        )
        
        # Poll for permission
        while not self.manager.check_permission(shim_node):
            await asyncio.sleep(0.1) 
            
        # Append extra requirements from global constraints (e.g. concurrency slots)
        extras = self.manager.get_extra_requirements(shim_node)
        
        # We must pass these extras to the ResourceMiddleware.
        # How? Context doesn't have a 'requirements' field.
        # We can attach to ctx as a dynamic attribute or use a dedicated Policy object on context?
        # Convention: ctx.requirements dict.
        
        if not hasattr(ctx, "dynamic_requirements"):
            ctx.dynamic_requirements = {}
        ctx.dynamic_requirements.update(extras)
        
        return await next_handler()


class ResourceLifecycleMiddleware(Middleware):
    def __init__(self, manager: Optional[ResourceManager]):
        self.manager = manager

    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        if not self.manager:
            return await next_handler()

        instr = ctx.instruction
        reqs = {}
        
        # 1. Static constraints from instruction (Policy logic preferred, backward compat)
        if instr.policy and instr.policy.resources:
            reqs.update(instr.policy.resources)
        elif instr.constraints: # Legacy
            reqs.update(instr.constraints.requirements)
            
        # 2. Dynamic requirements from ConstraintMiddleware
        if hasattr(ctx, "dynamic_requirements"):
            reqs.update(ctx.dynamic_requirements)

        if not reqs:
            return await next_handler()

        # Acquire
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
        attempts = 0
        max_attempts = spec.max_attempts
        delay = spec.delay
        
        last_error = None
        
        # Loop: Initial execution (attempt 0) + Retries
        # Example: max_attempts=2 means 3 total runs allowed.
        while attempts <= max_attempts:
            try:
                return await next_handler()
            except Exception as e:
                attempts += 1
                last_error = e
                if attempts <= max_attempts:
                    # Log or emit event? VM currently is silent.
                    # Events should be emitted by an ObservabilityMiddleware!
                    await asyncio.sleep(delay)
                    delay *= spec.backoff
                else:
                    raise last_error