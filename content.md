简要回答
我们正在执行 TDD 的绿色阶段。我们将 `VirtualMachine.execute` 重构为基于程序计数器 (PC) 的状态机，以支持 `Jump` 和 `JumpIfFalse` 指令。这使 VM 具备了执行分支和循环的能力。

## [WIP] feat(vm): 实现基于 PC 的控制流逻辑

### 用户需求
修改 `packages/cascade-vm/src/cascade/vm/machine.py`，实现对 `Jump` 和 `JumpIfFalse` 指令的支持，使 `test_vm_control_flow.py` 通过。

### 评论
这是 VM 架构的一次重大升级。我们将简单的迭代器循环替换为明确的 Fetch-Decode-Execute 循环（虽然目前 Fetch 和 Decode 还是简化的）。这为后续支持更复杂的控制流（如异常处理块）奠定了基础。

### 目标
1.  在 `machine.py` 中导入 `Jump` 和 `JumpIfFalse`。
2.  重写 `execute` 方法，使用 `pc` (程序计数器) 和 `while` 循环遍历指令。
3.  在循环内部处理跳转指令修改 `pc` 的逻辑。

### 基本原理
控制流指令的核心作用是修改执行顺序，这在 `for instr in instructions` 的迭代模式下是无法实现的。显式的 PC 管理是实现图灵完备虚拟机的标准做法。

### 标签
#intent/build #flow/ready #priority/high #comp/vm #concept/control-flow #task/domain/core #task/object/vm-loop #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 VM 执行循环

我们将导入新的指令类型，并重构 `execute` 方法以支持跳转。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
from cascade.spec.blueprint import (
    Blueprint,
    Instruction,
    Call,
    Literal,
    Register,
    Operand,
    TailCall,
)
from cascade.spec.ir.models import TaskDef
~~~~~
~~~~~python.new
from cascade.spec.blueprint import (
    Blueprint,
    Instruction,
    Call,
    Literal,
    Register,
    Operand,
    TailCall,
    Jump,
    JumpIfFalse,
)
from cascade.spec.ir.models import TaskDef
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
        # 3. Main Execution Loop
        while True:
            last_result = None

            for instr in current_blueprint.instructions:
                last_result = await self._dispatch(instr, frame)

            # TCO Logic
            if isinstance(last_result, TailCall):
                if last_result.target_blueprint_id:
~~~~~
~~~~~python.new
        # 3. Main Execution Loop
        while True:
            pc = 0
            instructions = current_blueprint.instructions
            last_result = None

            while pc < len(instructions):
                instr = instructions[pc]

                # Handle Control Flow
                if isinstance(instr, Jump):
                    pc += instr.offset
                    continue

                if isinstance(instr, JumpIfFalse):
                    val = frame.load(instr.condition)
                    if not val:
                        pc += instr.offset
                    else:
                        pc += 1
                    continue

                # Handle Standard Instructions
                last_result = await self._dispatch(instr, frame)
                pc += 1

            # TCO Logic
            if isinstance(last_result, TailCall):
                if last_result.target_blueprint_id:
~~~~~

### 下一步建议
现在所有的 VM 单元测试（包括控制流测试）都应该通过了。

接下来的挑战是**功能对齐**（阶段 6）。我们需要让 `Compiler` 能够利用这些新指令。具体来说，我们需要支持将 `LazyResult.run_if(condition)` 编译为 `JumpIfFalse` 指令序列。

建议的下一步是：
1.  在 `packages/cascade-compiler/tests/unit/test_backend.py` 中添加一个新的测试用例，验证 Backend 能否将带有条件分支的 IR 编译为包含 `JumpIfFalse` 的 Blueprint。
2.  修改 Backend 实现该逻辑。
