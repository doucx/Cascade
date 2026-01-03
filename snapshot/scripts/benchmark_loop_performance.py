import asyncio
import time
import inspect
from typing import Dict

# --- Cascade VM Imports ---
from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.ports import PortDef, PortRole
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor

ITERATIONS = 10000

# --- Cascade Benchmark Components ---

async def loop_logic(inputs: Dict[str, Token], node: PhysicsFuncNode) -> Dict[str, Token]:
    """
    The "business logic" for our self-looping node.
    It increments the counter in the token payload.
    NOW AN ASYNC FUNCTION.
    """
    # In a real async function, we might do `await asyncio.sleep(0)`
    # to yield control, but for a pure computation benchmark, this is fine.
    in_token = inputs["loop_in"]
    count = in_token.payload

    if count < ITERATIONS:
        # Continue the loop by emitting a new token
        return {"loop_out": Token(payload=count + 1)}
    else:
        # Terminate the loop by producing no output, starving the graph
        return {}

async def run_cascade_benchmark() -> float:
    """Sets up and runs the self-loop benchmark using the Cascade VM."""
    # 1. Build the physical graph: D_loop -> F_loop -> D_loop
    d_loop = PhysicsDataNode(id="D_loop", name="LoopCounter")
    f_loop = PhysicsFuncNode(
        id="F_loop",
        name="Incrementer",
        input_ports={"loop_in": PortDef("loop_in", PortRole.DATA)},
        output_ports={"loop_out": PortDef("loop_out", PortRole.DATA)},
    )
    graph = BipartiteGraph()
    graph.nodes = {d_loop.id: d_loop, f_loop.id: f_loop}
    graph.channels.append(Channel(d_loop.id, "out", f_loop.id, "loop_in"))
    graph.channels.append(Channel(f_loop.id, "loop_out", d_loop.id, "in"))

    # 2. Setup the VM
    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f_loop.id: loop_logic}
    reactor = Reactor(graph, memory, executor, function_map)

    # MONKEY-PATCH the _fire method to be "smart"
    original_fire = reactor._fire
    async def smart_fire(node: PhysicsFuncNode, input_data: Dict[str, Token]) -> None:
        func = reactor.function_map.get(node.id)
        if not func:
            return
        
        # THE CORE OF THE OPTIMIZATION
        if inspect.iscoroutinefunction(func):
            # If it's async, await it directly on the event loop
            result_tokens = await func(input_data, node)
            # This part is duplicated from Reactor but necessary for the patch
            outbound = reactor._outbound_channels.get(node.id, [])
            for channel in outbound:
                token = result_tokens.get(channel.source_port)
                if token is not None:
                    target_node = reactor.graph.nodes[channel.target_node_id]
                    reactor.memory.put(target_node, token)
        else:
            # Otherwise, use the original, safe method
            await original_fire(node, input_data)

    reactor._fire = smart_fire


    # 3. Prime the system with the initial state
    reactor.prime()
    memory.put(d_loop, Token(payload=0))

    # 4. Run the benchmark
    print("Starting Cascade VM benchmark (with native async optimization)...")
    start_time = time.monotonic()

    # The reactor loop continues as long as there are state changes
    while (await reactor.step()) > 0:
        pass

    end_time = time.monotonic()
    print("Cascade VM benchmark finished.")
    return end_time - start_time

# --- Native Python Benchmark ---

def run_python_benchmark() -> float:
    """Runs a simple while loop for comparison."""
    print("Starting native Python benchmark...")
    start_time = time.monotonic()

    count = 0
    while count < ITERATIONS:
        count += 1

    end_time = time.monotonic()
    print("Native Python benchmark finished.")
    return end_time - start_time

# --- Main Execution ---

async def main():
    """Main function to run benchmarks and print results."""
    print(f"--- Loop Performance Benchmark ({ITERATIONS} iterations) ---")
    
    python_duration = run_python_benchmark()
    cascade_duration = await run_cascade_benchmark()
    
    python_ips = ITERATIONS / python_duration if python_duration > 0 else float('inf')
    cascade_ips = ITERATIONS / cascade_duration if cascade_duration > 0 else float('inf')
    
    overhead = (cascade_duration / python_duration) if python_duration > 0 else 0
    
    print("\n--- Results ---")
    print(f"| {'Metric':<25} | {'Native Python':<20} | {'Cascade VM':<20} |")
    print(f"| {'-'*25} | {'-'*20} | {'-'*20} |")
    print(f"| {'Total Time (s)':<25} | {python_duration:<20.6f} | {cascade_duration:<20.6f} |")
    print(f"| {'Iterations/Second':<25} | {python_ips:<20,.2f} | {cascade_ips:<20,.2f} |")
    print("-" * 75)
    print(f"Cascade VM overhead is approximately {overhead:.2f}x that of a native loop.")

if __name__ == "__main__":
    asyncio.run(main())