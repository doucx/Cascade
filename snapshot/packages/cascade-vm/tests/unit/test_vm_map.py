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