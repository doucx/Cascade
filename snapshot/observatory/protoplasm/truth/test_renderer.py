import asyncio
import numpy as np
import shutil
import random

# Use the new UniGrid
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes
from observatory.protoplasm.truth.golden_ca import GoldenLife

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

    abs_err = 0

    try:
        for gen in range(MAX_GENERATIONS):
            # A. Get the next "correct" state from the simulator
            theoretical_grid = golden.step()
            
            # B. For this test, assume the "actual" grid from agents is identical
            actual_grid = theoretical_grid.copy()

            # --- Inject a fake error to test colors ---
            # Should turn RED (2.0)
            if 20 <= gen < 40:
                actual_grid[5, 5] = 1 
                abs_err = 1
            
            # Should turn CYAN (3.0)
            if 30 <= gen < 50:
                glider_pos = np.where(theoretical_grid == 1)
                if len(glider_pos[0]) > 0:
                    actual_grid[glider_pos[0][0], glider_pos[1][0]] = 0
                    abs_err = 1

            # C. Encode State
            display_grid = np.zeros(actual_grid.shape, dtype=np.float32)
            display_grid[(actual_grid == 1) & (theoretical_grid == 1)] = 1.0
            display_grid[(actual_grid == 1) & (theoretical_grid == 0)] = 2.0
            display_grid[(actual_grid == 0) & (theoretical_grid == 1)] = 3.0

            # D. Push Frame
            renderer.ingest_full(display_grid)
            renderer.set_extra_info(f"Gen {gen} | Errors: {abs_err}")
            
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