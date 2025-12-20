import asyncio
import numpy as np
import shutil
import random

from observatory.protoplasm.truth.renderer import TruthRenderer
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
    Main loop to test the TruthRenderer in isolation.
    """
    print("🚀 Starting Isolated Renderer Test...")
    
    # 1. Setup the "perfect" simulator
    golden = GoldenLife(GRID_WIDTH, GRID_HEIGHT)
    golden.seed(get_glider_seed(GRID_WIDTH, GRID_HEIGHT))

    # 2. Setup the renderer
    renderer = TruthRenderer(GRID_WIDTH, GRID_HEIGHT)
    renderer.start()

    try:
        for gen in range(MAX_GENERATIONS):
            # A. Get the next "correct" state from the simulator
            theoretical_grid = golden.step()
            
            # B. For this test, assume the "actual" grid from agents is identical
            actual_grid = theoretical_grid.copy()

            # --- Inject a fake error to test colors ---
            stats = {"abs": 0, "rel": 0}
            if 20 <= gen < 25:
                # Add a "ghost" cell (False Positive -> Red 'X')
                actual_grid[5, 5] = 1 
                stats["abs"] +=1
            if 30 <= gen < 35:
                # Remove a real cell (False Negative -> Cyan 'O')
                glider_pos = np.where(theoretical_grid == 1)
                if len(glider_pos[0]) > 0:
                    actual_grid[glider_pos[0][0], glider_pos[1][0]] = 0
                    stats["abs"] +=1

            # C. Update the renderer with both grids
            renderer.update_frame(gen, actual_grid, theoretical_grid, stats)
            
            # D. Wait to make it viewable
            await asyncio.sleep(FRAME_DELAY)

    finally:
        renderer.stop()
        print("\n✅ Renderer Test Finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")