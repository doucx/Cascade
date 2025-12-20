import asyncio
import random
import time

from observatory.visualization.raw_app import RawTerminalApp as TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes

# --- Configuration ---
NUM_SOURCES = 10000
GRID_WIDTH = 100
GRID_HEIGHT = 100
SIMULATION_DURATION_S = 60.0


async def source_coroutine(app: TerminalApp, source_id: int):
    """
    A simple async task that randomly generates updates for the grid.
    This simulates one agent's output without any of the complex logic.
    """
    # Stagger start times slightly to avoid initial thundering herd
    await asyncio.sleep(random.uniform(0, 0.5))

    while True:
        # Simulate work / thinking time
        await asyncio.sleep(random.uniform(0.5, 5.0))

        # Generate a "flash"
        x = random.randint(0, GRID_WIDTH - 1)
        y = random.randint(0, GRID_HEIGHT - 1)

        # Call the renderer directly, mimicking an agent's flash callback
        # Use batch API for RawTerminalApp
        await app.direct_update_grid_batch([(x, y, 1.0)])


async def main():
    """
    The main entry point for the stress test.
    """
    print("🚀 Starting Isolated Renderer Stress Test...")
    print(f"   - Update Sources: {NUM_SOURCES}")
    print(f"   - Grid Size: {GRID_WIDTH}x{GRID_HEIGHT}")

    # 1. Setup UI
    grid_view = GridView(
        width=GRID_WIDTH,
        height=GRID_HEIGHT,
        palette_func=Palettes.firefly,
        decay_per_second=4.0,  # Use decay to see flashes fade
    )
    status_bar = StatusBar(
        initial_status={
            "Test": "Renderer Stress Test",
            "Sources": NUM_SOURCES,
        }
    )
    app = TerminalApp(grid_view, status_bar)

    # 2. Create source tasks
    tasks = [asyncio.create_task(source_coroutine(app, i)) for i in range(NUM_SOURCES)]

    print("Starting renderer and source coroutines...")
    await app.start()

    # 3. Run for a fixed duration
    try:
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed >= SIMULATION_DURATION_S:
                break
            app.update_status("Elapsed", f"{elapsed:.1f}s / {SIMULATION_DURATION_S}s")
            await asyncio.sleep(1)

    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\nTest interrupted by user.")
    finally:
        print("\nCleaning up...")
        # 4. Cleanly shut down
        app.stop()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        print("Stress test finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
