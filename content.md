好的，我们立即开始第二阶段。

这是对 `cascade-vm` 单元测试进行范式迁移的计划。我们将系统性地重构这些测试，使其完全符合新的、解耦的“哈希 + 符号表”架构，从而将测试套件从红色状态恢复为绿色。

## [WIP] test: 对齐 VM 单元测试以使用基于哈希的链接

### 用户需求
更新 `packages/cascade-vm/tests/unit/` 目录中所有失败的单元测试，使其遵循新的架构范式。在该范式中，`Blueprint` 指令是纯粹的数据，而函数链接的责任已下放到 `VirtualMachine`，通过 `symbol_table` 在运行时完成。

### 评论
这是巩固“净化 `Blueprint`”架构重构成果的关键一步。通过重构这些核心单元测试，我们不仅修复了构建，更重要的是，我们正在创建与新 VM 交互的权威范例，有效地“吃自己的狗粮”。这确保了 VM 的新接口不仅在理论上是正确的，在实践中也是健壮、可用且可测试的。

### 目标
1.  修改 `test_vm_basic.py`、`test_vm_control_flow.py` 和 `test_vm_map.py` 文件。
2.  在每个测试用例中，从 `Call` 和 `MapCall` 的实例化中移除已废弃的 `func=` 关键字参数。
3.  用 `structure_hash="some_hash_key"` 参数替换它。
4.  为每个测试用例创建一个 `symbol_table` 字典，将哈希键映射到实际的测试辅助函数（如 `_add`, `append_val` 等）。
5.  更新对 `vm.execute(...)` 的调用，将 `symbol_table` 作为新参数传递。
6.  确保所有被修改的测试用例都能成功通过。

### 基本原理
旧的测试直接将运行时函数对象 (`func`) 嵌入到 `Call` 指令中，这与我们将 `Blueprint` 净化为纯粹、可序列化数据结构的核心目标相违背。新的架构将编译产物 (`Blueprint`) 与运行时环境 (`symbol_table`) 彻底解耦。因此，测试必须更新以反映这种架构上的分离。修改后的测试将明确验证 VM 的新契约：它是一个接收指令集和链接清单 (`symbol_table`) 的纯粹执行器。

### 标签
#intent/refine #intent/tooling #flow/ready #priority/high #comp/tests #concept/executor #scope/dx #ai/instruct #task/domain/architecture #task/object/legacy-vm #task/action/removal #task/state/continue

---

### Script

#### Acts 1: 更新 `test_vm_basic.py`

我们将重写此文件，引入 `symbol_table` 并使用 `structure_hash` 替代 `func`。

~~~~~act
write_file
packages/cascade-vm/tests/unit/test_vm_basic.py
~~~~~
~~~~~python
import pytest
import asyncio
from cascade.spec.blueprint import Blueprint, Call, Register, Literal
from cascade.vm import VirtualMachine


def _add(a: int, b: int) -> int:
    """Helper function for testing synchronous execution."""
    return a + b


async def _async_add(a: int, b: int) -> int:
    """Helper function for testing asynchronous execution."""
    await asyncio.sleep(0.01)
    return a + b


@pytest.mark.asyncio
async def test_vm_instruction_execution():
    """
    Case 1: The CPU Test (Synchronous).
    Manually construct a program:
      r0 = add(1, 2)
      r1 = add(r0, 3)
    Verify that r1 contains 6.
    """
    symbol_table = {
        "hash_for_add": _add,
    }

    # Program:
    # 1. r0 = _add(1, 2)
    instr1 = Call(
        structure_hash="hash_for_add",
        output=Register(0),
        args=[Literal(1), Literal(2)],
        kwargs={},
        task_name="add_1",
    )

    # 2. r1 = _add(r0, 3)
    instr2 = Call(
        structure_hash="hash_for_add",
        output=Register(1),
        args=[Register(0), Literal(3)],
        kwargs={},
        task_name="add_2",
    )

    blueprint = Blueprint(
        instructions=[instr1, instr2],
        register_count=2,
        input_args=[],
        input_kwargs={},
    )

    vm = VirtualMachine()
    result = await vm.execute(blueprint, symbol_table)

    # The result of the last instruction should be returned
    assert result == 6


@pytest.mark.asyncio
async def test_vm_async_execution():
    """
    Case 2: Async Execution.
    Manually construct a program:
      r0 = async_add(10, 20)
    Verify that VM awaits the result correctly.
    """
    symbol_table = {
        "hash_for_async_add": _async_add,
    }

    instr = Call(
        structure_hash="hash_for_async_add",
        output=Register(0),
        args=[Literal(10), Literal(20)],
        kwargs={},
        task_name="async_add",
    )

    blueprint = Blueprint(
        instructions=[instr],
        register_count=1,
        input_args=[],
        input_kwargs={},
    )

    vm = VirtualMachine()
    result = await vm.execute(blueprint, symbol_table)

    assert result == 30
~~~~~

#### Acts 2: 更新 `test_vm_control_flow.py`

同样，我们将重构此文件中的所有测试用例以适应新架构。

~~~~~act
write_file
packages/cascade-vm/tests/unit/test_vm_control_flow.py
~~~~~
~~~~~python
import pytest
from typing import List

from cascade.spec.blueprint import Blueprint, Call, Register, Literal, Jump, JumpIfFalse
from cascade.vm import VirtualMachine

# --- Helpers ---


def append_val(log: List[int], val: int):
    log.append(val)


def decrement(x: int) -> int:
    return x - 1


def is_positive(x: int) -> bool:
    return x > 0


# --- Symbol Table for all tests in this module ---

SYMBOL_TABLE = {
    "hash_append": append_val,
    "hash_decrement": decrement,
    "hash_is_positive": is_positive,
}


# --- Tests ---


@pytest.mark.asyncio
async def test_vm_jump_skips_instruction():
    """
    Verify Jump(offset) skips intermediate instructions.

    Program:
    0: Jump(2)   -> Goto 2
    1: Call(append, 1)  (Should be skipped)
    2: Call(append, 2)  (Should be executed)
    """
    log = []

    instrs = [
        # 0: Jump to index 2 (0 + 2 = 2)
        Jump(offset=2),
        # 1:
        Call(
            structure_hash="hash_append",
            output=Register(0),  # Dummy output
            args=[Literal(log), Literal(1)],
            task_name="log_1",
        ),
        # 2:
        Call(
            structure_hash="hash_append",
            output=Register(0),
            args=[Literal(log), Literal(2)],
            task_name="log_2",
        ),
    ]

    bp = Blueprint(instructions=instrs, register_count=1)
    vm = VirtualMachine()
    await vm.execute(bp, SYMBOL_TABLE)

    assert log == [2]


@pytest.mark.asyncio
async def test_vm_jump_if_false_branching():
    """
    Verify JumpIfFalse branches correctly based on register value.

    Program:
    0: R0 = input (cond)
    1: JumpIfFalse(R0, 2) -> Goto 3 if False
    2: Call(append, 1)    (Skipped if False)
    3: Call(append, 2)    (Executed)
    """
    log = []

    instrs = [
        JumpIfFalse(condition=Register(0), offset=2),
        Call(
            structure_hash="hash_append",
            output=Register(1),
            args=[Literal(log), Literal(1)],
            task_name="log_1",
        ),
        Call(
            structure_hash="hash_append",
            output=Register(1),
            args=[Literal(log), Literal(2)],
            task_name="log_2",
        ),
    ]

    bp = Blueprint(instructions=instrs, register_count=2, input_kwargs={"cond": 0})
    vm = VirtualMachine()

    # Case 1: Condition is False (Should Jump to 2, skipping 1)
    log.clear()
    await vm.execute(bp, SYMBOL_TABLE, initial_kwargs={"cond": False})
    assert log == [2]

    # Case 2: Condition is True (Should NOT Jump, executing 1 then 2)
    log.clear()
    await vm.execute(bp, SYMBOL_TABLE, initial_kwargs={"cond": True})
    assert log == [1, 2]


@pytest.mark.asyncio
async def test_vm_loop_backward_jump():
    """
    Verify backward jump creates a working loop.
    """
    log = []

    instrs = [
        # 0: R1 = R0 > 0
        Call(
            structure_hash="hash_is_positive",
            output=Register(1),
            args=[Register(0)],
            task_name="check_pos",
        ),
        # 1: if not R1 goto 5
        JumpIfFalse(condition=Register(1), offset=4),
        # 2: log.append(R0)
        Call(
            structure_hash="hash_append",
            output=Register(2),
            args=[Literal(log), Register(0)],
            task_name="log",
        ),
        # 3: R0 = R0 - 1
        Call(
            structure_hash="hash_decrement",
            output=Register(0),
            args=[Register(0)],
            task_name="decr",
        ),
        # 4: Goto 0
        Jump(offset=-4),
    ]

    bp = Blueprint(instructions=instrs, register_count=3, input_kwargs={"count": 0})
    vm = VirtualMachine()

    # Loop 3 times: 3, 2, 1
    await vm.execute(bp, SYMBOL_TABLE, initial_kwargs={"count": 3})
    assert log == [3, 2, 1]
~~~~~

#### Acts 3: 更新 `test_vm_map.py`

最后，我们重构 `MapCall` 相关的测试。

~~~~~act
write_file
packages/cascade-vm/tests/unit/test_vm_map.py
~~~~~
~~~~~python
import pytest
import asyncio
from cascade.spec.blueprint import Blueprint, Call, MapCall, Register, Literal
from cascade.vm import VirtualMachine

# --- Helpers ---


def double(x):
    return x * 2


async def async_double(x):
    await asyncio.sleep(0.01)
    return x * 2


def add(a, b):
    return a + b


# --- Symbol Table ---

SYMBOL_TABLE = {
    "hash_double": double,
    "hash_async_double": async_double,
    "hash_add": add,
}

# --- Tests ---


@pytest.mark.asyncio
async def test_vm_map_execution_sync():
    """
    Case 1: Sync MapCall.
    Verify VM iterates over list input and collects results.
    """
    # Instruction: results = map(double, x=[1, 2, 3])
    instr = MapCall(
        structure_hash="hash_double",
        output=Register(0),
        args=[],
        kwargs={"x": Literal([1, 2, 3])},
        task_name="map_double",
    )

    bp = Blueprint(instructions=[instr], register_count=1)
    vm = VirtualMachine()

    results = await vm.execute(bp, SYMBOL_TABLE)
    assert results == [2, 4, 6]


@pytest.mark.asyncio
async def test_vm_map_execution_async():
    """
    Case 2: Async MapCall.
    Verify VM awaits all coroutines.
    """
    instr = MapCall(
        structure_hash="hash_async_double",
        output=Register(0),
        kwargs={"x": Literal([10, 20])},
        task_name="map_async",
    )

    bp = Blueprint(instructions=[instr], register_count=1)
    vm = VirtualMachine()

    results = await vm.execute(bp, SYMBOL_TABLE)
    assert results == [20, 40]


@pytest.mark.asyncio
async def test_vm_map_multiple_iterables():
    """
    Case 3: Map with multiple iterables (zip behavior).
    map(add, a=[1, 2], b=[10, 20]) -> [11, 22]
    """
    instr = MapCall(
        structure_hash="hash_add",
        output=Register(0),
        kwargs={"a": Literal([1, 2]), "b": Literal([10, 20])},
        task_name="map_add",
    )

    bp = Blueprint(instructions=[instr], register_count=1)
    vm = VirtualMachine()

    results = await vm.execute(bp, SYMBOL_TABLE)
    assert results == [11, 22]
~~~~~

### 下一步建议
我们已经完成了对 `cascade-vm` 单元测试的现代化改造。现在，我建议你运行测试套件。

我们预期 `cascade-vm` 相关的测试现在应该全部通过。余下的失败将集中在更高层次的集成测试中，例如 `packages/cascade-engine/tests/integration/test_integration_map_control.py`。这些测试目前仍然试图使用旧的 `GraphExecutionStrategy` 并且没有为新的 VM 管道正确设置 `symbol_table`。

我们的下一个目标将是修复这些更高层次的集成测试，让它们正确地使用新的 `Compiler -> VM` 完整执行流程。
