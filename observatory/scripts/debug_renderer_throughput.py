"""
Debug Script 1: Renderer Throughput Test

Purpose:
  Isolates the RawTerminalApp renderer to measure its maximum update throughput
  without the overhead of the Cascade engine or agent logic. This script
  simulates a configurable number of "sources" that generate grid updates
  at a high frequency.

How to Run:
  python -m observatory.scripts.debug_renderer_throughput

Expected Output:
  A terminal visualization running smoothly. The FPS and flush duration
  metrics in the log file will tell us the renderer's baseline performance.
  If FPS here is high (>30) and flush duration is low (<20ms), the renderer
  itself is not the bottleneck.
"""

import asyncio
import random
import time

from observatory.visualization.raw_app import RawTerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
from observatory.monitors.aggregator import MetricsAggregator

# --- Configuration ---
NUM_SOURCES = 5000  # Number of simulated concurrent update sources
UPDATES_PER_SOURCE_PER_S = 2  # Avg updates per source per second
GRID_WIDTH = 50
GRID_HEIGHT = 50
SIMULATION_DURATION_S = 30.0


async def source_coroutine(app: RawTerminalApp):
    """A simple async task that randomly generates updates for the grid."""
    while True:
        # Generate a "flash"
        x = random.randint(0, GRID_WIDTH - 1)
        y = random.randint(0, GRID_HEIGHT - 1)
        await app.direct_update_grid_batch([(x, y, 1.0)])
        await asyncio.sleep(1.0 / UPDATES_PER_SOURCE_PER_S)


async def main():
    total_updates_per_s = NUM_SOURCES * UPDATES_PER_SOURCE_PER_S
    print("🚀 Starting Renderer Throughput Test...")
    print(f"   - Grid Size: {GRID_WIDTH}x{GRID_HEIGHT}")
    print(f"   - Sources: {NUM_SOURCES}")
    print(f"   - Target Rate: {total_updates_per_s:.0f} updates/sec")
    log_filename = f"renderer_throughput_log_{int(time.time())}.jsonl"

    aggregator = MetricsAggregator(log_filename)
    aggregator.open()
    print(f"📝 Logging metrics to [bold cyan]{log_filename}[/bold cyan]")

    grid_view = GridView(
        width=GRID_WIDTH, height=GRID_HEIGHT, palette_func=Palettes.firefly
    )
    status_bar = StatusBar(
        initial_status={"Test": "Renderer Throughput", "Sources": NUM_SOURCES}
    )
    app = RawTerminalApp(grid_view, status_bar, aggregator=aggregator)
    aggregator_task = asyncio.create_task(aggregator.run())
    await app.start()

    tasks = [asyncio.create_task(source_coroutine(app)) for _ in range(NUM_SOURCES)]

    try:
        await asyncio.sleep(SIMULATION_DURATION_S)
    finally:
        print("\nCleaning up...")
        app.stop()
        aggregator.close()
        aggregator_task.cancel()
        for task in tasks:
            task.cancel()
        await asyncio.gather(aggregator_task, *tasks, return_exceptions=True)
        print("Test finished.")


if __name__ == "__main__":
    asyncio.run(main())
