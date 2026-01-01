分析非常准确。当前的物理引擎在处理 `Map` 操作和位置参数映射时存在两个核心漏洞：

1.  **Map 逻辑缺失**：`PhysicsExecutor` 目前只是简单地调用 Python 函数。当输入是一个列表（如 `[1, 2, 3]`）且该节点在 IR 中被标记为 `is_map` 时，它应该执行向量化操作，而不是直接将列表传给函数（导致了 `[1, 2, 3] * 2` 变成了 `[1, 2, 3, 1, 2, 3]`）。
2.  **位置参数映射错误**：`Backend` 目前粗暴地将位置参数命名为 `"0"`, `"1"` 等。在 Python 中，除非函数定义了 `*args` 或位置唯一参数，否则 `**{"0": val}` 会触发 `TypeError`。我们需要利用 `TaskDef` 中的反射信息，将位置参数还原为它们在函数签名中的真实名称。

我将生成一个计划来完善物理模型的执行契约。

## [WIP] fix: 实现物理引擎的 Map 执行逻辑与参数名称对齐

### 错误分析
1.  **Map 失败**：`test_vm_integration_map_flow` 返回了 `[1, 2, 3, 1, 2, 3]`。这是因为 `double([1, 2, 3])` 被执行了，而物理执行器没有识别出这是一个需要对输入进行迭代的 Map 任务。
2.  **参数名不匹配**：`test_vm_integration_control_flow_true` 报错 `got an unexpected keyword argument '0'`。这是因为 `Backend` 将 `conditional_step("A")` 的第一个参数硬编码为 `"0"`，而 Python 函数期待的是 `val`。

### 用户需求
1.  支持 `PhysicsFuncNode` 的 Map 模式执行。
2.  在编译阶段将位置参数正确映射到其反射得到的名称。

### 评论
这是物理模型走向成熟的必经阶段。通过将编译器捕获的静态反射信息（`TaskDef`）透传给后端，并让执行器具备处理 Map 语义的能力，我们实现了从“简单函数调用”到“工作流原语执行”的跨越。

### 目标
1.  在 `PhysicsFuncNode` 规格中增加 `is_map` 标识。
2.  更新 `Backend` 以使用 `TaskDef` 中的参数名进行输入绑定。
3.  在 `PhysicsExecutor` 中实现 Map 模式下的向量化执行逻辑。

### 基本原理
1.  **参数还原**：`Backend` 在处理 `NodeIR.args` 时，应查阅 `node_ir.definition.args` 列表，按索引获取对应的 `name`。
2.  **向量化**：当 `is_map` 为真时，`PhysicsExecutor` 应对 `kwargs` 中的所有列表进行 zip 对齐，并循环调用函数，最后将结果收集回列表。

### 标签
#intent/fix #flow/ready #priority/high #comp/compiler #comp/vm #concept/physics #scope/api #ai/refine #task/domain/vm #task/object/executor #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 `topology.py` 增加 `is_map` 支持

我们需要在 `PhysicsFuncNode` 中记录这是否是一个 Map 任务。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class PhysicsFuncNode:
    """
    Represents a computational instance in the physical bipartite graph.
    This is the "Verb" or the transformer.
    """

    current_node_instance_hash: str
    # The stable, linkable identity used to look up the executable code in the symbol table.
    canonical_code_structure_hash: str
    name: str
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)
    # If not None, this node acts as an Emitter, pushing its result to the specified sink.
    sink_id: Optional[str] = field(default=None)
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class PhysicsFuncNode:
    """
    Represents a computational instance in the physical bipartite graph.
    This is the "Verb" or the transformer.
    """

    current_node_instance_hash: str
    # The stable, linkable identity used to look up the executable code in the symbol table.
    canonical_code_structure_hash: str
    name: str
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)
    # If not None, this node acts as an Emitter, pushing its result to the specified sink.
    sink_id: Optional[str] = field(default=None)
    is_map: bool = False
~~~~~

#### Acts 2: 更新 `physics.py` 增加 `is_map` 运行时支持

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
class FuncNode:
    """
    Stateless transformer. Represents the 'Verb' in the physics model.
    """

    def __init__(
        self,
        name: str,
        canonical_code_structure_hash: str,
        resource_requirements: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.canonical_code_structure_hash = canonical_code_structure_hash
        self.resource_requirements = resource_requirements or {}
        self.inputs: Dict[str, Port] = {}
        self.outputs: Dict[str, Port] = {}
~~~~~
~~~~~python.new
class FuncNode:
    """
    Stateless transformer. Represents the 'Verb' in the physics model.
    """

    def __init__(
        self,
        name: str,
        canonical_code_structure_hash: str,
        resource_requirements: Optional[Dict[str, Any]] = None,
        is_map: bool = False,
    ):
        self.name = name
        self.canonical_code_structure_hash = canonical_code_structure_hash
        self.resource_requirements = resource_requirements or {}
        self.is_map = is_map
        self.inputs: Dict[str, Port] = {}
        self.outputs: Dict[str, Port] = {}
~~~~~

#### Acts 3: 优化 `Backend` 的参数映射逻辑

我们将 `str(i)` 替换为基于 `TaskDef` 的真实参数名映射，并透传 `is_map`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
    def _process_node(self, node_ir: NodeIR):
        current_node_instance_hash = node_ir.current_node_instance_hash

        f_node = PhysicsFuncNode(
            current_node_instance_hash=current_node_instance_hash,
            canonical_code_structure_hash=node_ir.definition.canonical_code_structure_hash,
            name=node_ir.definition.name,
            inputs={},
            sink_id=None,  # Explicitly set sink_id to None for regular nodes
        )
        self._func_nodes[current_node_instance_hash] = f_node

        for i, val in enumerate(node_ir.args):
            self._process_literal(f_node, str(i), val)

        for k, val in node_ir.kwargs.items():
            self._process_literal(f_node, k, val)
~~~~~
~~~~~python.new
    def _process_node(self, node_ir: NodeIR):
        current_node_instance_hash = node_ir.current_node_instance_hash

        f_node = PhysicsFuncNode(
            current_node_instance_hash=current_node_instance_hash,
            canonical_code_structure_hash=node_ir.definition.canonical_code_structure_hash,
            name=node_ir.definition.name,
            inputs={},
            sink_id=None,
            is_map=node_ir.meta.get("is_map", False),
        )
        self._func_nodes[current_node_instance_hash] = f_node

        # Map positional arguments to their real names from TaskDef
        for i, val in enumerate(node_ir.args):
            arg_name = node_ir.definition.args[i].name
            self._process_literal(f_node, arg_name, val)

        for k, val in node_ir.kwargs.items():
            self._process_literal(f_node, k, val)
~~~~~

#### Acts 4: 在 `VMExecutionStrategy` 中透传 `is_map`

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
        # Pass 2: Instantiate all FuncNodes and wire their inputs
        for spec_f_node in topology.func_nodes.values():
            if spec_f_node.sink_id:
                f_node = EmitterNode(
                    name=spec_f_node.current_node_instance_hash,
                    canonical_code_structure_hash=spec_f_node.canonical_code_structure_hash,
                    sink_id=spec_f_node.sink_id,
                )
            else:
                f_node = FuncNode(
                    name=spec_f_node.current_node_instance_hash,
                    canonical_code_structure_hash=spec_f_node.canonical_code_structure_hash,
                )
~~~~~
~~~~~python.new
        # Pass 2: Instantiate all FuncNodes and wire their inputs
        for spec_f_node in topology.func_nodes.values():
            if spec_f_node.sink_id:
                f_node = EmitterNode(
                    name=spec_f_node.current_node_instance_hash,
                    canonical_code_structure_hash=spec_f_node.canonical_code_structure_hash,
                    sink_id=spec_f_node.sink_id,
                )
            else:
                f_node = FuncNode(
                    name=spec_f_node.current_node_instance_hash,
                    canonical_code_structure_hash=spec_f_node.canonical_code_structure_hash,
                    is_map=spec_f_node.is_map,
                )
~~~~~

#### Acts 5: 升级 `PhysicsExecutor` 支持 Map 执行逻辑

我们将实现向量化逻辑。如果 `is_map` 为真，我们会对输入参数进行对齐并并行/串行调用。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/executors/physics.py
~~~~~
~~~~~python.old
            # 3. Execution
            result = func(**kwargs)
            if inspect.isawaitable(result):
                result = await result

            # 4. Wrap Result: Convert the raw result back into a Token.
~~~~~
~~~~~python.new
            # 3. Execution
            if node.is_map:
                # Vectorized Execution (Map)
                # 1. Determine lengths and extract iterables
                iterables = {k: v for k, v in kwargs.items() if isinstance(v, list)}
                constants = {k: v for k, v in kwargs.items() if not isinstance(v, list)}
                
                if not iterables:
                    # If nothing is a list, map behaves like a regular call returning a list
                    result = [func(**kwargs)]
                else:
                    first_len = len(next(iter(iterables.values())))
                    results = []
                    for i in range(first_len):
                        call_kwargs = constants.copy()
                        for k, v_list in iterables.items():
                            call_kwargs[k] = v_list[i]
                        
                        r = func(**call_kwargs)
                        results.append(r)
                    
                    # Handle async items in results if necessary
                    if inspect.iscoroutinefunction(func):
                        result = await asyncio.gather(*results)
                    else:
                        result = results
            else:
                # Scalar Execution
                result = func(**kwargs)
                if inspect.isawaitable(result):
                    result = await result

            # 4. Wrap Result: Convert the raw result back into a Token.
~~~~~

### 下一步建议
应用这些修改后，`test_integration_map_control.py` 应该能够通过。
1. `double.map` 现在会正确触发向量化分支。
2. `conditional_step("A")` 的输入端口现在会正确命名为 `val`，从而匹配 Python 函数签名。
完成后，建议继续运行测试套件，检查是否有由于参数名映射导致的其他意外不匹配。
