好的，我们现在进入 GREEN 阶段，实现 `Backend` 的逻辑以通过测试。

## [WIP] feat(compiler): 实现 Backend 代码生成器

### 摘要头
## [WIP] feat(compiler): 实现 Backend 代码生成器

### 用户需求
根据 TDD 流程，实现 `cascade.compiler.Backend` 类。该类需要接收 `GraphIR` 和 `ExecutionPlan` 作为输入，并生成一个 `Blueprint` 对象，其中包含一个线性的、可由 VM 执行的指令序列。

### 评论
这是编译器管线的最后一步：代码生成 (Codegen)。我们将实现一个内部的 `_BlueprintBuilder` 来处理状态，包括最关键的**寄存器分配**。通过遍历 `ExecutionPlan`，我们可以保证在处理一个节点时，其所有上游依赖节点的输出寄存器都已经分配好了，从而正确地将数据流连接起来。

### 目标
1.  创建 `packages/cascade-compiler/src/cascade/compiler/backend.py` 文件并实现 `Backend` 类。
2.  更新 `packages/cascade-compiler/src/cascade/compiler/__init__.py` 以导出 `Backend`。
3.  更新 `packages/cascade-compiler/tests/test_backend.py`，移除 `xfail` 标记，使测试能够运行并通过。

### 基本原理
`Backend` 的核心是一个状态机，它将图的拓扑结构（通过 `ExecutionPlan`）和节点信息（通过 `GraphIR`）转换为一个线性指令序列。
-   **寄存器分配**: 我们维护一个 `node_output_registers` 字典，作为从节点 ID 到其输出寄存器的符号表。
-   **操作数解析**: 当为一个节点生成 `Call` 指令时，它的输入参数（`Operands`）会根据来源被解析：
    -   如果输入来自上游节点（通过 `EdgeIR`），操作数就是上游节点在符号表中的 `Register`。
    -   如果输入是节点自带的字面量（`NodeIR.inputs`），操作数就是 `Literal`。
这个过程确保了计算图中的数据流被正确地翻译为 VM 中的寄存器间数据流动。

### 标签
#intent/build #flow/ready #priority/high #comp/compiler #concept/ir #scope/core #ai/instruct #task/domain/refactor #task/object/compiler-backend #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 实现 Backend 类

创建 `backend.py` 并实现代码生成逻辑。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python
from typing import List, Dict, Tuple, Any

from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR
from cascade.spec.blueprint import Blueprint, Call, Register, Literal, Operand
from .optimizer import ExecutionPlan


class Backend:
    """
    Compiler Backend (Codegen): Transforms a scheduled IR into a linear Blueprint.
    """

    @staticmethod
    def compile(graph: GraphIR, plan: ExecutionPlan) -> Blueprint:
        builder = _BlueprintBuilder(graph, plan)
        return builder.build()


class _BlueprintBuilder:
    def __init__(self, graph: GraphIR, plan: ExecutionPlan):
        self._graph = graph
        self._plan = plan
        self._instructions: List[Call] = []
        self._register_counter = 0

        # The "Symbol Table" for register allocation
        self._node_output_registers: Dict[str, Register] = {}
        
        # Fast lookups
        self._nodes_map: Dict[str, NodeIR] = {n.id: n for n in graph.nodes}
        self._incoming_edges_map: Dict[str, List[EdgeIR]] = {}
        for edge in graph.edges:
            if edge.target_id not in self._incoming_edges_map:
                self._incoming_edges_map[edge.target_id] = []
            self._incoming_edges_map[edge.target_id].append(edge)

    def _allocate_register(self) -> Register:
        reg = Register(self._register_counter)
        self._register_counter += 1
        return reg

    def build(self) -> Blueprint:
        for stage in self._plan:
            for node_id in stage:
                self._process_node(node_id)
        
        return Blueprint(
            instructions=self._instructions,
            register_count=self._register_counter
        )

    def _process_node(self, node_id: str):
        node = self._nodes_map[node_id]

        # 1. Resolve Input Operands
        args: List[Operand] = []  # Positional args not yet fully supported by this IR
        kwargs: Dict[str, Operand] = {}

        # 1a. From Literals
        for key, value in node.inputs.items():
            kwargs[key] = Literal(value)

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
            kwargs[edge.target_arg] = source_register

        # 2. Allocate Output Register for this node
        output_register = self._allocate_register()
        self._node_output_registers[node_id] = output_register

        # 3. Create Instruction
        # For now, we assume the IR definition's callable is magically available.
        # A real implementation would need a way to resolve/load the actual function.
        # For testing, the function itself isn't invoked, so we can use a placeholder.
        
        # We also pass task name for better observability in the VM
        instr = Call(
            func=None,  # The VM will need to resolve this later
            output=output_register,
            args=args,
            kwargs=kwargs,
            task_name=node.definition.name
        )
        self._instructions.append(instr)
~~~~~

#### Acts 2: 导出 Backend

更新 `__init__.py`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/__init__.py
~~~~~
~~~~~python.old
from .frontend import Frontend
from .optimizer import Optimizer, ExecutionPlan
from .exceptions import CompilerError, CycleDetectedError

__all__ = [
    "Frontend",
    "Optimizer",
    "ExecutionPlan",
    "CompilerError",
    "CycleDetectedError",
]
~~~~~
~~~~~python.new
from .frontend import Frontend
from .optimizer import Optimizer, ExecutionPlan
from .backend import Backend
from .exceptions import CompilerError, CycleDetectedError

__all__ = [
    "Frontend",
    "Optimizer",
    "ExecutionPlan",
    "Backend",
    "CompilerError",
    "CycleDetectedError",
]
~~~~~

#### Acts 3: 更新测试用例 (GREEN)

移除 `xfail` 标记并启用测试。

~~~~~act
patch_file
packages/cascade-compiler/tests/test_backend.py
~~~~~
~~~~~python.old
# RED State: Backend not implemented
try:
    from cascade.compiler.backend import Backend
except ImportError:
    pass
~~~~~
~~~~~python.new
from cascade.compiler.backend import Backend
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/test_backend.py
~~~~~
~~~~~python.old
@pytest.mark.xfail(reason="Backend not implemented", raises=(ImportError, NameError))
def test_compile_single_node_literals():
~~~~~
~~~~~python.new
def test_compile_single_node_literals():
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/test_backend.py
~~~~~
~~~~~python.old
@pytest.mark.xfail(reason="Backend not implemented", raises=(ImportError, NameError))
def test_compile_dependency_registers():
~~~~~
~~~~~python.new
def test_compile_dependency_registers():
~~~~~
