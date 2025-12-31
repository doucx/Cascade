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