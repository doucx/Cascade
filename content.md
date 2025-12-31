好的，我们开始执行“架构硬化”的第一步。我将生成一个计划，重构 `NodeIR` 数据模型，将参数解析的职责从 `Backend` 转移到 `Frontend`。

## [WIP] refactor(compiler): Refine NodeIR to separate args and kwargs

### 用户需求
重构中间表示（IR）模型 `NodeIR`，以明确区分位置参数 (`args`) 和关键字参数 (`kwargs`)。这将把参数解析的复杂性从编译器后端 (`Backend`) 前移至前端 (`Frontend`)，使后端逻辑更简化、更健壮。

### 评论
这是一个关键的架构改进，用于偿还 MVP 阶段的技术债。当前的 `NodeIR.inputs: Dict` 模型语义模糊，迫使 `Backend` 在代码生成时进行不必要的猜测。通过在 IR层面显式分离 `args` 和 `kwargs`，我们遵循了“聪明的 Frontend，简单的 Backend”这一核心编译器设计原则，极大地提高了 IR 的清晰度和整个编译管道的稳定性。

### 目标
1.  **修改 Spec**: 更新 `cascade.spec.ir.models.NodeIR`，用 `args: List[Any]` 和 `kwargs: Dict[str, Any]` 替换 `inputs: Dict[str, Any]`。
2.  **更新 Frontend**: 修改 `cascade.compiler.frontend._GraphBuilder`，使其在构建 `NodeIR` 时直接填充新的 `args` 和 `kwargs` 字段。
3.  **简化 Backend**: 大幅简化 `cascade.compiler.backend._BlueprintBuilder`，使其直接消费 `NodeIR` 中已明确分离的 `args` 和 `kwargs`，移除所有数字键解析逻辑。
4.  **修复测试**: 更新所有依赖旧 `NodeIR.inputs` 结构的单元测试。

### 基本原理
编译器的中间表示（IR）应该是明确且无歧义的。将 Python 中具有不同语义的 `*args` 和 `**kwargs` 混合在一个字典中，是一种信息丢失。本次重构通过使 IR 更精确地反映源语言的语义，将解析责任正确地分配给了 `Frontend`，从而简化了后续的编译阶段，并为未来更高级的优化（如类型分析）奠定了更坚实的基础。

### 标签
#intent/refine #flow/ready #priority/high #comp/spec #comp/compiler #concept/ir #scope/core #task/domain/architecture #task/object/ir-model #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 Spec - 强化 IR 数据模型

我们将修改 `NodeIR` 的定义，使其结构更明确。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
@dataclass
class NodeIR:
    id: str
    definition: TaskDef
    inputs: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)
~~~~~
~~~~~python.new
@dataclass
class NodeIR:
    id: str
    definition: TaskDef
    # Literal positional arguments passed to the task
    args: List[Any] = field(default_factory=list)
    # Literal keyword arguments passed to the task
    kwargs: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)
~~~~~

#### Acts 2: 更新 Frontend - 前移解析逻辑

修改 `Frontend` 以填充新的 `NodeIR` 字段。

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

        for i, arg in enumerate(obj.args):
~~~~~
~~~~~python.new
        if node_id not in self.nodes:
            literal_args = [
                arg for arg in obj.args if not isinstance(arg, (LazyResult, MappedLazyResult))
            ]
            literal_kwargs = {
                k: val for k, val in obj.kwargs.items() if not isinstance(val, (LazyResult, MappedLazyResult))
            }

            node = NodeIR(
                id=node_id,
                definition=task_def,
                args=literal_args,
                kwargs=literal_kwargs,
            )
            self.nodes[node_id] = node

        for i, arg in enumerate(obj.args):
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

        for k, val in obj.mapping_kwargs.items():
~~~~~
~~~~~python.new
        if node_id not in self.nodes:
            literal_kwargs = {
                k: val for k, val in obj.mapping_kwargs.items() if not isinstance(val, (LazyResult, MappedLazyResult))
            }
            node = NodeIR(
                id=node_id,
                definition=task_def,
                # Mapped nodes only have keyword-based mapping
                args=[],
                kwargs=literal_kwargs,
                meta={"is_map": True}
            )
            self.nodes[node_id] = node

        for k, val in obj.mapping_kwargs.items():
~~~~~

#### Acts 3: 简化 Backend - 移除解析逻辑

现在 `Backend` 可以直接消费结构化的 `args` 和 `kwargs`。

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

        # 2. Emit Control Flow Guard (if needed)
        if control_dependency_reg:
~~~~~
~~~~~python.new
    def _process_node(self, node_id: str):
        node = self._nodes_map[node_id]

        # 1. Resolve Input Operands & Control Dependencies
        args: List[Operand] = [Literal(val) for val in node.args]
        kwargs: Dict[str, Operand] = {k: Literal(v) for k, v in node.kwargs.items()}
        control_dependency_reg: Any = None

        # 1a. From Edges (Dependencies) - Overwrite literals
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
                # Determine if it's a positional or keyword argument
                if edge.target_arg.isdigit():
                    arg_idx = int(edge.target_arg)
                    # Ensure args list is long enough
                    if arg_idx >= len(args):
                        args.extend([None] * (arg_idx - len(args) + 1)) # type: ignore
                    args[arg_idx] = source_register
                else:
                    kwargs[edge.target_arg] = source_register
        
        # 2. Emit Control Flow Guard (if needed)
        if control_dependency_reg:
~~~~~

#### Acts 4: 修复受影响的测试

更新 `test_frontend.py` 中对 `node.inputs` 的断言。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_frontend.py
~~~~~
~~~~~python.old
    node = ir.nodes[0]
    assert node.definition.name == "simple_task"
    assert node.inputs["x"] == 10
    
    # 4. Axiom Check: Enforce Long Hash Naming
    # We don't check the value, but the KEY must be the long form.
~~~~~
~~~~~python.new
    node = ir.nodes[0]
    assert node.definition.name == "simple_task"
    assert node.kwargs["x"] == 10
    
    # 4. Axiom Check: Enforce Long Hash Naming
    # We don't check the value, but the KEY must be the long form.
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_frontend.py
~~~~~
~~~~~python.old
    param_node = next(n for n in ir.nodes if n.definition.name == "_get_param_value")
    
    # Check inputs
    # The Param LazyResult stores the param name in its args/kwargs
    assert param_node.inputs.get("name") == "my_param" or param_node.inputs.get("0") == "my_param"


def test_compile_map_node():
~~~~~
~~~~~python.new
    param_node = next(n for n in ir.nodes if n.definition.name == "_get_param_value")
    
    # Check inputs
    # The Param LazyResult stores the param name in its args/kwargs
    assert param_node.kwargs.get("name") == "my_param" or param_node.args[0] == "my_param"


def test_compile_map_node():
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_frontend.py
~~~~~
~~~~~python.old
    # The Frontend must populate a field. Let's assume 'meta' in NodeIR for now.
    assert node.meta.get("is_map") is True
~~~~~
~~~~~python.new
    # The Frontend must populate a field. Let's assume 'meta' in NodeIR for now.
    assert node.kwargs["x"] == [1, 2, 3]
    
    # Spec Requirement: We need to know this is a MAP, not a single call with a list arg.
    # The Frontend must populate a field. Let's assume 'meta' in NodeIR for now.
    assert node.meta.get("is_map") is True
~~~~~
