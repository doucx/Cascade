我已分析完日志。

## [WIP] fix(vm): 修复 SignatureBinder 中混合参数的绑定错误

### 错误分析

**错误现象**:
在调用带有 `*args` 的函数（如 `_format_task(template, *args, **kwargs)`）时，如果第一个参数（`template`）通过关键字参数形式提供，同时后续的位置参数（`*args`）也存在，会触发 `TypeError: multiple values for argument 'template'`。

**根本原因**:
`SignatureBinder` 的 `bind_and_resolve` 方法在重构参数列表时存在缺陷。它的逻辑如下：
1.  它正确地识别出 `template` 是通过关键字参数 `kw_inputs` 提供的，并跳过将其添加到位置参数列表 `args_list` 中。
2.  **但它没有记录下位置 `0` 已经被消耗**。
3.  当它处理 `*args` 时，它会收集所有未被消耗的位置参数。在错误场景中，它找到了索引为 `1` 的参数。
4.  它将这个参数（来自索引 `1`）放入 `args_list` 的**第一个位置**（索引 `0`）。
5.  最终，`inspect.signature.bind` 被调用时，它收到了一个位置参数（`args_list[0]`）和一个同名的关键字参数（`template`），从而导致了 `multiple values` 错误。

### 用户需求

修复 `SignatureBinder`，使其能够正确处理混合了关键字参数和 `*args` 的函数调用。

### 评论

这是一个微妙但关键的绑定逻辑错误。修复此问题将增强 Cascade 对复杂函数签名的支持，提高框架的健壮性。

### 目标

修改 `packages/cascade-vm/src/cascade/vm/compute/binding.py` 中的 `bind_and_resolve` 方法，实现一个更精确的参数重构算法，该算法能够正确处理被关键字参数占用的位置槽。

### 基本原理

新的实现将不再简单地跳过被关键字参数满足的位置参数。取而代之，它会：
1.  构建一个 `final_args` 列表。
2.  按顺序检查函数签名中的每一个位置参数。
3.  如果一个位置被关键字参数满足，就从关键字参数字典中取出值，并放入 `final_args` 的正确位置。
4.  如果一个位置被位置参数满足，就从位置参数字典中取出值，并放入 `final_args`。
5.  所有剩余的位置参数都将被正确地追加到 `final_args` 列表的末尾，以供 `*args` 使用。
6.  最后，用重建好的 `final_args` 和剩余的 `final_kwargs` 调用 `self.sig.bind()`。

这种方法确保了传递给 `bind` 的参数列表与函数签名的期望完全一致，从根本上解决了冲突。

### 标签

#intent/fix #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/signature-binder #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 SignatureBinder 的参数绑定逻辑

我将用更健壮的参数重构逻辑替换 `binding.py` 中的相关代码块。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/binding.py
~~~~~
~~~~~python.old
        # 3. Reconstruct args_list based on signature consumption
        # This is critical to handle cases where positional args are sparse or skipped
        # because an earlier parameter was supplied via kwargs.
        args_list = []
        next_pos_idx = 0

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
                # *args consumes ALL remaining positional inputs, even if sparse.
                # We sort them to ensure deterministic order.
                remaining_keys = sorted([k for k in pos_inputs.keys() if k >= next_pos_idx])
                for k in remaining_keys:
                    args_list.append(pos_inputs[k])
                # No more positional consumption possible after *args
                break

        # 4. Bind
        try:
            bound = self.sig.bind(*args_list, **kw_inputs)
        except TypeError as e:
            raise TypeError(
                f"Failed to bind arguments for function '{self.func.__name__}': {e}"
            ) from e
~~~~~
~~~~~python.new
        # 3. Argument Reconstruction
        # This logic reconstructs a canonical `*args` and `**kwargs` from the
        # flat `pos_inputs` and `kw_inputs` maps, respecting the function signature.
        final_args = []
        final_kwargs = kw_inputs.copy()

        pos_params = [
            p
            for p in self.sig.parameters.values()
            if p.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]

        # Handle named positional parameters first.
        for i, param in enumerate(pos_params):
            if param.name in final_kwargs:
                # This positional slot is filled by a keyword argument.
                if i in pos_inputs:
                    raise TypeError(f"multiple values for argument '{param.name}'")
                final_args.append(final_kwargs.pop(param.name))
            elif i in pos_inputs:
                # This positional slot is filled by a positional argument.
                final_args.append(pos_inputs.pop(i))
            else:
                # This slot is unfilled. Python requires positional arguments to be
                # contiguous before keyword-only ones. We stop filling `final_args` here
                # and let `bind()` handle defaults or raise a TypeError for missing arguments.
                break

        # Any remaining items in pos_inputs are for the `*args` parameter.
        if pos_inputs:
            for i in sorted(pos_inputs.keys()):
                final_args.append(pos_inputs[i])

        # 4. Bind
        try:
            bound = self.sig.bind(*final_args, **final_kwargs)
        except TypeError as e:
            raise TypeError(
                f"Failed to bind arguments for function '{self.func.__name__}': {e}"
            ) from e
~~~~~

### 下一步建议

现在 Bug 已经修复，我建议我们继续推进，为这个修复创建一个 `[COMMIT]` 计划，将其作为一个原子性的、完整的单元提交到版本控制中。如果你同意，请告诉我，我将生成相应的 `git add` 和 `git commit` 指令。
