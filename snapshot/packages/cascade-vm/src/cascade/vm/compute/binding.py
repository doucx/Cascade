import inspect
import logging
from contextlib import ExitStack
from typing import Any, Dict, List, Tuple, Callable

from cascade.spec.dsl.resources import Inject
from cascade.spec.runtime import ExecutionContext
from cascade.bus.events import ResourceAcquired, ResourceReleased

logger = logging.getLogger(__name__)


class SignatureBinder:
    def __init__(self, func: Callable, context: ExecutionContext):
        self.func = func
        self.sig = inspect.signature(func)
        self.context = context

    def bind_and_resolve(
        self, raw_inputs: Dict[str, Any], stack: ExitStack
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # 1. Input Separation
        pos_inputs = {int(k): v for k, v in raw_inputs.items() if k.isdigit()}
        kw_inputs = {k: v for k, v in raw_inputs.items() if not k.isdigit()}

        # 2. System Parameter Injection
        # Ensure 'params_context' is available if requested by signature
        if "params_context" in self.sig.parameters and "params_context" not in kw_inputs:
            kw_inputs["params_context"] = self.context.params

        # 3. Reconstruct args_list, excluding any params already covered by kwargs.
        args_list = []
        params = list(self.sig.parameters.values())
        has_var_positional = any(
            p.kind == inspect.Parameter.VAR_POSITIONAL for p in params
        )

        max_pos_arg = -1
        if pos_inputs:
            max_pos_arg = max(pos_inputs.keys())

        for i in range(max_pos_arg + 1):
            # We only add a positional argument to the list if its corresponding
            # parameter is not already provided as a keyword argument.
            is_in_kwargs = False
            if i < len(params):
                param = params[i]
                if param.kind in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.POSITIONAL_ONLY,
                ):
                    if param.name in kw_inputs:
                        is_in_kwargs = True

            if not is_in_kwargs:
                if i in pos_inputs:
                    args_list.append(pos_inputs[i])
                elif not has_var_positional:
                    # If there's no *args, we can't have gaps in positional args
                    # unless they have defaults, which bind() will handle.
                    # We can stop building the list here.
                    break

        # 4. Bind
        try:
            bound = self.sig.bind(*args_list, **kw_inputs)
        except TypeError as e:
            raise TypeError(
                f"Failed to bind arguments for function '{self.func.__name__}': {e}"
            ) from e

        # Apply defaults (including Inject defaults)
        bound.apply_defaults()

        # 5. Recursive Resolution
        for name, value in bound.arguments.items():
            resolved = self._resolve_value(value, stack)
            if resolved is not value:
                bound.arguments[name] = resolved

        # Return the normalized arguments
        return bound.args, bound.kwargs

    def _resolve_value(self, value: Any, stack: ExitStack) -> Any:
        if isinstance(value, Inject):
            return self._resolve_resource(value, stack)
        return value

    def _resolve_resource(self, inject_def: Inject, stack: ExitStack) -> Any:
        name = inject_def.resource_name

        # 1. Check Active Resources (Run Scope)
        if name in self.context.active_resources:
            return self.context.active_resources[name]

        # 2. Create Ephemeral Resource (Task Scope)
        # Assuming resource_container is available on context
        if not hasattr(self.context, "resource_container"):
            raise RuntimeError(
                "Context missing 'resource_container', cannot resolve resources."
            )

        provider = self.context.resource_container.get_provider(name)

        # 3. Recursively Resolve Dependencies for the Provider
        sig = inspect.signature(provider)
        deps = {}
        for param_name, param in sig.parameters.items():
            if isinstance(param.default, Inject):
                deps[param_name] = self._resolve_resource(param.default, stack)

        # Access bus for event publishing
        bus = getattr(self.context.resource_container, "bus", None)
        run_id = self.context.run_id

        # 4. Instantiate
        resource = None
        if inspect.isgeneratorfunction(provider):
            gen = provider(**deps)
            try:
                resource = next(gen)
            except StopIteration:
                raise RuntimeError(f"Resource provider '{name}' yielded nothing.")

            if bus:
                bus.publish(ResourceAcquired(run_id=run_id, resource_name=name))

            # Register cleanup
            def cleanup():
                try:
                    next(gen)
                except StopIteration:
                    pass
                except Exception as e:
                    logger.warning(f"Error during teardown of resource '{name}': {e}")

                if bus:
                    bus.publish(ResourceReleased(run_id=run_id, resource_name=name))

            stack.callback(cleanup)
            return resource
        else:
            resource = provider(**deps)

            if bus:
                bus.publish(ResourceAcquired(run_id=run_id, resource_name=name))

            def cleanup_event():
                if bus:
                    bus.publish(ResourceReleased(run_id=run_id, resource_name=name))

            stack.callback(cleanup_event)
            return resource