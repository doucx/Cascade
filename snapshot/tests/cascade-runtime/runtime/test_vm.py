import pytest
from unittest.mock import MagicMock
from cascade.runtime.blueprint import Blueprint, Call, Literal, Register
from cascade.runtime.vm import VirtualMachine, Frame

@pytest.mark.asyncio
async def test_vm_executes_single_call():
    """
    Test execution of a simple blueprint: R0 = func(a=1)
    """
    # 1. Define Blueprint manually
    mock_func = MagicMock(return_value=42)
    
    # Instruction: R0 = mock_func(val=10)
    instr = Call(
        func=mock_func,
        output=Register(0),
        args=[],
        kwargs={"val": Literal(10)}
    )
    blueprint = Blueprint(instructions=[instr], register_count=1)

    # 2. Execute
    vm = VirtualMachine()
    result = await vm.execute(blueprint)

    # 3. Verify
    assert result == 42
    mock_func.assert_called_once_with(val=10)

@pytest.mark.asyncio
async def test_vm_handles_data_dependency():
    """
    Test R0 = func1(1); R1 = func2(R0)
    """
    func1 = MagicMock(return_value=100)
    func2 = MagicMock(return_value=200)

    # I1: R0 = func1(1)
    i1 = Call(
        func=func1,
        output=Register(0),
        args=[Literal(1)],
        kwargs={}
    )
    # I2: R1 = func2(R0)
    i2 = Call(
        func=func2,
        output=Register(1),
        args=[Register(0)],
        kwargs={}
    )
    
    blueprint = Blueprint(instructions=[i1, i2], register_count=2)

    vm = VirtualMachine()
    result = await vm.execute(blueprint)

    assert result == 200
    func1.assert_called_once_with(1)
    func2.assert_called_once_with(100) # Should receive result of func1

def test_vm_async_execution():
    """
    Test handling of async functions.
    """
    import asyncio
    
    async def async_add(x):
        return x + 1

    blueprint = Blueprint(
        instructions=[
            Call(
                func=async_add,
                output=Register(0),
                args=[],
                kwargs={"x": Literal(5)}
            )
        ],
        register_count=1
    )

    vm = VirtualMachine()
    # execute is sync wrapper for now? Or should it be async?
    # Engine.run is async. VM.execute should likely be async too.
    # We'll make VM.execute async.
    
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(vm.execute(blueprint))
    assert result == 6