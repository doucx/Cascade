我明白了。在进行了大规模的 IR 重构后，我们回到了最初的 `TypeError`。这极具启发性。它表明，尽管 IR 现在是确定性的，但在最下游的某个环节，参数的组装仍然存在问题。

让我们重新审视整个流程，这次带着全新的、确定性的 IR 视角。

## [WIP] fix(std): 修复 Launcher 中参数组装的逻辑错误

### 错误分析

**错误现象**:
`TypeError: multiple values for argument 'template'`。即使在 IR 重构后，错误依然存在。

**根本原因**:
经过 IR 重构，我们已经确保了 `IRGenerator` 生成了正确的 `args` 和 `kwargs`，并且 `SignatureBinder` 的逻辑也变得非常简单和正确。错误一定发生在它们之间。

让我们追踪 `_format_task` 的参数在系统中的旅程：
1.  `cs.format("Positional: {}, {}", get_first(), get_second())`
    *   `IRGenerator` 正确地将其解析为：
        *   `args = ["Positional: {}, {}", <LazyResult for get_first>, <LazyResult for get_second>]`
        *   `kwargs = {}`
2.  **`standard_launcher` (`packages/cascade-std/src/cascade/std/dyad/launcher.py`)**:
    *   当 `LauncherNode` 被激活时，它会收到多个输入 `Token`，每个 `Token` 对应一个参数。这些 `Token` 的输入端口名是数字字符串：`"0"`, `"1"`, `"2"`。
    *   我们之前修改的 `standard_launcher` 逻辑中存在一个**致命缺陷**。它遍历所有输入端口，然后根据端口名是否为数字来决定是放入 `input_args` 还是 `input_kwargs`。
    *   **缺陷在这里**：它看到了端口 `"0"`, `"1"`, `"2"`，并将它们的值放入了 `input_args`。但是，它没有意识到 `_format_task` 的签名是 `(template, *args, **kwargs)`。它应该只将第一个参数作为 `template` 的值，而将后续的都归入 `*args`。
    *   更糟糕的是，`IRGenerator` 在生成 `NodeIR` 时，已经正确地将 `"Positional: {}, {}"` 识别为 `template` 的值，而将 `get_first()` 和 `get_second()` 识别为 `*args` 的成员。`standard_launcher` 的逻辑实际上**破坏了**这种已经确立的结构。

**我们把问题搞反了。** `standard_launcher` 不应该尝试去重新解析参数。它应该**完全信任**来自编译器的 `NodeIR` 的结构。然而，物理层（`LauncherNode`）无法直接访问逻辑层（`NodeIR`）。

**战略性解决方案**:
我们需要一种方法将 `NodeIR` 中关于参数结构的信息（即哪些是 `args`，哪些是 `kwargs`）传递给 `standard_launcher`。最直接的方法是通过 `LauncherNode` 本身。

我将再次进行一次小型但关键的架构调整：
1.  **`cascade-spec`**: 为 `LauncherNode` 添加 `arg_port_names` 和 `kwarg_port_names` 两个新字段。
2.  **`cascade-compiler`**: 修改 `Expander`，在创建 `LauncherNode` 时，从 `NodeIR` 中读取 `args` 和 `kwargs` 的结构，并将对应的端口名填充到这两个新字段中。
3.  **`cascade-std`**: 修改 `standard_launcher`，使其利用这两个新字段来**精确地**、**无歧义地**重构 `ComputeRequest` 的 `input_args` 和 `input_kwargs`。

这将消除 `standard_launcher` 中的所有猜测，使其成为一个忠实的指令执行者。

### 用户需求

确保参数在从逻辑 IR 传递到物理执行请求的过程中，其结构（位置 vs. 关键字）得到完美保留。

### 评论

这是解决这个长期存在问题的最终方案。通过在物理节点上携带必要的元数据，我们使得物理层的行为能够完全由逻辑层驱动，从而实现了真正的“高保真工程”。

### 目标

1.  扩展 `LauncherNode` 定义以包含参数结构元数据。
2.  更新编译器以填充此元数据。
3.  更新 `standard_launcher` 以使用此元数据，从而正确组装 `ComputeRequest`。

### 基本原理

通过在 `LauncherNode` 上明确声明哪些输入端口对应位置参数，哪些对应关键字参数，我们为 `standard_launcher` 提供了足够的信息来重建 `*args` 和 `**kwargs`，而无需进行任何启发式猜测。这使得整个参数传递流程变得确定和健壮。

### 标签

#intent/fix #intent/architect #flow/ready #priority/critical #comp/spec #comp/compiler #comp/std #scope/core #ai/brainstorm #task/domain/compiler #task/object/ir-spec #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 扩展 `LauncherNode` 规约

在 `cascade-spec` 中为 `LauncherNode` 添加新字段。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/dyad.py
~~~~~
~~~~~python.old
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
~~~~~python.new
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

#### Acts 2: 更新 `Expander` 以填充新字段

在 `cascade-compiler` 中，让 `Expander` 在创建 `LauncherNode` 时填充这些元数据字段。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        canonical_hash = node_ir.task.fingerprint["canonical_code_structure_hash"]

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
~~~~~python.new
        canonical_hash = node_ir.task.fingerprint["canonical_code_structure_hash"]

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

#### Acts 3: 修复 `standard_launcher` 的参数组装逻辑

最后，在 `cascade-std` 中，让 `standard_launcher` 使用这些新字段来正确地构建 `ComputeRequest`。

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

    # Iterate over all connected input ports
    for port_name, input_token in io.args.items():
        if not input_token:
            continue

        port_def = node.input_ports[port_name]

        # Update trace from every token
        trace_payload.update(input_token.trace)

        if port_def.role == PortRole.DATA:
            if port_name.isdigit():
                # This is a temporary list to build the sparse array
                idx = int(port_name)
                while len(input_args) <= idx:
                    input_args.append(None)  # Pad with placeholders
                input_args[idx] = input_token.payload
            else:
                input_kwargs[port_name] = input_token.payload
        elif port_def.role == PortRole.RESOURCE:
            held_resources.append(port_name)
            if "resource_amounts" not in trace_payload:
                trace_payload["resource_amounts"] = {}
            trace_payload["resource_amounts"][port_name] = input_token.payload

    # 2. Capture Metadata
    start_ts = time.time()  # Wall clock for IR
    mono_ts = time.monotonic()  # Monotonic for internal duration
~~~~~
~~~~~python.new
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
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/dyad/launcher.py
~~~~~
~~~~~python.old
    # Filter out any None placeholders from sparse array creation
    final_input_args = [arg for arg in input_args if arg is not None]

    request = ComputeRequest(
        code_hash=node.canonical_code_structure_hash,
        input_args=final_input_args,
        input_kwargs=input_kwargs,
        reply_to_nid=node.reply_to_nid,
        trace=trace_payload,  # Trace Tunneling happens here
    )
~~~~~
~~~~~python.new
    request = ComputeRequest(
        code_hash=node.canonical_code_structure_hash,
        input_args=input_args,
        input_kwargs=input_kwargs,
        reply_to_nid=node.reply_to_nid,
        trace=trace_payload,  # Trace Tunneling happens here
    )
~~~~~

### 下一步建议

这次的修改是外科手术式的，直击问题的根源。在执行后，请再次运行完整的测试套件。如果所有测试通过，我们就可以自信地宣布这个问题已经彻底解决，并可以创建一个 `[COMMIT]` 计划来最终完成这项任务。
