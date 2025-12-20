import asyncio
import time
import math

from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
from observatory.monitors.aggregator import MetricsAggregator

# --- Configuration ---
GRID_WIDTH = 100
GRID_HEIGHT = 100
TOTAL_PIXELS = GRID_WIDTH * GRID_HEIGHT
SIMULATION_DURATION_S = 120.0
WAVE_GROWTH_INTERVAL_S = 5.0  # Every 5 seconds, the wave gets wider
SIMULATION_TICK_S = 0.01  # Run the simulation loop at 100Hz


async def main():
    """
    Main entry point for the wave test.
    """
    print("🚀 Starting Renderer Wave Stress Test...")
    log_filename = f"wave_test_log_{int(time.time())}.jsonl"

    # 1. Setup Logger
    aggregator = MetricsAggregator(log_filename)
    aggregator.open()
    print(f"📝 Logging aggregate metrics to [bold cyan]{log_filename}[/bold cyan]")

    # 2. Setup UI
    grid_view = GridView(
        width=GRID_WIDTH,
        height=GRID_HEIGHT,
        palette_func=Palettes.firefly,
        decay_per_second=8.0,
    )
    status_bar = StatusBar(
        initial_status={
            "Test": "Wave Stress Test",
            "Wave Width": 1,
        }
    )
    app = TerminalApp(grid_view, status_bar, aggregator=aggregator)
    await app.start()

    # 3. Start logger loop
    aggregator_task = asyncio.create_task(aggregator.run())

    # 4. Simulation State
    wave_width = 1
    scan_pos = 0
    last_growth_time = time.time()
    start_time = time.time()

    try:
        while True:
            # --- Simulation Logic ---
            now = time.time()
            elapsed = now - start_time

            if elapsed >= SIMULATION_DURATION_S:
                break

            # Grow the wave over time
            if now - last_growth_time > WAVE_GROWTH_INTERVAL_S:
                wave_width = max(1, min(TOTAL_PIXELS, wave_width * 2))
                last_growth_time = now
                app.update_status("Wave Width", wave_width)

            # --- Generate Updates for this Tick ---
            # This loop simulates the "thundering herd"
            for i in range(wave_width):
                current_pos = (scan_pos + i) % TOTAL_PIXELS
                x = current_pos % GRID_WIDTH
                y = current_pos // GRID_WIDTH
                app.direct_update_grid(x, y, 1.0)
            
            # Move the scanline forward and WRAP AROUND
            move_amount = math.ceil(GRID_WIDTH * 2 * SIMULATION_TICK_S) # Move 2 rows per second
            scan_pos = (scan_pos + move_amount) % TOTAL_PIXELS

            # --- Yield to Renderer ---
            await asyncio.sleep(SIMULATION_TICK_S)

    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\nTest interrupted.")
    finally:
        print("\nCleaning up...")
        app.stop()
        aggregator.close()
        aggregator_task.cancel()
        await asyncio.gather(aggregator_task, return_exceptions=True)
        print("Wave test finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass