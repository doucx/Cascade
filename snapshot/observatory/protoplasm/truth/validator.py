import asyncio
import time
import numpy as np
from typing import Dict, Any, List
from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife

class StateValidator:
    def __init__(self, width: int, height: int, connector: Connector):
        self.width = width
        self.height = height
        self.connector = connector
        self.golden = GoldenLife(width, height)
        
        # buffer[gen][agent_id] = state
        self.buffer: Dict[int, Dict[int, int]] = {}
        # Stores the validated/truth state for each generation
        self.truth_history: Dict[int, np.ndarray] = {}
        
        self.total_agents = width * height
        self._running = False
        
        # Stats
        self.errors_found = 0
        self.max_gen_verified = -1

    async def run(self):
        self._running = True
        print(f"⚖️  Validator active. Grid: {self.width}x{self.height}")
        
        sub = await self.connector.subscribe("validator/report", self.on_report)
        
        try:
            while self._running:
                self._process_buffers()
                await asyncio.sleep(0.01)
        finally:
            await sub.unsubscribe()

    async def on_report(self, topic: str, payload: Any):
        """
        Payload: {id, coords: [x, y], gen, state}
        """
        gen = payload['gen']
        agent_id = payload['id']
        state = payload['state']
        
        if gen not in self.buffer:
            self.buffer[gen] = {}
            
        # Optimization: We could store (x,y) mapping once, but payload carries it.
        # For validation we need to map id -> (x,y) to construct the matrix.
        # Let's trust the coords in payload for now.
        if 'coords' in payload:
             # We store full metadata in buffer to reconstruct grid later
             self.buffer[gen][agent_id] = payload

    def _process_buffers(self):
        # Check if any generation is complete
        # We process generations in order.
        next_gen = self.max_gen_verified + 1
        
        if next_gen not in self.buffer:
            return

        current_buffer = self.buffer[next_gen]
        if len(current_buffer) < self.total_agents:
            # Waiting for more reports...
            return
            
        # Complete! Let's validate.
        print(f"[Validator] Verifying Generation {next_gen}...")
        self._verify_generation(next_gen, current_buffer)
        
        # Cleanup
        del self.buffer[next_gen]
        self.max_gen_verified = next_gen

    def _verify_generation(self, gen: int, reports: Dict[int, Any]):
        # 1. Construct Actual Grid
        actual_grid = np.zeros((self.height, self.width), dtype=np.int8)
        for r in reports.values():
            x, y = r['coords']
            actual_grid[y, x] = r['state']
            
        # 2. Get Expected Grid
        if gen == 0:
            # Gen 0 is the axiom. We set the golden reference to match it.
            self.golden.seed(actual_grid)
            self.truth_history[0] = actual_grid
            print("✅ Gen 0 accepted as Axiom.")
            return
        
        # For Gen > 0, we must calculate expectation from Gen-1 Truth
        prev_truth = self.truth_history.get(gen - 1)
        if prev_truth is None:
            print(f"❌ Missing truth for Gen {gen-1}, cannot verify Gen {gen}")
            return
            
        # Reset golden to prev state and step
        self.golden.seed(prev_truth)
        expected_grid = self.golden.step()
        self.truth_history[gen] = expected_grid
        
        # 3. Compare
        diff = actual_grid != expected_grid
        errors = np.sum(diff)
        
        if errors == 0:
            print(f"✅ Gen {gen} Verified. Perfect Match.")
        else:
            self.errors_found += errors
            print(f"🚨 Gen {gen} MISMATCH! {errors} errors found.")
            # Optional: Print diff locations
            rows, cols = np.where(diff)
            for r, c in zip(rows[:5], cols[:5]):
                print(f"   - Mismatch at ({c}, {r}): Expected {expected_grid[r,c]}, Got {actual_grid[r,c]}")
            if errors > 5: print("   ... and more.")

    def stop(self):
        self._running = False