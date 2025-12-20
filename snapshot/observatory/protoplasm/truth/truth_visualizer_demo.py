"""
truth_visualizer_demo.py - 3-Network Validation Demo

This script demonstrates the "A/B/C" validation model.
Network A: Simulated Cluster (with injected errors)
Network B: Step Predictor (Internal to Validator)
Network C: Absolute Truth (Internal to Validator)

It directly drives the StateValidator to visualize:
- Logic Errors (Red/Cyan): A diverges from B (Immediate computation error)
- Drift Errors (Gold/Violet): A matches B, but diverges from C (Wrong timeline)
"""
import asyncio
import numpy as np

from observatory.protoplasm.truth.golden_ca import GoldenLife
from observatory.protoplasm.truth.validator import StateValidator
from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes

# --- Test Configuration ---
GRID_WIDTH = 50
GRID_HEIGHT = 25
MAX_GENERATIONS = 300
FRAME_DELAY = 0.1

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
        palette_func=Palettes.truth_diff, # New 6-color palette
        decay_per_second=0.0
    )
    status_bar = StatusBar({"Generation": 0, "Status": "Init"})
    app = TerminalApp(grid_view, status_bar)

    # 3. Setup Validator (It holds Network B and C internally)
    # We pass None for connector as we will inject state manually
    validator = StateValidator(GRID_WIDTH, GRID_HEIGHT, connector=None, app=app)

    await app.start()
    try:
        # Feed Gen 0
        validator.ingest_full_state(0, seed)
        await asyncio.sleep(1.0) # Pause to see seed

        for gen in range(1, MAX_GENERATIONS):
            # --- Step Network A ---
            grid_a = simulated_cluster.step()
            
            # --- Inject Errors into A ---
            
            # Scenario 1: Logic Error (Flash in the pan) at Gen 30
            # A single cell flips wrongly, but A continues computing correctly from that error.
            # This causes an immediate Red/Cyan flash (Logic Error).
            # Then, because A's state is now physically different, it will drift from C.
            if gen == 30:
                # Inject a False Positive (Ghost)
                grid_a[10, 10] = 1 
                app.update_status("Event", "INJECT: Logic FP (Red)")
            
            if gen == 31:
                 app.update_status("Event", "Result: Drift (Gold)")

            # Scenario 2: Massive Logic Failure at Gen 100
            # A whole block fails to compute
            if gen == 100:
                grid_a[0:5, 0:5] = 0
                app.update_status("Event", "INJECT: Mass Logic FN (Cyan)")

            # --- Validation ---
            # We push A's state to the validator. 
            # It compares A vs B (Relative) and A vs C (Absolute).
            # It calculates the colors and updates the App.
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