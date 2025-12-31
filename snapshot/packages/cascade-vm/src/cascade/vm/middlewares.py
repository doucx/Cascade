import inspect
import asyncio
from typing import Any, List, Dict, Callable, Awaitable

from .middleware import Middleware, ExecutionContext, NextHandler
from cascade.spec.blueprint import ContextOperand, ResourceOperand, ExecutionPolicy

class ContextMiddleware(Middleware):
    """Resolves ContextOperands from the top-level context data."""
    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        # Resolve positional args
        for i, arg in enumerate(ctx.resolved_args):
            if isinstance(arg, ContextOperand):
                if ctx.context_data and arg.scope in ctx.context_data:
                    ctx.resolved_args[i] = ctx.context_data[arg.scope].get(arg.key)

        # Resolve keyword args
        for key, arg in ctx.resolved_kwargs.items():
            if isinstance(arg, ContextOperand):
                if ctx.context_data and arg.scope in ctx.context_data:
                    ctx.resolved_kwargs[key] = ctx.context_data[arg.scope].get(arg.key)
        
        return await next_handler()


class ResourceMiddleware(Middleware):
    """Resolves ResourceOperands and manages resource lifecycle."""
    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        # Resolve ResourceOperands first
        for i, arg in enumerate(ctx.resolved_args):
            if isinstance(arg, ResourceOperand):
                ctx.resolved_args[i] = ctx.active_resources.get(arg.name)
        
        for key, arg in ctx.resolved_kwargs.items():
             if isinstance(arg, ResourceOperand):
                ctx.resolved_kwargs[key] = ctx.active_resources.get(arg.name)

        # Acquire/Release resources defined in policy
        requirements = {}
        if ctx.instruction.policy and ctx.instruction.policy.resources:
            requirements = ctx.instruction.policy.resources

        if not requirements or not ctx.vm.resource_manager:
            return await next_handler()

        await ctx.vm.resource_manager.acquire(requirements)
        try:
            return await next_handler()
        finally:
            await ctx.vm.resource_manager.release(requirements)


class RetryMiddleware(Middleware):
    """Handles instruction retry policy."""
    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        policy = getattr(ctx.instruction, 'policy', None)
        retry_policy = policy.retry if policy else None

        if not retry_policy:
            return await next_handler()

        max_attempts = retry_policy.max_attempts
        delay = retry_policy.delay
        backoff = retry_policy.backoff
        last_exception = None

        for attempt in range(max_attempts + 1):
            try:
                return await next_handler()
            except Exception as e:
                last_exception = e
                if attempt < max_attempts:
                    await asyncio.sleep(delay)
                    delay *= backoff
        
        raise last_exception