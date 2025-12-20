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
    Main loop to test the UniGridRenderer in isolation with Truth palette.
    """
    print("🚀 Starting Isolated Renderer Test (UniGrid)...")
    
    # 1. Setup simulator
    golden = GoldenLife(GRID_WIDTH, GRID_HEIGHT)
    golden.seed(get_glider_seed(GRID_WIDTH, GRID_HEIGHT))

    # 2. Setup UniGrid with Truth palette
    renderer = UniGridRenderer(
        width=GRID_WIDTH, 
        height=GRID_HEIGHT, 
        palette_func=Palettes.truth,
        decay_rate=0.0
    )
    
    # We must run renderer in a background task
    renderer_task = asyncio.create_task(renderer.start())

    try:
        for gen in range(MAX_GENERATIONS):
            # A. Get next state (Theoretical Truth)
            theo_grid = golden.step().astype(np.float32)
            
            # B. Simulate Actual Grid (copy truth)
            # We map this to the Diff codes:
            # 0.0 = Dead, 1.0 = Alive
            diff_grid = theo_grid.copy()

            # --- Inject Fake Errors ---
            if 20 <= gen < 25:
                # Ghost cell (False Positive -> 2.0 -> Red)
                diff_grid[5, 5] = 2.0
                renderer.set_extra_info(f"Gen {gen}: Injecting False Positive (Red)")
            elif 30 <= gen < 35:
                # Remove cell (False Negative -> 3.0 -> Cyan)
                glider_pos = np.where(theo_grid == 1)
                if len(glider_pos[0]) > 0:
                    diff_grid[glider_pos[0][0], glider_pos[1][0]] = 3.0
                renderer.set_extra_info(f"Gen {gen}: Injecting False Negative (Cyan)")
            else:
                renderer.set_extra_info(f"Gen {gen}: Perfect Match")

            # C. Ingest Full Frame
            renderer.ingest_full(diff_grid)
            
            # D. Wait
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