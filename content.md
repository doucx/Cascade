简要回答
好的，错误原因已明确：之前的参数绑定逻辑不仅将位置参数错误地放入了 `kwargs`，还完全遗漏了对变长参数（`*args`, `**kwargs`）的支持。

我将应用修正后的 `_bind_execution_arguments` 方法，它包含一个完整的状态机来正确处理所有类型的 Python 参数。

## [WIP] fix(vm): 修复参数绑定逻辑以支持变长参数(*args, **kwargs)

### 错误分析
测试 `test_helpers.py` 失败（`TypeError: multiple values for argument 'template'`）是因为旧的绑定逻辑错误地将位置参数（`pos_inputs[0]`）放入了 `final_kwargs['template']` 中，导致后续执行时位置参数和关键字参数冲突。此外，旧逻辑完全缺少处理 `*args` 和 `**kwargs` 的代码，导致变长参数丢失。

### 用户需求
修复 VM 适配层，使其能够正确执行带有 `*args` 和 `**kwargs` 的任务，确保标准库中的 helper 函数正常工作。

### 评论
参数绑定是 VM 与用户代码交互的关键边界。这次修复将引入一个健壮的、基于 `inspect` 的参数匹配器，它模拟了 Python 原生的参数绑定行为，并叠加了 Cascade 的依赖注入逻辑。

### 目标
1.  重构 `_bind_execution_arguments`，实现对 POSITIONAL_ONLY, VAR_POSITIONAL, VAR_KEYWORD 等所有参数类型的正确支持。
2.  确保 `Inject` 和 `params_context` 依然能够优先注入。

### 基本原理
采用“消耗式”匹配策略：维护一个位置指针 `next_pos_idx` 和一个剩余关键字字典 `kw_inputs`。遍历函数签名时，根据参数类型决定是从位置输入消耗、从关键字输入消耗，还是进行注入。`*args` 将一次性消耗剩余的所有位置输入，`**kwargs` 将一次性消耗剩余的所有关键字输入。

### 标签
#intent/fix #flow/ready #priority/critical #comp/vm #scope/core #task/domain/compute #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 _bind_execution_arguments

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/adapters.py
~~~~~
~~~~~python.old
    def _bind_execution_arguments(
        self, func: Any, raw_inputs: Dict[str, Any], stack: ExitStack
    ) -> Tuple[List[Any], Dict[str, Any]]:
        sig = inspect.signature(func)
        final_kwargs: Dict[str, Any] = {}

        # Pre-process inputs
        pos_inputs = {int(k): v for k, v in raw_inputs.items() if k.isdigit()}
        kw_inputs = {k: v for k, v in raw_inputs.items() if not k.isdigit()}

        for i, param in enumerate(sig.parameters.values()):
            # A. Try Keyword Input
            if param.name in kw_inputs:
                final_kwargs[param.name] = kw_inputs[param.name]
                continue

            # B. Try Positional Input
            if i in pos_inputs:
                final_kwargs[param.name] = pos_inputs[i]
                continue

            # C. System Context
            if param.name == "params_context":
                final_kwargs[param.name] = self.context.params
                continue

            # D. Dependency Injection
            if isinstance(param.default, Inject):
                final_kwargs[param.name] = self._resolve_resource(param.default, stack)
                continue

            # E. Default Value (implicitly handled by Python call if missing from final_kwargs)

        # Split into args/kwargs to respect POSITIONAL_ONLY
        call_args = []
        call_kwargs = {}

        for param in sig.parameters.values():
            if param.name in final_kwargs:
                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    call_args.append(final_kwargs[param.name])
                else:
                    call_kwargs[param.name] = final_kwargs[param.name]

        return call_args, call_kwargs
~~~~~
~~~~~python.new
    def _bind_execution_arguments(
        self, func: Any, raw_inputs: Dict[str, Any], stack: ExitStack
    ) -> Tuple[List[Any], Dict[str, Any]]:
        sig = inspect.signature(func)

        # Prepare Inputs
        # pos_inputs: index -> value
        pos_inputs = {int(k): v for k, v in raw_inputs.items() if k.isdigit()}
        # kw_inputs: name -> value (mutable, we will pop from it)
        kw_inputs = {k: v for k, v in raw_inputs.items() if not k.isdigit()}

        final_args: List[Any] = []
        final_kwargs: Dict[str, Any] = {}

        next_pos_idx = 0

        for param in sig.parameters.values():
            # --- 1. Special Handling: Inject / System Context ---
            # These are handled regardless of Parameter Kind (except maybe VAR_*)
            injected_value = None
            has_injection = False

            if param.name == "params_context":
                injected_value = self.context.params
                has_injection = True
            elif isinstance(param.default, Inject):
                injected_value = self._resolve_resource(param.default, stack)
                has_injection = True

            if has_injection:
                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    final_args.append(injected_value)
                elif param.kind in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                ):
                    final_kwargs[param.name] = injected_value
                # VAR_POSITIONAL / VAR_KEYWORD usually don't have Inject defaults, ignoring.
                continue

            # --- 2. Standard Parameter Handling ---

            if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                # Must take from positional inputs
                if next_pos_idx in pos_inputs:
                    final_args.append(pos_inputs[next_pos_idx])
                    next_pos_idx += 1
                elif param.default is not inspect.Parameter.empty:
                    final_args.append(param.default)
                else:
                    # Let Python raise the error if missing
                    pass

            elif param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                # Priority: Keyword -> Positional
                if param.name in kw_inputs:
                    final_kwargs[param.name] = kw_inputs.pop(param.name)
                elif next_pos_idx in pos_inputs:
                    final_args.append(pos_inputs[next_pos_idx])
                    next_pos_idx += 1
                elif param.default is not inspect.Parameter.empty:
                    # Python will use default
                    pass

            elif param.kind == inspect.Parameter.VAR_POSITIONAL:  # *args
                # Consume ALL remaining positional inputs
                # We need to find all keys >= next_pos_idx
                sorted_keys = sorted(
                    [k for k in pos_inputs.keys() if k >= next_pos_idx]
                )
                for k in sorted_keys:
                    final_args.append(pos_inputs[k])
                # Advance index to avoid re-consumption
                if sorted_keys:
                    next_pos_idx = sorted_keys[-1] + 1

            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                if param.name in kw_inputs:
                    final_kwargs[param.name] = kw_inputs.pop(param.name)
                # else default or error

            elif param.kind == inspect.Parameter.VAR_KEYWORD:  # **kwargs
                # Consume ALL remaining keyword inputs
                # kw_inputs is being popped, so whatever is left goes here
                final_kwargs.update(kw_inputs)
                kw_inputs.clear()

        return final_args, final_kwargs
~~~~~

### 下一步建议
再次运行测试以确认修复生效：
1. `pytest packages/cascade-library/tests/integration/test_helpers.py`
