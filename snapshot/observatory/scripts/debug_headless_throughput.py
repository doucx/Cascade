"""
Debug Script 2: Headless Throughput Test

Purpose:
  Isolates the core agent simulation logic to measure its maximum throughput
  without the overhead of rendering. This script runs the full firefly
  simulation but does not create or update any UI components.

How to Run:
  python -m observatory.scripts.debug_headless_throughput

Expected Output:
  A stream of text to the console reporting the number of flashes per second.
  This number gives us a baseline for how fast the simulation *can* run. If this
  number is very high (e.g., >20,000 flashes/sec), it means the agent logic
  itself is fast, and the bottleneck likely appears when coupling it with the UI.
"""
import asyncio
import random
import time
from collections import deque
from typing import List

import cascade as cs
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.networking.direct_channel import DirectChannel

# --- Configuration ---
NUM_AGENTS = 2500
PERIOD = 5.0
NUDGE = 0.2
DURATION_SECONDS = 30.0
GRID_SIDE = int(NUM_AGENTS**0.5)


def get_neighbors(index: int, width: int, height: int) -> List[int]:
    x, y = index % width, index // width
    neighbors = []
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue
            nx, ny = (x + dx) % width, (y + dy) % height
            neighbors.append(ny * width + nx)
    return neighbors


async def run_headless_experiment():
    print("🚀 Starting Headless Throughput Test...")
    print(f"   - Agents: {NUM_AGENTS}")

    # --- Flash Counter ---
    flash_count = 0
    flash_times = deque()

    class HeadlessConnector:
        async def publish(self, topic, payload, **kwargs):
            nonlocal flash_count
            flash_count += 1

        async def connect(self): pass
        async def disconnect(self): pass
        async def subscribe(self, topic, callback):
            class DummySub:
                async def unsubscribe(self): pass
            return DummySub()

    connector = HeadlessConnector()

    channels = [DirectChannel(f"agent_{i}") for i in range(NUM_AGENTS)]
    engine = cs.Engine(cs.NativeSolver(), cs.LocalExecutor(), cs.MessageBus())

    @resource(name="connector")
    def connector_provider():
        yield connector
    engine.register(connector_provider)

    agent_tasks = []
    for i in range(NUM_AGENTS):
        initial_phase = random.uniform(0, PERIOD)
        neighbor_ids = get_neighbors(i, GRID_SIDE, GRID_SIDE)
        my_neighbors = [channels[nid] for nid in neighbor_ids]
        my_channel = channels[i]

        workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=PERIOD,
            nudge=NUDGE,
            neighbors=my_neighbors,
            my_channel=my_channel,
            connector=cs.inject("connector"),
            refractory_period=PERIOD * 0.2,
        )
        agent_tasks.append(engine.run(workflow))

    all_tasks = asyncio.gather(*agent_tasks)
    start_time = time.time()
    last_report_time = start_time

    try:
        while time.time() - start_time < DURATION_SECONDS:
            await asyncio.sleep(1.0)
            now = time.time()
            interval = now - last_report_time
            rate = (flash_count - (flash_times[0] if flash_times else 0)) / interval
            
            # Simple reporting
            current_rate = (flash_count - getattr(run_headless_experiment, 'last_flash_count', 0)) / interval
            print(f"   - Flashes/sec: {current_rate:,.0f} (Total: {flash_count:,})")
            
            run_headless_experiment.last_flash_count = flash_count
            last_report_time = now

    finally:
        print("\nCleaning up...")
        all_tasks.cancel()
        await asyncio.gather(all_tasks, return_exceptions=True)
        print("Test finished.")

# Add a stateful attribute for rate calculation
run_headless_experiment.last_flash_count = 0

if __name__ == "__main__":
    asyncio.run(run_headless_experiment())