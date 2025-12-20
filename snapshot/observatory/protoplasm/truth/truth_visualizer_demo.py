import asyncio
import numpy as np
from asyncio import Queue

from observatory.visualization import VisualizerApp
from observatory.visualization.palette import Palettes
from observatory.protoplasm.truth.golden_ca import GoldenLife
from observatory.protoplasm.truth import ui

# --- Demo Configuration ---
GRID_WIDTH = 50
GRID_HEIGHT = 25
MAX_GENERATIONS = 200
FRAME_DELAY = 0.05  # seconds

def get_glider_seed(width: int, height: int) -> np.ndarray:
    """Creates a simple Glider pattern on the grid."""
    grid = np.zeros((height, width), dtype=np.int8)
    grid[1, 2] = 1
    grid[2, 3] = 1
    grid[3, 1:4] = 1
    return grid

async def simulation_loop(grid_queue: Queue, status_queue: Queue):
    """The logic loop that produces data for the TUI."""
    golden = GoldenLife(GRID_WIDTH, GRID_HEIGHT)
    golden.seed(get_glider_seed(GRID_WIDTH, GRID_HEIGHT))

    errors = {"abs": 0, "rel": 0}

    for gen in range(MAX_GENERATIONS):
        theoretical_grid = golden.step()
        actual_grid = theoretical_grid.copy()
        errors["abs"] = 0

        if 20 <= gen < 40:
            if theoretical_grid[5, 5] == 0:
                actual_grid[5, 5] = 1
                errors["abs"] += 1
        
        if 30 <= gen < 50:
            glider_pos = np.where(theoretical_grid == 1)
            if len(glider_pos[0]) > 0:
                y, x = glider_pos[0][0], glider_pos[1][0]
                if actual_grid[y, x] == 1:
                    actual_grid[y, x] = 0
                    errors["abs"] += 1

        display_grid = ui.create_display_grid(actual_grid, theoretical_grid)
        status_line = ui.format_status_line(
            gen, GRID_WIDTH * GRID_HEIGHT, GRID_WIDTH * GRID_HEIGHT, errors
        )

        grid_queue.put_nowait(display_grid)
        status_queue.put_nowait(status_line)
        
        await asyncio.sleep(FRAME_DELAY)

async def main():
    """Sets up the TUI and the simulation logic to run concurrently."""
    grid_queue = Queue()
    status_queue = Queue()
    
    app = VisualizerApp(
        width=GRID_WIDTH,
        height=GRID_HEIGHT,
        palette_func=Palettes.truth,
        data_queue=grid_queue,
        status_queue=status_queue,
    )

    # Run the simulation loop and the UI app concurrently
    sim_task = asyncio.create_task(simulation_loop(grid_queue, status_queue))
    
    # app.run_async() is the non-blocking way to run a Textual app
    await app.run_async()

    # Cleanup
    if not sim_task.done():
        sim_task.cancel()
    
    print("\n✅ Visualizer Demo Finished.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDemo interrupted by user.")