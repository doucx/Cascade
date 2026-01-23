简要回答
测试失败表明之前的 `_bind_execution_arguments` 实现过于简单，没有正确处理 `*args` (VAR_POSITIONAL) 和 `**kwargs` (VAR_KEYWORD) 类型的参数。这导致像 `cs.dict` 和 `cs.format` 这样依赖变长参数的辅助函数无法接收到输入。

我将重构参数绑定逻辑，实现一个能够正确处理 Python 所有参数类型（包括变长参数）以及 Cascade 特有注入逻辑的绑定器。

## [WIP] fix(vm): 修复参数绑定逻辑以支持变长参数(*args, **kwargs)

### 错误分析
测试 `test_helpers.py` 失败的根本原因是 `BridgedComputeService._bind_execution_arguments` 方法在遍历函数签名时，对于 `VAR_KEYWORD` (`**kwargs`) 和 `VAR_POSITIONAL` (`*args`) 类型的参数，仅仅检查了参数名是否存在于输入中，而没有去“收集”剩余的未匹配输入。

1.  **`test_dict_provider`**: `def _dict_task(**kwargs)`。绑定器只找名为 `kwargs` 的输入，忽略了 `dynamic_key` 和 `static_key` 等实际输入，导致传给函数的 `kwargs` 为空。
2.  **`test_format_provider`**: `def _format_task(template, *args, **kwargs)`。绑定器正确绑定了 `template`，但忽略了 `*args` 和 `**kwargs` 的收集逻辑，导致 `name="World"` 丢失。

### 用户需求
修复 VM 适配层，使其能够正确执行带有 `*args` 和 `**kwargs` 的任务，这对于标准库中的 helper 函数（如 `format`, `dict`, `gather`）至关重要。

### 评论
参数绑定是 VM 与用户代码交互的边界，必须完全符合 Python 的调用约定，同时还要叠加 Cascade 的依赖注入逻辑。这是一个复杂但必须精确实现的逻辑。

### 目标
1.  重构 `_bind_execution_arguments`，实现完整的参数匹配状态机。
2.  支持 `VAR_POSITIONAL`：收集所有未使用的位置输入。
3.  支持 `VAR_KEYWORD`：收集所有未使用的关键字输入。
4.  保持 `Inject` 和 `params_context` 的优先注入逻辑。

### 基本原理
我们将采用“消耗式”匹配策略：
1.  将输入分为 `pos_inputs` (按索引排序) 和 `kw_inputs` (字典)。
2.  维护一个 `next_pos_index` 指针。
3.  遍历函数签名参数：
    *   如果是 `Inject`/系统参数，直接注入。
    *   如果是普通参数，优先从 `kw_inputs` 消耗（匹配名字），否则从 `pos_inputs` 消耗（匹配索引）。
    *   如果是 `*args`，吞噬所有剩余 `pos_inputs`。
    *   如果是 `**kwargs`，吞噬所有剩余 `kw_inputs`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/vm #scope/core #task/domain/compute #task/object/adapter-layer #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 重写 _bind_execution_arguments

我们将完全替换 `packages/cascade-vm/src/cascade/vm/compute/adapters.py` 中的 `_bind_execution_arguments` 方法。

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
                elif param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
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
                
            elif param.kind == inspect.Parameter.VAR_POSITIONAL: # *args
                # Consume ALL remaining positional inputs
                # We need to find all keys >= next_pos_idx
                sorted_keys = sorted([k for k in pos_inputs.keys() if k >= next_pos_idx])
                for k in sorted_keys:
                    final_args.append(pos_inputs[k])
                # Advance index to avoid re-consumption (though loop implies we are done with pos args for standard params)
                if sorted_keys:
                    next_pos_idx = sorted_keys[-1] + 1
            
            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                if param.name in kw_inputs:
                    final_kwargs[param.name] = kw_inputs.pop(param.name)
                # else default or error
            
            elif param.kind == inspect.Parameter.VAR_KEYWORD: # **kwargs
                # Consume ALL remaining keyword inputs
                # kw_inputs is being popped, so whatever is left goes here
                final_kwargs.update(kw_inputs)
                kw_inputs.clear()

        return final_args, final_kwargs
~~~~~

### 下一步建议

现在参数绑定逻辑应该能够正确处理变长参数了。请再次运行集成测试以验证修复。

1.  `pytest packages/cascade-library/tests/integration/test_helpers.py`
2.  `pytest packages/cascade-runtime/tests/integration/test_engine_inputs.py` (确保没破坏原有逻辑)
