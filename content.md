简要回答
我们正在 **Phase 6 (功能对齐)** 的实施阶段。测试 `test_compile_conditional_execution` 失败（预期内，assert 2 == 3 表明生成的指令数是 2 而不是 3），因为 `Backend` 目前忽略了控制边，只生成了两个 `Call` 指令，缺少了中间的 `JumpIfFalse`。

我们将修改 `Backend` 的指令生成逻辑。由于我们已经有了拓扑排序后的 `ExecutionPlan`，我们可以在处理每个 Node 时，检查其是否受控于某个前序 Node（即存在入站 CONTROL 边）。

## [WIP] feat(compiler): Backend 实现控制流指令生成

### 用户需求
修改 `packages/cascade-compiler/src/cascade/compiler/backend.py`，使其能够识别 `EdgeKind.CONTROL` 类型的边，并在受控节点执行前插入 `JumpIfFalse` 指令。

### 评论
对于 `Backend` 来说，处理控制流最简单的方式是“前置守卫 (Pre-guarding)”。当我们准备生成某个 Node 的 `Call` 指令时，我们先检查它是否有入站控制边。如果有，我们在 `Call` 之前插入一个 `JumpIfFalse`，指向 `Call` 之后的位置。

注意：目前的 `ExecutionPlan` 只是简单的分层列表。在更复杂的场景（嵌套条件）下，这种简单的插入可能不够，但在当前 MVP 阶段，它足以支持基本的 `run_if`。

### 目标
1.  在 `_BlueprintBuilder` 中引入对 `EdgeKind` 的处理。
2.  在处理 Node 时，识别控制依赖。
3.  生成 `JumpIfFalse` 指令，并正确计算 `offset`（对于单指令跳过，offset 固定为 2）。

### 基本原理
我们利用 `_incoming_edges_map` 来查找依赖。如果发现 `EdgeKind.CONTROL`，我们获取源节点的输出寄存器，并生成跳转指令。

### 标签
#intent/build #flow/ready #priority/high #comp/compiler #concept/codegen #task/domain/core #task/object/backend #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 更新 Backend 逻辑

我们需要导入新的指令类型和枚举，并修改 `_process_node` 方法。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
from typing import List, Dict, Tuple, Any

from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR
from cascade.spec.blueprint import Blueprint, Call, Register, Literal, Operand
from .optimizer import ExecutionPlan
~~~~~
~~~~~python.new
from typing import List, Dict, Tuple, Any

from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind
from cascade.spec.blueprint import Blueprint, Call, Register, Literal, Operand, JumpIfFalse
from .optimizer import ExecutionPlan
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
    def _process_node(self, node_id: str):
        node = self._nodes_map[node_id]

        # 1. Resolve Input Operands & Control Dependencies
        args: List[Operand] = []  # Positional args not yet fully supported by this IR
        kwargs: Dict[str, Operand] = {}
        control_dependency_reg: Any = None

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
            
            if edge.kind == EdgeKind.CONTROL:
                # We currently support only one control dependency per node for simplicity.
                # If multiple exist, they should ideally be combined (AND logic) in the graph structure.
                control_dependency_reg = source_register
            else:
                kwargs[edge.target_arg] = source_register

        # 2. Emit Control Flow Guard (if needed)
        if control_dependency_reg:
            # JumpIfFalse offset=2 means skip the next instruction (which is length 1)
            # Layout: [JumpIfFalse, Call]
            # If false, PC += 2. From index i, lands on i+2 (after Call).
            jump = JumpIfFalse(condition=control_dependency_reg, offset=2)
            self._instructions.append(jump)

        # 3. Allocate Output Register for this node
        output_register = self._allocate_register()
        self._node_output_registers[node_id] = output_register
~~~~~

### 下一步建议
如果此测试通过，`Backend` 和 `VM` 在控制流方面就初步对齐了。

现在的缺环是 `Frontend`。我们需要更新 `packages/cascade-compiler/src/cascade/compiler/frontend.py`，使其在解析 `LazyResult` 时，能够识别 `_condition` 属性，并生成 `EdgeKind.CONTROL` 类型的边。

建议的步骤：
1.  在 `test_frontend.py` 中添加测试用例，验证 `Frontend` 能正确将 `t.run_if(c)` 转换为带有 `EdgeKind.CONTROL` 的 `GraphIR`。
2.  修改 `Frontend` 实现此逻辑。
