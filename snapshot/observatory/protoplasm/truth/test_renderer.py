import asyncio
import numpy as np
import shutil
import random

from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes
from observatory.protoplasm.truth.golden_ca import GoldenLife

# --- Test Configuration ---
GRID_WIDTH = 40
GRID_HEIGHT = 20
MAX_GENERATIONS = 200
FRAME_DELAY = 0.05  # seconds

def get_glider_seed(width: int, height: int) -> np.ndarray:
    grid = np.zeros((height, width), dtype=np.int8)
    grid[1, 2] = 1; grid[2, 3] = 1; grid[3, 1:4] = 1
    return grid

async def main():
    print("🚀 Starting UniGrid Renderer Test for Conway...")
    
    golden = GoldenLife(GRID_WIDTH, GRID_HEIGHT)
    golden.seed(get_glider_seed(GRID_WIDTH, GRID_HEIGHT))

    renderer = UniGridRenderer(
        width=GRID_WIDTH,
        height=GRID_HEIGHT,
        palette_func=Palettes.conway_diff,
        decay_rate=0.0
    )
    
    renderer_task = asyncio.create_task(renderer.start())
    # Allow renderer to initialize
    await asyncio.sleep(0.1)

    try:
        for gen in range(MAX_GENERATIONS):
            theoretical_grid = golden.step()
            actual_grid = theoretical_grid.copy()
            
            abs_err, rel_err = 0, 0

            # --- Inject fake errors to test colors ---
            if 20 <= gen < 25:
                actual_grid[5, 5] = 1 
                abs_err +=1
            if 30 <= gen < 35:
                glider_pos = np.where(theoretical_grid == 1)
                if len(glider_pos[0]) > 0:
                    actual_grid[glider_pos[0][0], glider_pos[1][0]] = 0
                    abs_err +=1
            
            # --- Manually compute and push frame state ---
            diff_matrix = np.zeros_like(actual_grid)
            diff_matrix[(actual_grid == 1) & (theoretical_grid == 1)] = 1
            diff_matrix[(actual_grid == 1) & (theoretical_grid == 0)] = 2
            diff_matrix[(actual_grid == 0) & (theoretical_grid == 1)] = 3
            
            # Push data to renderer's matrix
            renderer.matrix.brightness = diff_matrix
            
            # Update status info
            total_err = abs_err + rel_err
            status_icon = "✅ SYNC" if total_err == 0 else "❌ DRIFT"
            status_msg = f"GEN: {gen} | Status: {status_icon} | Test Mode"
            renderer.set_extra_info(status_msg)
            
            await asyncio.sleep(FRAME_DELAY)

    finally:
        renderer.stop()
        if not renderer_task.done():
            renderer_task.cancel()
        print("\n✅ Renderer Test Finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")