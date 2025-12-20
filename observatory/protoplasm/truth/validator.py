import asyncio
import numpy as np
from typing import Dict, Any, Optional

from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife
from observatory.visualization.app import TerminalApp

class StateValidator:
    """
    Implements the 3-Network Validation Model:
    Network A: Actual State (from Telemetry or Simulation)
    Network B: Relative Truth (Stepwise prediction based on A[t-1])
    Network C: Absolute Truth (Pathfinding based on Initial Seed)
    """
    def __init__(self, width: int, height: int, connector: Connector, app: Optional[TerminalApp] = None):
        self.width = width
        self.height = height
        self.connector = connector
        self.app = app
        
        # Network B: Relative Predictor (Resets every gen)
        self.golden_relative = GoldenLife(width, height)
        
        # Network C: Absolute Truth (Persists)
        self.golden_absolute = GoldenLife(width, height)
        
        # Internal Diff Matrix for rendering (0-5 states)
        self.diff_matrix = np.zeros((height, width), dtype=np.int8)
        
        # Buffers for Async Aggregation
        self.buffer: Dict[int, Dict[int, int]] = {}
        self.history_actual: Dict[int, np.ndarray] = {}
        
        self.total_agents = width * height
        self._running = False
        
        # Stats
        self.stats = {
            "logic_errors": 0, # A != B
            "drift_errors": 0  # A != C
        }
        self.max_gen_verified = -1

    async def run(self):
        """Async listener loop for the real experiment."""
        self._running = True
        if not self.app:
            print(f"⚖️  Validator active (headless). Grid: {self.width}x{self.height}.")
        
        sub = await self.connector.subscribe("validator/report", self.on_report)
        try:
            while self._running:
                self._process_buffers()
                await asyncio.sleep(0.01)
        finally:
            await sub.unsubscribe()

    async def on_report(self, topic: str, payload: Any):
        """Collects async reports from agents."""
        gen = payload['gen']
        agent_id = payload['id']
        
        if gen not in self.buffer:
            self.buffer[gen] = {}
        self.buffer[gen][agent_id] = payload

    def _process_buffers(self):
        """Checks if we have a full frame to verify."""
        next_gen = self.max_gen_verified + 1
        
        if next_gen not in self.buffer:
            if self.app and next_gen > 0:
                 self._update_progress_ui(next_gen, 0)
            return

        current_buffer = self.buffer[next_gen]
        
        if len(current_buffer) < self.total_agents:
            if self.app:
                self._update_progress_ui(next_gen, len(current_buffer))
            return
            
        # Reconstruct full grid A
        actual_grid = np.zeros((self.height, self.width), dtype=np.int8)
        for r in current_buffer.values():
            x, y = r['coords']
            actual_grid[y, x] = r['state']
            
        # Verify
        self.ingest_full_state(next_gen, actual_grid)
        
        # Cleanup
        del self.buffer[next_gen]
        # Keep minimal history for Relative prediction
        if next_gen - 2 in self.history_actual:
            del self.history_actual[next_gen - 2]
            
        self.max_gen_verified = next_gen

    def _update_progress_ui(self, gen, count):
        bar_len = 20
        progress = count / self.total_agents
        filled = int(bar_len * progress)
        bar = "█" * filled + "░" * (bar_len - filled)
        self.app.update_status("Progress", f"Gen {gen}: [{bar}]")

    def ingest_full_state(self, gen: int, grid_a: np.ndarray):
        """
        Direct entry point for validation. 
        Can be called by _process_buffers (Async) or directly by Demo (Sync).
        """
        # Store A for future B predictions
        self.history_actual[gen] = grid_a.copy()

        # --- 1. Compute Network C (Absolute Truth) ---
        if gen == 0:
            self.golden_absolute.seed(grid_a)
            grid_c = grid_a # At gen 0, C is defined by A
        else:
            # C steps forward from its own internal state
            grid_c = self.golden_absolute.step()

        # --- 2. Compute Network B (Relative Truth) ---
        if gen == 0:
            grid_b = grid_a # At gen 0, B is defined by A
        else:
            # B steps forward from A's LAST state
            prev_a = self.history_actual.get(gen - 1)
            if prev_a is not None:
                self.golden_relative.seed(prev_a)
                grid_b = self.golden_relative.step()
            else:
                # Should not happen in sequential exec, fallback to C
                grid_b = grid_c

        # --- 3. Compute Diff Matrix ---
        self._compute_diff(grid_a, grid_b, grid_c)
        
        # --- 4. Update UI ---
        if self.app:
            self.app.ingest_full_matrix(self.diff_matrix)
            self.app.update_status("Generation", gen)
            
            logic_err = np.sum((grid_a != grid_b))
            drift_err = np.sum((grid_a != grid_c))
            
            self.stats["logic_errors"] += logic_err
            self.stats["drift_errors"] += drift_err
            
            status_icon = "✅ SYNC" if (logic_err + drift_err) == 0 else "❌ ERROR"
            self.app.update_status("Status", status_icon)
            self.app.update_status("Logic Err", f"{logic_err} (Cum: {self.stats['logic_errors']})")
            self.app.update_status("Drift Err", f"{drift_err} (Cum: {self.stats['drift_errors']})")

    def _compute_diff(self, A: np.ndarray, B: np.ndarray, C: np.ndarray):
        """
        Generates the visualization mask.
        Priority: Logic Error (vs B) > Drift Error (vs C) > Correct
        """
        self.diff_matrix.fill(0) # Default Dead
        
        # 1. Base Correct State (Matches A)
        self.diff_matrix[A == 1] = 1 
        
        # 2. Drift Errors (A vs C) - Warning Level
        # FP: A=1, C=0 -> 4 (Gold)
        mask_drift_fp = (A == 1) & (C == 0)
        self.diff_matrix[mask_drift_fp] = 4
        
        # FN: A=0, C=1 -> 5 (Violet)
        mask_drift_fn = (A == 0) & (C == 1)
        self.diff_matrix[mask_drift_fn] = 5
        
        # 3. Logic Errors (A vs B) - Critical Level (Overwrites Drift)
        # FP: A=1, B=0 -> 2 (Red)
        mask_logic_fp = (A == 1) & (B == 0)
        self.diff_matrix[mask_logic_fp] = 2
        
        # FN: A=0, B=1 -> 3 (Cyan)
        mask_logic_fn = (A == 0) & (B == 1)
        self.diff_matrix[mask_logic_fn] = 3

    def stop(self):
        self._running = False