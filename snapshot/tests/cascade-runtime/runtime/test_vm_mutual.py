from typing import Any
import pytest
import cascade as cs
from cascade.graph.compiler import BlueprintBuilder
from cascade.runtime.vm import VirtualMachine
from cascade.runtime.blueprint import TailCall

# --- Define Mutual Recursive Tasks ---

@cs.task
def ping(n: int) -> Any:
    if n > 0:
        # Calls 'pong' blueprint
        return TailCall(kwargs={"n": n - 1}, target_blueprint_id="pong")
    return "Ping Done"

@cs.task
def pong(n: int) -> Any:
    if n > 0:
        # Calls 'ping' blueprint
        return TailCall(kwargs={"n": n - 1}, target_blueprint_id="ping")
    return "Pong Done"

@pytest.mark.asyncio
async def test_vm_mutual_recursion():
    """
    Tests A -> B -> A execution flow.
    """
    # 1. Compile both tasks
    builder = BlueprintBuilder()
    
    # Compile Ping (using dummy input to establish structure)
    bp_ping = builder.build(ping(n=0), template=True)
    
    # Compile Pong
    bp_pong = builder.build(pong(n=0), template=True)
    
    # 2. Setup VM
    vm = VirtualMachine()
    vm.register_blueprint("ping", bp_ping)
    vm.register_blueprint("pong", bp_pong)
    
    # 3. Execute Ping(4)
    # Flow: Ping(4) -> Pong(3) -> Ping(2) -> Pong(1) -> Ping(0) -> "Ping Done"
    result = await vm.execute(bp_ping, initial_kwargs={"n": 4})
    
    assert result == "Ping Done"

@pytest.mark.asyncio
async def test_vm_mutual_recursion_pong_ends():
    """
    Tests case where recursion ends in the second function.
    """
    builder = BlueprintBuilder()
    bp_ping = builder.build(ping(n=0), template=True)
    bp_pong = builder.build(pong(n=0), template=True)
    
    vm = VirtualMachine()
    vm.register_blueprint("ping", bp_ping)
    vm.register_blueprint("pong", bp_pong)
    
    # Flow: Ping(3) -> Pong(2) -> Ping(1) -> Pong(0) -> "Pong Done"
    result = await vm.execute(bp_ping, initial_kwargs={"n": 3})
    
    assert result == "Pong Done"
