"""
truth_visualizer_demo.py - 3-Network Validation Demo (Fixed)

This script demonstrates the "A/B/C" validation model.
Network A: Simulated Cluster (with injected errors)
Network B: Step Predictor (Internal to Validator)
Network C: Absolute Truth (Internal to Validator)

Scenarios:
1. Logic Error (FP): Sudden appearance of a block.
   - Frame T: Red (A has it, B doesn't)
   - Frame T+1: Gold (A has it, B predicts it, C doesn't)
2. Logic Error (FN): Sudden disappearance of everything.
   - Frame T: Cyan (A empty, B has life)
   - Frame T+1: Violet (A empty, B predicts empty, C has life)
"""

import asyncio
import numpy as np

from observatory.protoplasm.truth.golden_ca import GoldenLife
from observatory.protoplasm.truth.validator import StateValidator
from observatory.visualization.raw_app import RawTerminalApp as TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes

# --- Test Configuration ---
GRID_WIDTH = 50
GRID_HEIGHT = 25
MAX_GENERATIONS = 200
FRAME_DELAY = 0.05


def get_glider_seed(width: int, height: int) -> np.ndarray:
    grid = np.zeros((height, width), dtype=np.int8)
    # Glider at (1,1)
    grid[1, 2] = 1
    grid[2, 3] = 1
    grid[3, 1:4] = 1
    return grid


async def main():
    print("🚀 Starting 3-Network Validation Demo...")

    # 1. Network A (The "Actual" System we are simulating)
    simulated_cluster = GoldenLife(GRID_WIDTH, GRID_HEIGHT)
    seed = get_glider_seed(GRID_WIDTH, GRID_HEIGHT)
    simulated_cluster.seed(seed)

    # 2. Setup UI
    grid_view = GridView(
        width=GRID_WIDTH,
        height=GRID_HEIGHT,
        palette_func=Palettes.truth_diff,
        decay_per_second=0.0,
    )
    status_bar = StatusBar({"Generation": 0, "Status": "Init"})
    app = TerminalApp(grid_view, status_bar)

    # 3. Setup Validator
    validator = StateValidator(GRID_WIDTH, GRID_HEIGHT, connector=None, app=app)

    await app.start()
    try:
        # Feed Gen 0
        validator.ingest_full_state(0, seed)
        await asyncio.sleep(1.0)

        for gen in range(1, MAX_GENERATIONS):
            # --- Step Network A ---
            grid_a = simulated_cluster.step()

            # --- Inject Errors ---
            injected = False

            # Scenario 1: Gen 30 - The "Bunker" Injection
            # Inject a 2x2 Block (Still Life) at (10, 10).
            # It survives forever.
            if gen == 30:
                grid_a[10:12, 10:12] = 1
                injected = True
                app.update_status("Event", "INJECT: Logic FP (Red Block)")

            if gen == 32:
                app.update_status("Event", "Result: Drift (Gold Block)")

            # Scenario 2: Gen 100 - The "Extinction" Event
            # Wipe out the entire grid.
            if gen == 100:
                grid_a.fill(0)
                injected = True
                app.update_status("Event", "INJECT: Mass Logic FN (Cyan)")

            # CRITICAL FIX: If we modified grid_a, we MUST write it back
            # to the simulator so the error persists/propagates!
            if injected:
                simulated_cluster.seed(grid_a)

            # --- Validation ---
            validator.ingest_full_state(gen, grid_a)

            # --- Render Speed Control ---
            await asyncio.sleep(FRAME_DELAY)

    finally:
        app.stop()
        print("\n✅ Demo Finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted.")
