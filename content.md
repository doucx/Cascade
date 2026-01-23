好的，日志显示我们修复了一个问题，但暴露了另一个问题。这是一个好迹象，意味着我们的重构正在深入到问题的核心。

1.  `test_format_provider` **失败**: `TypeError: missing a required argument: 'template'`。这表明当 `template` 作为位置参数传递时，它没有被正确地放入 `ComputeRequest` 的 `input_args` 中。
2.  `test_format_provider_with_positional_args` **失败**: `AssertionError: assert 'first' == 'Positional: first, second'`。这表明 `_format_task` 只收到了 `'first'` 作为 `*args` 的唯一成员，而模板字符串和 `'second'` 都丢失了。

这两个失败都指向同一个嫌疑人：`standard_launcher`。我上次修改它的逻辑时，引入了一个新的、更微妙的错误。

## [WIP] fix(std): 最终修复 Launcher 的参数组装逻辑

### 错误分析

**错误现象**:
`_format_task` 要么完全没有收到 `template` 参数，要么只收到了 `*args` 的一部分。

**根本原因**:
我上次修改 `standard_launcher` 时，逻辑过于复杂，并且基于一个错误的假设。让我们重新检查：

```python
# 旧的错误逻辑
for port_name in node.arg_port_names:
    token = io.args.get(port_name)
    if token:
        input_args.append(token.payload)
        trace_payload.update(token.trace)

for port_name in node.kwarg_port_names:
    # ...
```

这里的 `io.args` 是 `LauncherSpec.IO` 协议的一部分，它是一个 `Dict[str, Token]`，包含了所有输入端口的数据。
`node.arg_port_names` 是我们新加的元数据，它是一个 `List[str]`，包含了**应该**作为位置参数的端口名，例如 `["0", "1", "2"]`。

**缺陷在于**：
1.  `test_format_provider` 场景:
    *   调用为 `cs.format("Hello, {name}!", name=get_name())`
    *   `IRGenerator` 正确生成 `NodeIR`：`args=["Hello, {name}!"], kwargs={"name": ...}`
    *   `Expander` 正确生成 `LauncherNode`：`arg_port_names=["0"], kwarg_port_names={"name"}`
    *   `standard_launcher` 运行时，`arg_port_names` 是 `["0"]`。它会查找端口名为 `"0"` 的 `token` 并将其 payload 放入 `input_args`。
    *   然而，对于 `kwargs={"name": ...}`，它会查找端口名为 `"name"` 的 `token`。
    *   **但是！** `IRGenerator` 在生成 `NodeIR` 时，是根据 Python 的调用规则来的。它看到的是 `cs.format(template, name=...)`。它不知道 `name` 最终会进入 `**kwargs`。它只知道 `name` 是一个关键字参数。所以它生成的 `NodeIR.kwargs` 是 `{"name": ...}`。
    *   `standard_launcher` 的逻辑是，它只处理 `arg_port_names` 和 `kwarg_port_names` 中列出的端口。它没有处理那些既不是 `args` 也不是 `kwargs`，但最终会进入 `**kwargs` 的参数。

2.  `test_format_provider_with_positional_args` 场景:
    *   调用为 `cs.format("Positional: {}, {}", get_first(), get_second())`
    *   `IRGenerator` 正确生成 `NodeIR`：`args=["Positional: {}, {}", <...>, <...>]`, `kwargs={}`
    *   `Expander` 正确生成 `LauncherNode`：`arg_port_names=["0", "1", "2"], kwarg_port_names={}`
    *   `standard_launcher` 的循环 `for port_name in node.arg_port_names:` 会按顺序查找 `"0"`, `"1"`, `"2"` 的 `token` 并将它们的 payload 放入 `input_args`。
    *   **但是！** 之前的 `IndexError` 日志显示，`_format_task` 只收到了 `('first',)`。这表明 `template` 和 `second` 丢失了。这意味着 `standard_launcher` 内部的逻辑有严重问题。

**真正的根源**：`standard_launcher` 的逻辑过于复杂，它不应该区分 `arg_port_names` 和 `kwarg_port_names`。物理层只关心端口。逻辑层的 `args` vs `kwargs` 的区别，应该在更高层就被解析并映射到正确的物理端口上。`Expander` 已经做了这件事，它为所有 `args` 和 `kwargs` 都创建了端口。`standard_launcher` 的职责应该极其简单：收集**所有**数据端口的输入，然后根据端口名是数字还是字符串来重建 `args` 和 `kwargs`。我们最初的思路是正确的，只是实现有误。

我将撤销对 `standard_launcher` 的复杂修改，并恢复到一个更简单、更健壮的版本，它不依赖 `arg_port_names` 和 `kwarg_port_names`。这些元数据在 `LauncherNode` 上是多余的，因为 `Expander` 已经将 `args/kwargs` 结构编码到了端口名（数字 vs. 字符串）中。

### 用户需求

一个能够正确处理任何参数组合的 `standard_launcher` 实现。

### 评论

我们绕了一个大圈，但最终回到了问题的本质。复杂性属于编译器，物理执行单元应该尽可能简单。我之前试图在 `standard_launcher` 中添加太多智能，这是一个错误。现在我们将纠正这个设计。

### 目标

1.  **简化 `LauncherNode`**: 移除 `arg_port_names` 和 `kwarg_port_names` 字段。
2.  **简化 `Expander`**: 移除填充这些字段的逻辑。
3.  **修复 `standard_launcher`**: 使用简单、正确的逻辑来从 `io.args` 中重建 `ComputeRequest` 的 `input_args` 和 `input_kwargs`。

### 基本原理

最终的正确逻辑：
1.  `standard_launcher` 接收到一个 `io.args` 字典，其中包含了所有数据输入端口的 `Token`。
2.  它将 `io.args` 字典的键分为两部分：数字字符串键和非数字字符串键。
3.  数字键对应的内容（按键排序）构成 `ComputeRequest` 的 `input_args`。
4.  非数字键（且角色为 DATA）对应的内容构成 `ComputeRequest` 的 `input_kwargs`。
这与 `IRGenerator` 的行为完美匹配，形成了一个端到端一致的参数传递管道。

### 标签

#intent/fix #intent/refine #flow/ready #priority/critical #comp/spec #comp/compiler #comp/std #scope/core #ai/brainstorm #task/domain/compiler #task/object/ir-spec #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 简化 `LauncherNode` 规约

我们将移除之前添加的元数据字段。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/dyad.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from typing import List, Set
from .nodes import PhysicsFuncNode


@dataclass
class LauncherNode(PhysicsFuncNode):
    # The canonical hash of the code to be executed.
    canonical_code_structure_hash: str = ""

    # The explicit ID of the DataNode where the result should be deposited.
    # This eliminates the need for topological guessing.
    reply_to_nid: str = ""

    # Metadata to reconstruct arguments correctly
    arg_port_names: List[str] = field(default_factory=list)
    kwarg_port_names: Set[str] = field(default_factory=set)
~~~~~
~~~~~python.new
from dataclasses import dataclass
from .nodes import PhysicsFuncNode


@dataclass
class LauncherNode(PhysicsFuncNode):
    # The canonical hash of the code to be executed.
    canonical_code_structure_hash: str = ""

    # The explicit ID of the DataNode where the result should be deposited.
    # This eliminates the need for topological guessing.
    reply_to_nid: str = ""
~~~~~

#### Acts 2: 简化 `Expander`

移除填充 `LauncherNode` 元数据字段的逻辑。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        f_launcher = LauncherNode(
            id=f_launch_id,
            name=f"Launch({node_ir.name})",
            input_ports=launcher_inputs,
            # Launcher only has observability output locally.
            # Data output is evaporated to the Queue.
            output_ports={
                "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event")
            },
            canonical_code_structure_hash=canonical_hash,
            reply_to_nid=d_result_id,
            arg_port_names=[str(i) for i in range(len(node_ir.args))],
            kwarg_port_names=set(node_ir.kwargs.keys()),
        )
~~~~~
~~~~~python.new
        f_launcher = LauncherNode(
            id=f_launch_id,
            name=f"Launch({node_ir.name})",
            input_ports=launcher_inputs,
            # Launcher only has observability output locally.
            # Data output is evaporated to the Queue.
            output_ports={
                "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event")
            },
            canonical_code_structure_hash=canonical_hash,
            reply_to_nid=d_result_id,
        )
~~~~~

#### Acts 3: 最终修复 `standard_launcher`

用简单、正确的逻辑重写 `standard_launcher`。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/dyad/launcher.py
~~~~~
~~~~~python.old
@implements(LauncherSpec)
def standard_launcher(io: LauncherSpec.IO, node: LauncherNode, resources: Any) -> None:
    # 1. Prepare Inputs & Trace
    input_args: List[Any] = []
    input_kwargs: Dict[str, Any] = {}
    trace_payload: Dict[str, Any] = {}
    held_resources: List[str] = []

    # Use the metadata from the LauncherNode to reconstruct args and kwargs
    for port_name in node.arg_port_names:
        token = io.args.get(port_name)
        if token:
            input_args.append(token.payload)
            trace_payload.update(token.trace)

    for port_name in node.kwarg_port_names:
        token = io.args.get(port_name)
        if token:
            input_kwargs[port_name] = token.payload
            trace_payload.update(token.trace)

    # Handle other non-data ports like resources
    for port_name, input_token in io.args.items():
        if not input_token or port_name in node.arg_port_names or port_name in node.kwarg_port_names:
            continue

        port_def = node.input_ports[port_name]
        trace_payload.update(input_token.trace)

        if port_def.role == PortRole.RESOURCE:
            held_resources.append(port_name)
            if "resource_amounts" not in trace_payload:
                trace_payload["resource_amounts"] = {}
            trace_payload["resource_amounts"][port_name] = input_token.payload


    start_ts = time.time()  # Wall clock for IR
    mono_ts = time.monotonic()  # Monotonic for internal duration

    # Extract logical ID and Task Name
    # Convention: logical_id is the prefix of the physical ID
    logical_id = node.id.split(".")[0]

    task_name = "unknown"
    if node.name.startswith("Launch(") and node.name.endswith(")"):
        task_name = node.name[7:-1]

    # Update Trace
    trace_payload["start_ts"] = mono_ts
    trace_payload["id"] = logical_id
    if held_resources:
        trace_payload["held_resources"] = held_resources

    # 3. Construct EventIR (STARTED)
    ctx: EventContext = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": start_ts,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": EventState.RUNNING,
            "task_id": logical_id,
            "task_name": task_name,
        },
    }

    # 4. Emit Observability Event
    # The Launcher emits the STARTED event directly.
    io.obs_output = Token(payload=ir, trace=trace_payload)

    # 5. Dispatch Compute Request
    if not node.reply_to_nid:
        raise ValueError(
            f"LauncherNode '{node.id}' is missing 'reply_to_nid'. "
            "Determinism violation: Cannot dispatch without explicit return address."
        )

    if not node.canonical_code_structure_hash:
        raise ValueError(
            f"LauncherNode '{node.id}' is missing 'canonical_code_structure_hash'."
        )

    request = ComputeRequest(
        code_hash=node.canonical_code_structure_hash,
        input_args=input_args,
        input_kwargs=input_kwargs,
        reply_to_nid=node.reply_to_nid,
        trace=trace_payload,  # Trace Tunneling happens here
    )
~~~~~
~~~~~python.new
@implements(LauncherSpec)
def standard_launcher(io: LauncherSpec.IO, node: LauncherNode, resources: Any) -> None:
    # 1. Prepare Inputs & Trace
    pos_args: Dict[int, Any] = {}
    input_kwargs: Dict[str, Any] = {}
    trace_payload: Dict[str, Any] = {}
    held_resources: List[str] = []

    # Iterate over all connected input ports
    for port_name, input_token in io.args.items():
        if not input_token:
            continue

        port_def = node.input_ports[port_name]
        trace_payload.update(input_token.trace)

        if port_def.role == PortRole.DATA:
            if port_name.isdigit():
                pos_args[int(port_name)] = input_token.payload
            else:
                input_kwargs[port_name] = input_token.payload
        elif port_def.role == PortRole.RESOURCE:
            held_resources.append(port_name)
            if "resource_amounts" not in trace_payload:
                trace_payload["resource_amounts"] = {}
            trace_payload["resource_amounts"][port_name] = input_token.payload

    # Reconstruct the final positional args list from the sparse map
    input_args = []
    if pos_args:
        for i in range(max(pos_args.keys()) + 1):
            input_args.append(pos_args.get(i))


    start_ts = time.time()  # Wall clock for IR
    mono_ts = time.monotonic()  # Monotonic for internal duration

    # Extract logical ID and Task Name
    # Convention: logical_id is the prefix of the physical ID
    logical_id = node.id.split(".")[0]

    task_name = "unknown"
    if node.name.startswith("Launch(") and node.name.endswith(")"):
        task_name = node.name[7:-1]

    # Update Trace
    trace_payload["start_ts"] = mono_ts
    trace_payload["id"] = logical_id
    if held_resources:
        trace_payload["held_resources"] = held_resources

    # 3. Construct EventIR (STARTED)
    ctx: EventContext = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": start_ts,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": EventState.RUNNING,
            "task_id": logical_id,
            "task_name": task_name,
        },
    }

    # 4. Emit Observability Event
    # The Launcher emits the STARTED event directly.
    io.obs_output = Token(payload=ir, trace=trace_payload)

    # 5. Dispatch Compute Request
    if not node.reply_to_nid:
        raise ValueError(
            f"LauncherNode '{node.id}' is missing 'reply_to_nid'. "
            "Determinism violation: Cannot dispatch without explicit return address."
        )

    if not node.canonical_code_structure_hash:
        raise ValueError(
            f"LauncherNode '{node.id}' is missing 'canonical_code_structure_hash'."
        )

    request = ComputeRequest(
        code_hash=node.canonical_code_structure_hash,
        input_args=input_args,
        input_kwargs=input_kwargs,
        reply_to_nid=node.reply_to_nid,
        trace=trace_payload,  # Trace Tunneling happens here
    )
~~~~~

### 下一步建议

这次的修改回到了一个更简单、更符合第一性原理的设计。我相信这已经解决了问题的根源。请运行测试套件。如果通过，我们将创建一个 `[COMMIT]` 计划来结束这个漫长但富有成效的重构任务。
