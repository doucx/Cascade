import asyncio
import numpy as np
import shutil
import random

# Use the new UniGrid and the shared UI module
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes
from observatory.protoplasm.truth.golden_ca import GoldenLife
from observatory.protoplasm.truth import ui

# --- Test Configuration ---
GRID_WIDTH = 40
GRID_HEIGHT = 20
MAX_GENERATIONS = 200
FRAME_DELAY = 0.05  # seconds

def get_glider_seed(width: int, height: int) -> np.ndarray:
    """Creates a simple Glider pattern on the grid."""
    grid = np.zeros((height, width), dtype=np.int8)
    #   .X.
    #   ..X
    #   XXX
    grid[1, 2] = 1
    grid[2, 3] = 1
    grid[3, 1:4] = 1
    return grid

async def main():
    """
    Main loop to test the UniGridRenderer in "Truth Mode".
    """
    print("🚀 Starting UniGrid Truth Mode Test...")
    
    # 1. Setup the "perfect" simulator
    golden = GoldenLife(GRID_WIDTH, GRID_HEIGHT)
    golden.seed(get_glider_seed(GRID_WIDTH, GRID_HEIGHT))

    # 2. Setup the renderer with Truth Palette
    renderer = UniGridRenderer(
        width=GRID_WIDTH, 
        height=GRID_HEIGHT, 
        palette_func=Palettes.truth,
        decay_rate=0.0
    )
    renderer_task = asyncio.create_task(renderer.start())

    errors = {"abs": 0, "rel": 0}

    try:
        for gen in range(MAX_GENERATIONS):
            # A. Get theoretical state
            theoretical_grid = golden.step()
            
            # B. Create actual state with injected errors
            actual_grid = theoretical_grid.copy()
            errors["abs"] = 0 # Reset per frame for this test
            
            if 20 <= gen < 40:
                # Create a false positive (Red)
                if theoretical_grid[5, 5] == 0:
                    actual_grid[5, 5] = 1 
                    errors["abs"] += 1
            
            if 30 <= gen < 50:
                # Create a false negative (Cyan)
                glider_pos = np.where(theoretical_grid == 1)
                if len(glider_pos[0]) > 0:
                    y, x = glider_pos[0][0], glider_pos[1][0]
                    if actual_grid[y, x] == 1:
                        actual_grid[y, x] = 0
                        errors["abs"] += 1

            # C. Use shared UI logic to create display grid and status line
            display_grid = ui.create_display_grid(actual_grid, theoretical_grid)
            status_line = ui.format_status_line(
                gen, 
                GRID_WIDTH * GRID_HEIGHT, # Assume full buffer for test
                GRID_WIDTH * GRID_HEIGHT, 
                errors
            )

            # D. Push to renderer
            renderer.ingest_full(display_grid)
            renderer.set_extra_info(status_line)
            
            # E. Wait
            await asyncio.sleep(FRAME_DELAY)

    finally:
        renderer.stop()
        if not renderer_task.done():
            renderer_task.cancel()
            await renderer_task
        print("\n✅ Renderer Test Finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")