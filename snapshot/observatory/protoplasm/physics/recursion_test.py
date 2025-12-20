import asyncio
import time
import os
import gc
from typing import Optional

import cascade as cs

# Use psutil if available, otherwise fallback to a simpler method
try:
    import psutil
    def get_memory_mb():
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
except ImportError:
    def get_memory_mb():
        return 0.0 # Cannot measure without psutil

# --- Configuration ---
NUM_AGENTS = 10000
NUM_GENERATIONS = 1000  # Total generations to simulate
REPORT_INTERVAL = 100   # Report stats every N generations

# --- The Recursive Agent ---

def immortal_agent(agent_id: int, gen: int):
    """
    A simple recursive agent that just counts its generations.
    This tests the Engine's ability to handle infinite recursion (TCO).
    """
    @cs.task(name=f"step_{agent_id}")
    def step(current_gen: int):
        # Perform a tiny bit of work
        return current_gen + 1

    next_gen_val = step(gen)

    @cs.task(name=f"loop_{agent_id}")
    def loop(next_val: int):
        # Tail call back to itself
        return immortal_agent(agent_id, next_val)

    return loop(next_gen_val)

# --- Experiment Orchestrator ---

async def run_recursion_experiment():
    print(f"🚀 Starting Recursion & Memory Experiment...")
    print(f"   - Agents: {NUM_AGENTS}")
    print(f"   - Target Generations: {NUM_GENERATIONS}")
    
    initial_mem = get_memory_mb()
    print(f"Initial Memory Usage: {initial_mem:.2f} MB")

    # 1. Create 10,000 Agent Tasks
    agent_tasks = []
    # We use a shared engine to stress the internal graph-building and cleanup logic
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=cs.MessageBus()
    )

    print(f"Starting {NUM_AGENTS} agents...")
    
    # We create all workflows but we need a way to stop them after NUM_GENERATIONS.
    # We'll modify the agent to stop at a limit for this test.
    
    def controlled_agent(agent_id: int, gen: int, limit: int):
        @cs.task
        def step(v): return v + 1
        
        next_v = step(gen)
        
        @cs.task
        def check(v):
            if v >= limit:
                return v
            return controlled_agent(agent_id, v, limit)
            
        return check(next_v)

    start_time = time.perf_counter()
    
    # Run agents concurrently
    tasks = [engine.run(controlled_agent(i, 0, NUM_GENERATIONS)) for i in range(NUM_AGENTS)]
    
    # Monitor memory in a background loop
    async def monitor_mem():
        while True:
            await asyncio.sleep(2)
            mem = get_memory_mb()
            print(f"   [Monitor] Memory: {mem:.2f} MB (Delta: {mem - initial_mem:+.2f} MB)")
            # Trigger GC manually to see if it clears the "lazy" junk
            # gc.collect()

    monitor_task = asyncio.create_task(monitor_mem())

    try:
        results = await asyncio.gather(*tasks)
        print(f"\n✅ Successfully reached {NUM_GENERATIONS} generations for all {NUM_AGENTS} agents.")
    finally:
        monitor_task.cancel()

    end_time = time.perf_counter()
    final_mem = get_memory_mb()
    
    print("\n--- Recursion Stability Report ---")
    print(f"Total Time:      {end_time - start_time:.2f} s")
    print(f"Total Recursions: {NUM_AGENTS * NUM_GENERATIONS:,.0f}")
    print(f"Initial Memory:   {initial_mem:.2f} MB")
    print(f"Final Memory:     {final_mem:.2f} MB")
    print(f"Net Leak:         {final_mem - initial_mem:+.2f} MB")
    print("----------------------------------")
    
    if (final_mem - initial_mem) > 100: # Arbitrary threshold for 10k agents
        print("⚠️  POTENTIAL LEAK: Memory increased significantly.")
        print("   Check if Engine._execute_graph is holding onto old LazyResults.")
    else:
        print("✅  STABLE: Memory usage remained within reasonable bounds.")

if __name__ == "__main__":
    asyncio.run(run_recursion_experiment())