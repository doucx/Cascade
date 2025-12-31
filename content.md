好的，我理解。我们开始执行“架构硬化”任务的第一步：**重构 IR 模型**。

你的分析完全正确。当前的 `NodeIR.inputs` 是一个“贫血”模型，它将本应在编译前端（Frontend）完成的参数解析工作推迟到了后端（Backend），违反了“聪明的 Frontend, 简单的 Backend”这一核心编译原则。

我将生成一个计划，该计划会执行以下操作：
1.  修改 `cascade.spec.ir.models.NodeIR`，废弃 `inputs` 字段，引入 `args: List[Any]` 和 `kwargs: Dict[str, Any]`。
2.  更新 `Frontend`，使其在构建 `NodeIR` 时就负责解析 `LazyResult` 的参数，并填充到新的 `args` 和 `kwargs` 字段中。
3.  简化 `Backend`，使其不再进行参数解析，而是直接消费 `NodeIR` 中清晰的 `args` 和 `kwargs`。
4.  同步更新所有受此变更影响的单元测试。

这将使我们的 IR 结构更加清晰、自文档化，并简化后端逻辑，为未来的优化奠定坚实的基础。

## [WIP] refactor(ir): Refactor NodeIR to separate args and kwargs

### 用户需求
根据“偿还MVP技术债”的规划，重构 IR 模型（`NodeIR`），以明确分离位置参数（`args`）和关键字参数（`kwargs`），并将参数解析逻辑从 Backend 前移至 Frontend。

### 评论
这是一个关键的架构重构。将 `args` 和 `kwargs` 在 IR层面明确分离，可以极大地提高 IR 的可读性和自文档化能力。更重要的是，它将参数解析的复杂性正确地归于 Frontend 的职责范围，使得 Backend 的实现可以显著简化，更专注于代码生成，这完全符合“聪明的 Frontend，简单的 Backend”的设计哲学。

### 目标
1.  修改 `cascade.spec.ir.models.NodeIR` 的数据结构，用 `args: List[Any]` 和 `kwargs: Dict[str, Any]` 替换 `inputs: Dict[str, Any]`。
2.  更新 `cascade.compiler.frontend._GraphBuilder`，使其在访问 `LazyResult` 时，直接将 `LazyResult.args` 和 `LazyResult.kwargs` 解析并填充到 `NodeIR` 的新字段中。
3.  简化 `cascade.compiler.backend._BlueprintBuilder`，移除其内部对数字键的解析逻辑，改为直接消费 `NodeIR.args` 和 `NodeIR.kwargs`。
4.  更新所有因 `NodeIR` 结构变更而失败的单元测试。

### 基本原理
当前 `NodeIR.inputs` 字段是一个混合了位置参数（以数字字符串为键）和关键字参数的 `Dict[str, Any]`。这种“贫血”模型迫使 Backend 在代码生成阶段去反向解析参数的意图，这既职责错位又效率低下。

本次重构通过在 `NodeIR` 中创建 `args` 和 `kwargs` 两个专用字段，将参数的语义在 IR 层面固定下来。`Frontend` 在编译时拥有最完整的上下文信息（`LazyResult` 对象），因此是执行“参数分类”逻辑的唯一正确位置。完成此重构后，IR 成为一个更纯粹、更明确的数据契约，Backend 的逻辑也将因此变得更加健壮和简单。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #comp/spec #concept/ir #scope/core #ai/instruct #task/domain/architecture #task/object/ir-model #task/action/refactor #task/state/begin #task/status/active

---

### Script

#### Acts 1: Refactor `NodeIR` in `cascade-spec`

首先，我们修改核心 IR 数据模型 `NodeIR`。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from cascade.spec.fingerprint import Fingerprint


class EdgeKind(str, Enum):
    DATA = "DATA"  # Standard data dependency
    CONTROL = "CONTROL"  # Conditional execution (run_if)


class ArgumentKind(str, Enum):
    POSITIONAL_ONLY = "POSITIONAL_ONLY"
    POSITIONAL_OR_KEYWORD = "POSITIONAL_OR_KEYWORD"
    VAR_POSITIONAL = "VAR_POSITIONAL"  # *args
    KEYWORD_ONLY = "KEYWORD_ONLY"
    VAR_KEYWORD = "VAR_KEYWORD"  # **kwargs


@dataclass(frozen=True)
class ArgumentDef:
    name: str
    kind: ArgumentKind
    annotation: Optional[str] = None
    default_value_repr: Optional[str] = None


@dataclass(frozen=True)
class TaskDef:
    name: str
    args: List[ArgumentDef]
    # The stable semantic identity of this task definition.
    # Must contain keys like 'current_code_structure_hash'.
    fingerprint: Fingerprint
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    # Execution mode (e.g. "blocking", "compute") derived from the task definition
    mode: str = "blocking"


@dataclass
class NodeIR:
    id: str
    definition: TaskDef
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeIR:
    source_id: str
    target_id: str
    target_arg: str
    kind: EdgeKind = EdgeKind.DATA


@dataclass
class GraphIR:
    nodes: List[NodeIR]
    edges: List[EdgeIR]
    meta: Dict[str, Any] = field(default_factory=dict)


# --- VM Instruction Set ---


@dataclass
class Instruction:
    id: str


@dataclass
class Call(Instruction):
    task_name: str
    args: List[Any]
    output_register: str


@dataclass
class Return(Instruction):
    source_register: str
~~~~~

#### Acts 2: Update `Frontend` to Populate New IR Fields

接下来，修改 `Frontend` 以填充新的 `args` 和 `kwargs` 字段。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
        if node_id not in self.nodes:
            literal_inputs = {
                str(i): arg for i, arg in enumerate(obj.args) if not isinstance(arg, (LazyResult, MappedLazyResult))
            }
            literal_inputs.update(
                {k: val for k, val in obj.kwargs.items() if not isinstance(val, (LazyResult, MappedLazyResult))}
            )

            node = NodeIR(id=node_id, definition=task_def, inputs=literal_inputs)
            self.nodes[node_id] = node
~~~~~
~~~~~python.new
        if node_id not in self.nodes:
            literal_args = [
                arg for arg in obj.args if not isinstance(arg, (LazyResult, MappedLazyResult))
            ]
            literal_kwargs = {
                k: val for k, val in obj.kwargs.items() if not isinstance(val, (LazyResult, MappedLazyResult))
            }

            node = NodeIR(id=node_id, definition=task_def, args=literal_args, kwargs=literal_kwargs)
            self.nodes[node_id] = node
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
        if node_id not in self.nodes:
            literal_inputs = {
                k: val for k, val in obj.mapping_kwargs.items() if not isinstance(val, (LazyResult, MappedLazyResult))
            }
            node = NodeIR(
                id=node_id,
                definition=task_def,
                inputs=literal_inputs,
                meta={"is_map": True}
            )
            self.nodes[node_id] = node
~~~~~
~~~~~python.new
        if node_id not in self.nodes:
            literal_kwargs = {
                k: val for k, val in obj.mapping_kwargs.items() if not isinstance(val, (LazyResult, MappedLazyResult))
            }
            node = NodeIR(
                id=node_id,
                definition=task_def,
                kwargs=literal_kwargs,
                meta={"is_map": True}
            )
            self.nodes[node_id] = node
~~~~~

#### Acts 3: Simplify `Backend` to Consume New IR Fields

现在，简化 `Backend` 的实现，使其直接使用 `node.args` 和 `node.kwargs`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
    def _process_node(self, node_id: str):
        node = self._nodes_map[node_id]

        # 1. Resolve Input Operands & Control Dependencies
        # We use a temporary dictionary to collect all inputs (args and kwargs)
        # and then split them based on keys (digit keys -> args, others -> kwargs)
        all_inputs: Dict[str, Operand] = {}
        control_dependency_reg: Any = None

        # 1a. From Literals
        for key, value in node.inputs.items():
            all_inputs[key] = Literal(value)

        # 1b. From Edges (Dependencies)
        incoming_edges = self._incoming_edges_map.get(node_id, [])
        for edge in incoming_edges:
            # The source node must have been processed in a previous stage,
            # so its output register must be in our map.
            source_register = self._node_output_registers.get(edge.source_id)
            if source_register is None:
                # This indicates a flaw in the ExecutionPlan or this compiler's logic
                raise RuntimeError(
                    f"Compiler Error: Dependency '{edge.source_id}' for node '{node_id}' "
                    "was not assigned a register before being used."
                )
            
            if edge.kind == EdgeKind.CONTROL:
                # We currently support only one control dependency per node for simplicity.
                # If multiple exist, they should ideally be combined (AND logic) in the graph structure.
                control_dependency_reg = source_register
            else:
                all_inputs[edge.target_arg] = source_register

        # 1c. Split into args and kwargs
        # We find keys that are digits "0", "1", ... and map them to the positional list
        args: List[Operand] = []
        kwargs: Dict[str, Operand] = {}
        
        # Determine max positional index
        max_arg_idx = -1
        for k in all_inputs.keys():
            if k.isdigit():
                max_arg_idx = max(max_arg_idx, int(k))
        
        # Pre-fill args list with None (or check for gaps)
        if max_arg_idx >= 0:
            args = [None] * (max_arg_idx + 1) # type: ignore

        for k, v in all_inputs.items():
            if k.isdigit():
                args[int(k)] = v
            else:
                kwargs[k] = v
        
        # Check for gaps in positional args
        if any(a is None for a in args):
             # This might happen if '0' and '2' are provided but '1' is missing.
             # For now, we assume the IR is well-formed or the function has defaults.
             # But Literal(None) would be safer than actual None.
             pass
~~~~~
~~~~~python.new
    def _process_node(self, node_id: str):
        node = self._nodes_map[node_id]

        # 1. Resolve Input Operands & Control Dependencies
        args: List[Operand] = [Literal(val) for val in node.args]
        kwargs: Dict[str, Operand] = {k: Literal(v) for k, v in node.kwargs.items()}
        control_dependency_reg: Any = None

        # 1a. Overlay dependencies from Edges
        incoming_edges = self._incoming_edges_map.get(node_id, [])
        for edge in incoming_edges:
            source_register = self._node_output_registers.get(edge.source_id)
            if source_register is None:
                raise RuntimeError(
                    f"Compiler Error: Dependency '{edge.source_id}' for node '{node_id}' "
                    "was not assigned a register before being used."
                )

            if edge.kind == EdgeKind.CONTROL:
                control_dependency_reg = source_register
            else:
                # Dependency can be positional or keyword
                if edge.target_arg.isdigit():
                    idx = int(edge.target_arg)
                    # Grow args list if necessary
                    while len(args) <= idx:
                        args.append(None) # type: ignore
                    args[idx] = source_register
                else:
                    kwargs[edge.target_arg] = source_register
~~~~~

#### Acts 4: Update Affected Tests

最后，更新因 `NodeIR` 结构变化而受影响的单元测试。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_frontend.py
~~~~~
~~~~~python.old
    node = ir.nodes[0]
    assert node.definition.name == "simple_task"
    assert node.inputs["x"] == 10
~~~~~
~~~~~python.new
    node = ir.nodes[0]
    assert node.definition.name == "simple_task"
    assert node.kwargs["x"] == 10
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_frontend.py
~~~~~
~~~~~python.old
    # The Param LazyResult stores the param name in its args/kwargs
    assert param_node.inputs.get("name") == "my_param" or param_node.inputs.get("0") == "my_param"
~~~~~
~~~~~python.new
    # The Param LazyResult stores the param name in its args/kwargs
    assert param_node.kwargs.get("name") == "my_param" or (len(param_node.args) > 0 and param_node.args[0] == "my_param")
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_frontend.py
~~~~~
~~~~~python.old
    # For now, let's assert that inputs contain the list.
    assert node.inputs["x"] == [1, 2, 3]
~~~~~
~~~~~python.new
    # For now, let's assert that kwargs contain the list.
    assert node.kwargs["x"] == [1, 2, 3]
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend.py
~~~~~
~~~~~python.old
    # Node A(x=1, y="hello")
    task_def = _create_dummy_task_def("task_A")
    node = NodeIR(id="A", definition=task_def, inputs={"x": 1, "y": "hello"})
~~~~~
~~~~~python.new
    # Node A(x=1, y="hello")
    task_def = _create_dummy_task_def("task_A")
    node = NodeIR(id="A", definition=task_def, kwargs={"x": 1, "y": "hello"})
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend.py
~~~~~
~~~~~python.old
    node_b = NodeIR(
        id="B", 
        definition=_create_dummy_task_def("process"),
        inputs={"scale": 2}, # Constant input
        meta={"is_map": True}
    )
~~~~~
~~~~~python.new
    node_b = NodeIR(
        id="B", 
        definition=_create_dummy_task_def("process"),
        kwargs={"scale": 2}, # Constant input
        meta={"is_map": True}
    )
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_compiler_linking.py
~~~~~
~~~~~python.old
    task_def = TaskDef(name="test_task", args=[], fingerprint=fp)
    node = NodeIR(id="n1", definition=task_def, inputs={})
~~~~~
~~~~~python.new
    task_def = TaskDef(name="test_task", args=[], fingerprint=fp)
    node = NodeIR(id="n1", definition=task_def, kwargs={})
~~~~~

### 下一步建议
我们已经对 IR 模型和相关的编译器组件进行了核心重构。下一步是运行 `cascade-compiler` 包的测试套件，以确保我们的修改是正确且没有引入回归问题的。

我建议执行： `pytest packages/cascade-compiler/`
