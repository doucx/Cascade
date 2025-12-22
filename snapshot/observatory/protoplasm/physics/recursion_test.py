import asyncio
import time
import os
import re

import cascade as cs
from cascade.runtime.subscribers import HumanReadableLogSubscriber
from cascade.common.messaging import bus as global_bus
from cascade.common.renderers import CliRenderer

# --- Memory Monitoring Utils ---


def get_memory_mb():
    """
    Tries to get memory usage via psutil, then /proc/self/status (Linux),
    then returns 0.0 if all fail.
    """
    # 1. Try psutil
    try:
        import psutil

        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        pass

    # 2. Try reading /proc/self/status (Linux specific)
    try:
        with open("/proc/self/status", "r") as f:
            content = f.read()
            # Look for "VmRSS:    1234 kB"
            match = re.search(r"VmRSS:\s+(\d+)\s+kB", content)
            if match:
                return float(match.group(1)) / 1024.0
    except FileNotFoundError:
        pass

    print("⚠️  Warning: Cannot determine memory usage (psutil missing & not on Linux?)")
    return 0.0


# --- Configuration ---
NUM_AGENTS = 1000  # Reduced from 10,000 to ensure responsiveness
NUM_GENERATIONS = 1000  # Total generations to simulate
REPORT_INTERVAL = 2  # Monitor interval in seconds

# --- The Recursive Agent ---


def controlled_agent(agent_id: int, gen: int, limit: int):
    """
    A recursive agent that stops after `limit` generations.
    """

    # We use a task for the step to involve the Engine's scheduling machinery
    @cs.task(name="step")
    def step(v):
        return v + 1

    next_v = step(gen)

    # We use a task for the check/recursion to test TCO
    @cs.task(name="loop")
    def loop(v):
        if v >= limit:
            return v
        return controlled_agent(agent_id, v, limit)

    return loop(next_v)


# --- Experiment Orchestrator ---


async def run_recursion_experiment():
    print("🚀 Starting Recursion & Memory Experiment...")
    print(f"   - Agents: {NUM_AGENTS}")
    print(f"   - Target Generations: {NUM_GENERATIONS}")

    initial_mem = get_memory_mb()
    print(f"Initial Memory Usage: {initial_mem:.2f} MB")

    # 1. Setup Engine with Visibility
    # We attach a subscriber to the bus so we can see if things go wrong.
    # But we set min_level="WARNING" to avoid flooding stdout with 1000 agents' info.

    # Configure global renderer for the bus (used by subscribers)
    global_bus.set_renderer(CliRenderer(store=global_bus.store, min_level="WARNING"))

    engine_bus = cs.MessageBus()
    # Attach subscriber to the engine's bus
    HumanReadableLogSubscriber(engine_bus)

    engine = cs.Engine(
        solver=cs.NativeSolver(), executor=cs.LocalExecutor(), bus=engine_bus
    )

    print(f"Starting {NUM_AGENTS} agents...")
    start_time = time.perf_counter()

    # 2. Launch Agents
    # We stagger the start slightly to avoid thundering herd on graph build
    tasks = []
    for i in range(NUM_AGENTS):
        tasks.append(engine.run(controlled_agent(i, 0, NUM_GENERATIONS)))
        if i % 100 == 0:
            await asyncio.sleep(0)  # Yield to event loop

    print("All agents scheduled. Monitoring...")

    # 3. Monitor memory in a background loop
    async def monitor_mem():
        max_mem = initial_mem
        while True:
            await asyncio.sleep(REPORT_INTERVAL)
            mem = get_memory_mb()
            max_mem = max(max_mem, mem)
            print(
                f"   [Monitor] Memory: {mem:.2f} MB (Delta: {mem - initial_mem:+.2f} MB) | Max Delta: {max_mem - initial_mem:+.2f} MB"
            )

    monitor_task = asyncio.create_task(monitor_mem())

    try:
        # Wait for all agents to finish
        await asyncio.gather(*tasks)
        print(
            f"\n✅ Successfully reached {NUM_GENERATIONS} generations for all {NUM_AGENTS} agents."
        )
    except Exception as e:
        print(f"\n❌ Experiment failed with error: {e}")
        raise
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

    # Check for leaks
    # Allow some overhead for python objects, but it shouldn't be massive
    if (final_mem - initial_mem) > 50:
        print("⚠️  POTENTIAL LEAK: Memory increased significantly (>50MB).")
    else:
        print("✅  STABLE: Memory usage remained within reasonable bounds.")


if __name__ == "__main__":
    asyncio.run(run_recursion_experiment())
