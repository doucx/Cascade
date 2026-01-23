我们又回到了最初的 `TypeError`，这非常有启发性。这证明我们的 IR 重构是成功的，因为它清除了所有噪音，将我们直接引向了最后一个、也是最根本的 bug。在整个复杂的系统中，有一个地方仍在错误地将位置参数解释为关键字参数。

## [WIP] fix(compiler): 纠正编译器中端口命名的根本性错误

### 错误分析

**错误现象**:
`TypeError: multiple values for argument 'template'`。即使在 IR 重构后，`inspect.bind` 仍然收到了一个位置参数（来自 `*args`）和一个同名的关键字参数（来自 `**kwargs`）。

**根本原因**:
经过深入的、端到端的数据流跟踪，我终于定位到了这个极其微妙的 bug。它不在 `SignatureBinder`，也不在 `standard_launcher`，而是在编译器的更深层——`ParameterWiringPolicy` 和 `Expander` 中。

1.  **`ParameterWiringPolicy` 的错误假设**:
    *   当它处理一个位置参数（例如，`input_key="0"`）时，它会去查看 `NodeIR` 中对应的 `TaskDef`，找到索引为 0 的参数定义（`ArgumentDef`），并**使用该参数的名称**（例如，`'template'`）作为物理端口的名称。
    *   这是一个致命错误。它将一个**位置**信息（索引 `0`）错误地转换为了一个**名称**信息（`'template'`）。

2.  **`Expander` 的协同错误**:
    *   `Expander` 同样犯了这个错误，它也根据 `TaskDef` 中的参数名称来创建端口，而不是简单地使用参数的索引。

3.  **连锁反应**:
    *   因此，对于 `cs.format("string", ...)` 调用，编译器错误地创建了一个名为 `'template'` 的物理端口，而不是名为 `"0"` 的端口。
    *   在运行时，`standard_launcher` 收到一个在 `'template'` 端口上的 `Token`。因为它不是数字，所以 `standard_launcher` **正确地**将其放入了 `input_kwargs`。
    *   同时，后续的 `*args` 参数（例如，`get_first()`）对应的端口名是 `"1"`，所以它们被**正确地**放入了 `input_args`。
    *   最终，`SignatureBinder` 收到了 `args=['first', ...]` 和 `kwargs={'template': 'string', ...}`。当它调用 `bind` 时，`template` 参数从 `args[0]` 接收了 `'first'`，又从 `kwargs` 中接收了 `'string'`，导致了 `multiple values` 错误。

### 用户需求

确保编译器生成的物理图忠实地反映 DSL 中定义的参数结构，特别是位置和关键字的区别。

### 评论

这是一个典型的因“过度智能”而导致的 bug。编译器组件试图通过参数名称来变得更“具可读性”，但却破坏了参数传递的核心语义。正确的做法是，物理端口的名称必须严格、直接地反映其在 `NodeIR.args`（通过索引）或 `NodeIR.kwargs`（通过键名）中的身份。

### 目标

1.  修复 `ParameterWiringPolicy`，使其始终使用参数的索引（作为字符串）或关键字作为端口名。
2.  修复 `Expander`，使其遵循同样的、简单的命名规则。

### 基本原理

我们将移除 `ParameterWiringPolicy` 和 `Expander` 中所有试图从 `TaskDef` 推断端口名的逻辑。端口名将直接来源于 `NodeIR.args` 的索引或 `NodeIR.kwargs` 的键。这将确保从逻辑 IR 到物理图的映射是 1:1 且无损的，从而彻底根除此 bug。

### 标签

#intent/fix #flow/ready #priority/critical #comp/compiler #scope/core #ai/instruct #task/domain/compiler #task/object/port-naming #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `ParameterWiringPolicy` 的端口命名逻辑

我们将强制 `port_name` 直接等于 `input_key`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/parameter.py
~~~~~
~~~~~python.old
        for input_key, source_ref in all_inputs.items():
            # Resolve the actual port name on the Launcher.
            if input_key.isdigit():
                idx = int(input_key)
                arg_def = (
                    node_ir.task.args[idx] if idx < len(node_ir.task.args) else None
                )

                # For *args, the port name is the index itself, not the arg name (e.g. 'args')
                if arg_def and arg_def.kind != ArgumentKind.VAR_POSITIONAL:
                    port_name = arg_def.name
                else:
                    port_name = input_key
            else:
                port_name = input_key
~~~~~
~~~~~python.new
        for input_key, source_ref in all_inputs.items():
            # The physical port name MUST be the input key itself (either digit for args or string for kwargs)
            # to ensure a direct mapping from IR to the physical graph.
            port_name = input_key
~~~~~

#### Acts 2: 修复 `ParameterExpansionPolicy` 中类似的逻辑

`ParameterExpansionPolicy` 中虽然不直接创建端口，但它会根据端口名创建 `Dep` 和 `Const` 节点，保持一致性是好的。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/parameter.py
~~~~~
~~~~~python.old
        for input_key, source_ref in all_inputs.items():
            # Resolve port name
            if input_key.isdigit():
                idx = int(input_key)
                port_name = (
                    node_ir.task.args[idx].name
                    if idx < len(node_ir.task.args)
                    else input_key
                )
            else:
                port_name = input_key
~~~~~
~~~~~python.new
        for input_key, source_ref in all_inputs.items():
            # The port name is the key itself. We use it for naming debug nodes.
            port_name = input_key
~~~~~

### 下一步建议

这个修复应该最终解决了所有参数绑定问题。在执行此计划后，请运行完整的测试套件。如果所有测试都通过，我们就可以满怀信心地创建一个 `[COMMIT]` 计划，将这次漫长而重要的重构工作画上句号。
