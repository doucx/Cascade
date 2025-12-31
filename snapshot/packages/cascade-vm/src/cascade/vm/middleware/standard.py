import asyncio
from typing import Any, Dict, Optional
from cascade.spec.blueprint import ResourceOperand, ContextOperand
from cascade.vm.middleware.base import Middleware, ExecutionContext, NextHandler
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
            current_node_instance_hash=str(uuid4()), 
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