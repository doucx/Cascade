import pytest
import asyncio
from typing import Dict, Any, Callable

# SDK constructs
from cascade.spec.task import task
from cascade.spec.environment import EnvironmentDef, ResourceDef

# Compiler
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder

# VM
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor

# Standard Library
from cascade.std.triad import standard_bleacher, standard_stainer

# --- Test Workflow Definition ---

@task
def setup_task():
    print("Running setup...")
    return "setup_complete"

@task
def should_run_task():
    print("Deciding to run...")
    return True

@task
def main_task(x: int):
    print(f"Running main task with {x}...")
    return x * 2

@task
def final_task(res: int, setup_status: str):
    print(f"Final task processing {res} with status {setup_status}")
    return f"Result: {res}, Status: {setup_status}"

# --- Test Case ---

@pytest.mark.asyncio
async def test_e2e_vm_run_with_all_features():
    """
    Simulates the future VMExecutionStrategy to test the full Compiler -> VM pipeline.
    """
    # 1. Define the complex workflow using the SDK
    setup_result = setup_task()
    condition_result = should_run_task()
    
    main_result = main_task(10).with_constraints(gpu=1).run_if(condition_result).after(setup_result)
    
    final_result_lr = final_task(main_result, setup_result)

    # 2. Manually compile the workflow
    # Frontend
    generator = IRGenerator()
    graph_ir = generator.generate(final_result_lr)
    
    # Backend
    environment = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1)])
    builder = Builder()
    physical_graph = builder.build(graph_ir, environment)

    # 3. Manually set up the VM
    memory = VolatileMemory()
    executor = PhysicsExecutor()
    
    # Create the function map: map physical node IDs to actual callables
    from cascade.spec.physics import Token
    
    # Helper to adapt user functions to Physics Protocol
    def create_worker_adapter(user_func):
        async def adapter(inputs: Dict[str, Token], node):
            # Unpack kwargs from the worker_input token
            kwargs = inputs["worker_input"].payload
            print(f"DEBUG: Executing {user_func.__name__} with {kwargs}")
            
            # Call user function
            if asyncio.iscoroutinefunction(user_func):
                result = await user_func(**kwargs)
            else:
                result = user_func(**kwargs)
            
            print(f"DEBUG: Finished {user_func.__name__} -> {result}")
            return {"worker_result": Token(payload=result)}
        return adapter

    user_tasks = {
        "setup_task": setup_task.func,
        "should_run_task": should_run_task.func,
        "main_task": main_task.func,
        "final_task": final_task.func,
    }
    
    function_map: Dict[str, Callable] = {}
    for node_ir in graph_ir.nodes:
        if node_ir.name in user_tasks:
            # Map the worker node to the ADAPTED user function
            worker_id = f"{node_ir.id}.worker"
            user_func = user_tasks[node_ir.name]
            function_map[worker_id] = create_worker_adapter(user_func)

    for node_id in physical_graph.nodes:
        if node_id.endswith(".bleach"):
            function_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            function_map[node_id] = standard_stainer
        # We don't need to map the observer for this test to keep it simple

    reactor = Reactor(physical_graph, memory, executor, function_map)
    reactor.prime()

    # 4. Set up a sink to capture the final result
    final_result = None
    result_event = asyncio.Event()

    async def result_sink(token):
        nonlocal final_result
        final_result = token.payload
        result_event.set()

    final_node_id = next(n.id for n in graph_ir.nodes if n.name == "final_task")
    final_stainer_id = f"{final_node_id}.stain"
    reactor.add_sink(final_stainer_id, "output", result_sink)

    # 5. Run the VM until idle
    step = 0
    max_steps = 20  # Safety break
    while step < max_steps:
        fired_count = await reactor.step()
        
        # Wait for any scheduled tasks to complete
        while reactor.active_task_count > 0:
            await asyncio.sleep(0.001)

        if fired_count == 0 and reactor.active_task_count == 0:
            print(f"VM is idle after {step + 1} steps.")
            break
        
        step += 1
    else:
        pytest.fail(f"VM did not become idle within {max_steps} steps.")


    # 6. Assertions
    # Wait for the result to be captured by the sink
    await asyncio.wait_for(result_event.wait(), timeout=1.0)
    
    # Assert the final computed value
    assert final_result == "Result: 20, Status: setup_complete"
    
    # Assert the resource state
    gpu_resource_id = "canonical.resource.gpu"
    assert memory.get_count(gpu_resource_id) == 1, "GPU resource was not released"