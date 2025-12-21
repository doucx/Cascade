import pytest
import cascade as cs
from cascade.graph.compiler import BlueprintBuilder
from cascade.runtime.vm import VirtualMachine
from cascade.runtime.blueprint import TailCall

# --- Define a recursive task using TailCall ---

@cs.task
def recursive_countdown(count: int) -> Any:
    if count > 0:
        return TailCall(kwargs={"count": count - 1})
    return "Done"

@pytest.mark.asyncio
async def test_vm_tco_integration():
    """
    End-to-end test of TCO:
    1. Define a recursive task.
    2. Compile it using BlueprintBuilder.
    3. Execute it using VirtualMachine.
    """
    
    # 1. Define the workflow template
    # We pass an initial value (5), but this mainly sets the structure.
    # The VM will override this with the initial_kwargs we pass to execute().
    target = recursive_countdown(count=0) 

    # 2. Compile
    builder = BlueprintBuilder()
    blueprint = builder.build(target)
    
    # Verify compilation structure
    # Should have 1 input ('count') and 1 output
    assert "count" in blueprint.input_kwargs
    
    # 3. Execute
    vm = VirtualMachine()
    # Start with count=5
    result = await vm.execute(blueprint, initial_kwargs={"count": 5})
    
    assert result == "Done"