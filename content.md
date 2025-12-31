简要回答
我们正在进行 **Phase 0 (Spec)** 的补充工作，以支持 **Phase 6 (功能对齐)**。

为了以“正规军”的方式支持条件执行，我们拒绝在 Backend 中根据参数名（如 `_condition`）进行硬编码判断。相反，我们将在 IR 层面显式引入 `EdgeKind` 概念。这将使 `Frontend` 能够准确表达控制流意图，`Backend` 能够据此生成跳转指令。

## [WIP] feat(spec): 在 IR 中引入 EdgeKind 以支持控制流

### 用户需求
1.  升级 `cascade-spec`，在 IR 中显式区分数据边（DATA）和控制边（CONTROL）。
2.  在 `cascade-compiler` 中编写测试，验证 Backend 能利用此信息生成 `JumpIfFalse` 指令。

### 评论
这是架构演进的关键一步。通过将控制流语义下沉到 IR 数据结构中，我们避免了“魔法字符串”带来的脆弱性。这也为未来支持更复杂的控制流（如循环回边、异常处理边）预留了扩展空间。

### 目标
1.  在 `cascade.spec.ir.models` 中添加 `EdgeKind` 枚举。
2.  更新 `EdgeIR` 定义，包含 `kind` 字段。
3.  在 `test_backend.py` 中添加针对条件执行的编译测试。

### 基本原理
IR (中间表示) 必须包含足够的信息来驱动代码生成，而无需 Backend 去猜测 Frontend 的意图。显式的边类型是图编译器中处理控制流的标准做法。

### 标签
#intent/architect #flow/ready #priority/high #comp/spec #comp/compiler #concept/ir #task/domain/core #task/object/control-flow #task/action/design #task/state/continue

---

### Script

#### Acts 1: 更新 Spec 定义 (IR Models)

我们在 IR 中引入 `EdgeKind` 枚举，并将其添加到 `EdgeIR` 中。默认为 `DATA` 以保持向后兼容性（在代码层面，虽然这里是数据类更新）。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from cascade.spec.fingerprint import Fingerprint


class ArgumentKind(str, Enum):
    POSITIONAL_ONLY = "POSITIONAL_ONLY"
    POSITIONAL_OR_KEYWORD = "POSITIONAL_OR_KEYWORD"
~~~~~
~~~~~python.new
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
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
@dataclass
class EdgeIR:
    source_id: str
    target_id: str
    target_arg: str


@dataclass
class GraphIR:
~~~~~
~~~~~python.new
@dataclass
class EdgeIR:
    source_id: str
    target_id: str
    target_arg: str
    kind: EdgeKind = EdgeKind.DATA


@dataclass
class GraphIR:
~~~~~

#### Acts 2: 导出新类型

确保新类型在 `__init__.py` 中可见。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/__init__.py
~~~~~
~~~~~python.old
from .models import (
    ArgumentKind,
    ArgumentDef,
    TaskDef,
    GraphIR,
    NodeIR,
    EdgeIR,
    Instruction,
    Call,
    Return,
)

__all__ = [
    "ArgumentKind",
    "ArgumentDef",
    "TaskDef",
    "GraphIR",
    "NodeIR",
    "EdgeIR",
    "Instruction",
    "Call",
    "Return",
]
~~~~~
~~~~~python.new
from .models import (
    EdgeKind,
    ArgumentKind,
    ArgumentDef,
    TaskDef,
    GraphIR,
    NodeIR,
    EdgeIR,
    Instruction,
    Call,
    Return,
)

__all__ = [
    "EdgeKind",
    "ArgumentKind",
    "ArgumentDef",
    "TaskDef",
    "GraphIR",
    "NodeIR",
    "EdgeIR",
    "Instruction",
    "Call",
    "Return",
]
~~~~~

#### Acts 3: 编写 Backend 测试用例

现在 Spec 已经支持，我们可以在 Compiler 中编写测试了。这个测试模拟了一个 `A ->(Control)-> B` 的场景，并断言生成的 Blueprint 中包含 `JumpIfFalse`。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend.py
~~~~~
~~~~~python.old
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.blueprint import Blueprint, Call, Register, Literal

from cascade.compiler.backend import Backend
~~~~~
~~~~~python.new
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.blueprint import Blueprint, Call, Register, Literal, JumpIfFalse

from cascade.compiler.backend import Backend
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend.py
~~~~~
~~~~~python.old
    assert isinstance(operand_in_b, Register)
    assert operand_in_b.index == reg_out_a.index
~~~~~
~~~~~python.new
    assert isinstance(operand_in_b, Register)
    assert operand_in_b.index == reg_out_a.index


def test_compile_conditional_execution():
    """
    Case 3: Conditional Execution (A -[CONTROL]-> B).
    Verify that Backend generates a JumpIfFalse instruction before B.
    """
    # 1. Setup IR
    # A produces a boolean. B executes only if A is True.
    node_a = NodeIR(id="A", definition=_create_dummy_task_def("condition"))
    node_b = NodeIR(id="B", definition=_create_dummy_task_def("action"))
    
    # Control edge: A -> B
    # target_arg is typically ignored or used for metadata in control edges
    edge = EdgeIR(source_id="A", target_id="B", target_arg="_condition", kind=EdgeKind.CONTROL)
    
    ir = GraphIR(
        nodes=[node_a, node_b],
        edges=[edge]
    )
    plan = [["A"], ["B"]] # Two stages

    # 2. Execute Backend
    blueprint = Backend.compile(ir, plan)

    # 3. Assertions
    # Expected sequence:
    # 0: Call(condition) -> R_a
    # 1: JumpIfFalse(R_a, offset=2) -> Skip next instruction
    # 2: Call(action)
    
    assert len(blueprint.instructions) == 3
    
    instr_0 = blueprint.instructions[0]
    instr_1 = blueprint.instructions[1]
    instr_2 = blueprint.instructions[2]
    
    # Check 0: Condition
    assert isinstance(instr_0, Call)
    assert instr_0.task_name == "condition"
    reg_cond = instr_0.output
    
    # Check 1: Jump
    assert isinstance(instr_1, JumpIfFalse)
    assert instr_1.condition.index == reg_cond.index
    # Offset should skip exactly one instruction (instr_2)
    # The jump is relative to the jump instruction itself? 
    # Or usually relative to PC+1.
    # In our VM implementation:
    # if not val: pc += offset
    # So if we are at PC=1, and we want to go to PC=3 (after action),
    # 1 + offset = 3 => offset = 2.
    assert instr_1.offset == 2
    
    # Check 2: Action
    assert isinstance(instr_2, Call)
    assert instr_2.task_name == "action"
~~~~~

### 下一步建议
测试现在会失败（RED），因为 `Backend` 尚未处理 `EdgeKind.CONTROL`。我们需要修改 `cascade-compiler` 的 `Backend` 来实现这一逻辑。这将涉及在生成指令流时插入跳转指令，并计算正确的偏移量。这是一个稍微复杂一点的算法挑战（可能需要 Backpatching 或简单的预计算）。
