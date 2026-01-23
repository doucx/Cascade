## [WIP] fix(vm): 修复参数绑定逻辑以支持混合参数传递，并更新集成测试

### 错误分析
1.  **参数绑定失效**: `SignatureBinder` 在处理混合了关键字参数（如 `template`）和后续位置参数（如 `*args`）的情况时，直接将前者保留在 `kwargs` 中，导致 `inspect.bind` 无法正确匹配后续的位置参数（`*args` 必须紧跟在位置参数之后）。这导致了 `TypeError: multiple values for argument 'template'`。
2.  **测试用例缺陷**: `test_compute_adapters.py` 中的 `test_is_idle_state_changes` 注册了一个需要参数的函数 `sync_add`，但在构造请求时未提供参数，导致绑定失败。
3.  **资源注入疑似失效**: SQL 测试中的 `AttributeError: 'Inject' object has no attribute 'execute'` 表明 `Inject` 对象未被解析。这可能是由于 `binding.py` 中 `_resolve_value` 的递归逻辑未正确覆盖所有情况，或者 `Inject` 类型检查存在问题。

### 用户需求
修复参数绑定逻辑，使其能智能地将必要的关键字参数“提升”为位置参数，以满足 `*args` 的连续性要求。修复相关测试用例。

### 评论
参数绑定是 VM 稳定性的基石。当前的修复方案通过检测后续是否存在位置参数，来决定是否将当前的关键字参数提升为位置参数，这是一种符合 Python 参数解析规则的健壮策略。

### 目标
1.  修改 `packages/cascade-vm/src/cascade/vm/compute/binding.py`，实现“参数提升”逻辑。
2.  修改 `packages/cascade-vm/tests/integration/test_compute_adapters.py`，修复空参数调用的测试错误。

### 基本原理
Python 的函数调用机制要求位置参数必须在关键字参数之前。当底层数据结构（`raw_inputs`）将原本应为位置参数的值存储为关键字（如 `template`）时，如果后续还有位置参数（如传给 `*args` 的值），我们必须在传递给 `bind` 之前，将那个关键字参数还原为位置参数，否则 `bind` 会因为位置参数序列中断而报错或产生歧义。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/compute-adapter #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 SignatureBinder 的绑定逻辑

我们将增强 `binding.py`，使其在检测到后续有剩余位置参数时，强制将当前的关键字参数提升为位置参数。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/binding.py
~~~~~
~~~~~python.old
        for param in self.sig.parameters.values():
            if param.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                # If this parameter is already satisfied by kwargs, it consumes no positional index.
                if param.name in kw_inputs:
                    continue

                # Otherwise, try to satisfy it from pos_inputs.
                if next_pos_idx in pos_inputs:
                    args_list.append(pos_inputs[next_pos_idx])
                    next_pos_idx += 1
                else:
                    # Missing positional argument. Let 'bind' handle the error or default value.
                    pass

            elif param.kind == inspect.Parameter.VAR_POSITIONAL:
~~~~~
~~~~~python.new
        for param in self.sig.parameters.values():
            if param.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                # 1. Try to satisfy from positional inputs first
                if next_pos_idx in pos_inputs:
                    args_list.append(pos_inputs[next_pos_idx])
                    next_pos_idx += 1
                    
                # 2. Try to satisfy from keyword inputs
                elif param.name in kw_inputs:
                    # CRITICAL FIX: If we have pending positional inputs (e.g. for *args later),
                    # we MUST promote this kwarg to a positional arg to maintain the sequence.
                    # Check if there are any positional inputs with index >= next_pos_idx
                    has_pending_pos = any(k >= next_pos_idx for k in pos_inputs)
                    
                    if has_pending_pos:
                         # Promote!
                         val = kw_inputs.pop(param.name)
                         args_list.append(val)
                    else:
                         # Safe to leave in kwargs
                         pass
                else:
                    # Missing argument. Let 'bind' handle the error or default value.
                    pass

            elif param.kind == inspect.Parameter.VAR_POSITIONAL:
~~~~~

#### Acts 2: 修复 Compute Adapter 测试

我们将修复 `test_is_idle_state_changes`，为其提供合法的参数，并顺便更新断言以反映 `inspect.bind` 的规范化行为（将参数转为 tuple）。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_compute_adapters.py
~~~~~
~~~~~python.old
    service.executor.execute = blocking_executor
    service.registry.register("idle_test_hash", sync_add)

    request = ComputeRequest(
        code_hash="idle_test_hash",
        input_refs={},
        reply_to_nid="d_out",
        trace={},
    )
    await inbound_queue.put(request)
    assert service.is_idle() is False
~~~~~
~~~~~python.new
    service.executor.execute = blocking_executor
    service.registry.register("idle_test_hash", sync_add)

    # Fix: Provide required arguments for sync_add(a, b)
    request = ComputeRequest(
        code_hash="idle_test_hash",
        input_refs={"0": 1, "1": 2},
        reply_to_nid="d_out",
        trace={},
    )
    await inbound_queue.put(request)
    assert service.is_idle() is False
~~~~~

### 下一步建议
执行测试。如果 `test_helpers.py` 通过，说明参数提升逻辑生效。如果 `test_sql.py` 依然失败，我们需要进一步检查 `Inject` 对象的传递路径，或者检查是否 `cascade-vm` 和 `cascade-library` 引用了不同的 `Inject` 类定义。作为防御性编程，我建议下一步在 `binding.py` 中增加对 `Inject` 解析的日志记录，以便确切知道它是否被触发。
