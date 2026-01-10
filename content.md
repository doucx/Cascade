你的分析完全正确。上一轮的修复是成功的，它清除了 `Expander` 层的错误，但这也暴露了编译流程中下一阶段的问题：`ParameterWiringPolicy`。

错误日志 `WiringError: FuncNode '...bleach' has no input port 'args'. Available: ['0', '1']` 明确指出：
1.  **成功之处**: `BleachNode` 确实已经被正确地创建了，它拥有名为 `'0'` 和 `'1'` 的输入端口，这与 `_internal_gather(*args)` 的语义一致。
2.  **新的失败点**: `ParameterWiringPolicy` 在尝试连接依赖项时，仍然错误地计算出目标端口名为 `'args'`，而不是正确的 `'0'` 或 `'1'`。

这是因为该策略的逻辑只检查了参数索引是否在 `task.args` 列表的范围内，但没有检查该参数的 `kind` 是否为 `VAR_POSITIONAL`。对于 `*args`，其参数名（如 `args`）不应被用作端口名。

我将生成一个计划来修复这个接线策略。

## [WIP] fix: 纠正 ParameterWiringPolicy 中对 *args 的端口名解析

### 错误分析
`WiringError` 的根本原因在于 `ParameterWiringPolicy` 在解析位置参数（`input_key` 是数字）的目标端口名时存在缺陷。

其现有逻辑为：
```python
if idx < len(node_ir.task.args):
    port_name = node_ir.task.args[idx].name
else:
    port_name = input_key
```
对于 `_internal_gather(*args)`，`task.args` 列表为 `[ArgumentDef(name='args', kind=VAR_POSITIONAL)]`。当 `input_key` 为 `'0'` 时，`idx` 为 `0`，`0 < 1` 为真，因此 `port_name` 被错误地解析为 `node_ir.task.args[0].name`，即 `'args'`。

正确的逻辑应该是：如果参数类型是 `VAR_POSITIONAL`，则端口名必须是其数字索引（`input_key`），而不是参数名。

### 用户需求
修复 `test_vm_list_output` 测试中出现的 `WiringError`，确保编译器能够为 `*args` 函数正确地连接输入。

### 评论
这个修复进一步加强了编译器物理层与 Python 语言语义之间的一致性。通过在接线阶段也尊重参数的 `kind`，我们确保了从定义到实现的整个编译链路的正确性。

### 目标
修改 `ParameterWiringPolicy` 的 `apply` 方法，使其在解析位置参数的端口名时，能够正确处理 `ArgumentKind.VAR_POSITIONAL` 的情况。

### 基本原理
我们将增强端口名解析逻辑，增加一个对 `arg.kind` 的检查。只有当参数是常规的位置或关键字参数时，才使用其 `.name` 作为端口名。如果参数是 `VAR_POSITIONAL`，则直接使用其数字索引作为端口名。

### 标签
#intent/fix #flow/ready #priority/high #comp/compiler #concept/parser #scope/core #ai/instruct #task/domain/compiler #task/object/wiring-policy #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 导入 ArgumentKind

首先，我们需要在 `parameter.py` 中导入 `ArgumentKind` 枚举，以便在逻辑中使用它。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/parameter.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import NodeIR
from cascade.std.specs import StainerSpec
from cascade.compiler.backend.expander import SubGraph
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import NodeIR, ArgumentKind
from cascade.std.specs import StainerSpec
from cascade.compiler.backend.expander import SubGraph
~~~~~

#### Acts 2: 修正端口名解析逻辑

现在，我们用更精确的逻辑替换掉有问题的端口名解析代码块。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/parameter.py
~~~~~
~~~~~python.old
            # Resolve the actual port name on the Bleacher.
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
            # Resolve the actual port name on the Bleacher.
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

### 下一步建议

这个修复应该能解决 `WiringError`。请再次运行 `pytest packages/cascade-runtime/tests/integration/test_vm_e2e.py`。如果所有测试通过，则意味着从前端 DSL 解析到后端物理图生成和接线的整个 `*args` 处理链路都已正确实现。
