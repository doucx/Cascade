import asyncio
import time
import random
import statistics
from typing import List

import cascade as cs

# --- Experiment Configuration ---
NUM_NOISE_TASKS_CPU = 5000
NUM_NOISE_TASKS_IO = 5000
PROBE_INTERVAL_S = 0.05  # 50ms, a common tick rate in simulations
EXPERIMENT_DURATION_S = 10.0

# --- Noise Generators ---

async def cpu_noise_task():
    """A task that burns CPU cycles to stress the scheduler."""
    while True:
        # Perform some meaningless computation
        _ = sum(i*i for i in range(1000))
        # Yield control to the event loop
        await asyncio.sleep(0)

async def io_noise_task():
    """A task that simulates frequent, short IO waits."""
    while True:
        # Simulate waiting for a network packet, DB query, etc.
        await asyncio.sleep(random.uniform(0.01, 0.05))

# --- Time Probe ---

@cs.task
async def time_probe_task(interval: float, duration: float) -> List[float]:
    """
    The core measurement tool.
    Repeatedly calls cs.wait() and records the timing error.
    """
    errors_ms = []
    num_probes = int(duration / interval)
    print(f"TimeProbe: Starting measurement for {num_probes} probes...")
    
    for i in range(num_probes):
        start_time = time.perf_counter()
        
        await cs.wait(interval)
        
        end_time = time.perf_counter()
        actual_delay = end_time - start_time
        error = actual_delay - interval
        errors_ms.append(error * 1000) # Store error in milliseconds
        
        # Print progress without spamming
        if (i + 1) % (num_probes // 10) == 0:
            print(f"TimeProbe: Progress {((i+1)/num_probes)*100:.0f}%...")

    return errors_ms

# --- Main Experiment Orchestrator ---

async def main():
    print("🚀 Starting Jitter Meter Experiment...")
    print(f"   - CPU Noise Tasks: {NUM_NOISE_TASKS_CPU}")
    print(f"   - IO Noise Tasks: {NUM_NOISE_TASKS_IO}")
    print(f"   - Total Noise: {NUM_NOISE_TASKS_CPU + NUM_NOISE_TASKS_IO} coroutines")
    print(f"   - Probe Interval: {PROBE_INTERVAL_S * 1000} ms")
    print(f"   - Duration: {EXPERIMENT_DURATION_S} seconds")
    
    # 1. Start Noise Tasks in the background
    noise_tasks = []
    for _ in range(NUM_NOISE_TASKS_CPU):
        noise_tasks.append(asyncio.create_task(cpu_noise_task()))
    for _ in range(NUM_NOISE_TASKS_IO):
        noise_tasks.append(asyncio.create_task(io_noise_task()))
        
    print("Noise generators started. Allowing system to stabilize...")
    await asyncio.sleep(1)

    # 2. Run the Probe using Cascade's async API
    # We are already in an async context, so we must instantiate the Engine
    # and `await` its run method, not use the synchronous `cs.run()` helper.
    print("Running Cascade probe workflow...")
    probe_workflow = time_probe_task(PROBE_INTERVAL_S, EXPERIMENT_DURATION_S)

    # Instantiate a default, silent engine for the probe
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=cs.MessageBus() # A silent bus for clean test output
    )
    timing_errors = await engine.run(probe_workflow)

    # 3. Stop Noise Tasks
    print("Probe finished. Shutting down noise generators...")
    for task in noise_tasks:
        task.cancel()
    await asyncio.gather(*noise_tasks, return_exceptions=True)

    # 4. Analyze and Report Results
    if not timing_errors:
        print("\n❌ No timing data collected. Experiment failed.")
        return
        
    mean_error = statistics.mean(timing_errors)
    std_dev = statistics.stdev(timing_errors)
    min_error = min(timing_errors)
    max_error = max(timing_errors)
    
    print("\n--- Jitter Analysis Report ---")
    print(f"Target Interval: {PROBE_INTERVAL_S * 1000:.2f} ms")
    print(f"Samples Collected: {len(timing_errors)}")
    print("------------------------------")
    print(f"Mean Error:      {mean_error:+.4f} ms")
    print(f"Std Deviation:   {std_dev:.4f} ms")
    print(f"Min Error (fast):{min_error:+.4f} ms")
    print(f"Max Error (lag): {max_error:+.4f} ms")
    print("------------------------------")
    
    # Interpretation
    print("\nInterpretation:")
    if max_error > (PROBE_INTERVAL_S * 1000 * 0.25):
         print(f"⚠️  WARNING: Maximum lag ({max_error:.2f}ms) is over 25% of the target interval.")
         print(f"   This indicates significant scheduling jitter under load.")
    else:
        print("✅  SUCCESS: Jitter is within acceptable limits for the given load.")
        
    print(f"   The system's 'minimum reliable time slice' is likely in the range of {max_error:.0f}-{max_error*2:.0f} ms.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExperiment interrupted by user.")