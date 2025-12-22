import pytest
from typing import Any
from cascade.runtime.vm import VirtualMachine
from cascade.spec.blueprint import Blueprint, Call, Register, TailCall

# --- Mock User Function ---


def recursive_countdown(count: int) -> Any:
    """
    A simple recursive function.
    If count > 0, returns TailCall(count - 1).
    If count == 0, returns "Done".
    """
    if count > 0:
        return TailCall(kwargs={"count": count - 1})
    return "Done"


# --- Tests ---


@pytest.mark.asyncio
async def test_vm_handles_simple_recursion():
    """
    Verifies that the VM can execute a recursive loop using TailCall
    without crashing or returning early.
    """
    # 1. Manually construct a Blueprint for 'recursive_countdown'
    # It has 1 input: 'count', mapped to Register(0)
    # Instruction: res = recursive_countdown(count) -> Register(1)
    # The result of the instruction is the implicit return of the block.

    # Registers:
    # R0: input 'count'
    # R1: output result

    instr = Call(
        func=recursive_countdown, output=Register(1), kwargs={"count": Register(0)}
    )

    blueprint = Blueprint(
        instructions=[instr],
        register_count=2,
        input_kwargs={"count": 0},  # Map 'count' arg to R0
    )

    vm = VirtualMachine()

    # 2. Run with initial count = 5
    # Expectation:
    # It calls recursive_countdown(5) -> returns TailCall(4)
    # VM sees TailCall -> updates R0=4 -> re-runs
    # ...
    # Calls recursive_countdown(0) -> returns "Done"
    # VM sees "Done" -> returns "Done"

    result = await vm.execute(blueprint, initial_kwargs={"count": 5})

    assert result == "Done"


@pytest.mark.asyncio
async def test_vm_propagates_exceptions():
    """Ensure exceptions break the loop correctly."""

    def failing_task(x):
        raise ValueError("Boom")

    blueprint = Blueprint(
        instructions=[Call(func=failing_task, output=Register(1), args=[Register(0)])],
        register_count=2,
        input_args=[0],
    )

    vm = VirtualMachine()
    with pytest.raises(ValueError, match="Boom"):
        await vm.execute(blueprint, initial_args=[1])
