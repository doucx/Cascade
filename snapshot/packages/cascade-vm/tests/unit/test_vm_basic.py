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
