import asyncio
import time
import numpy as np
from typing import Dict, Any, List, Optional
from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife
from .renderer import TruthRenderer

class StateValidator:
    def __init__(self, width: int, height: int, connector: Connector, enable_ui: bool = True):
        self.width = width
        self.height = height
        self.connector = connector
        self.golden = GoldenLife(width, height)
        
        # UI
        self.enable_ui = enable_ui
        self.renderer = TruthRenderer(width, height) if enable_ui else None
        
        # buffer[gen][agent_id] = state
        self.buffer: Dict[int, Dict[int, int]] = {}
        
        # History
        # theoretical: The pure timeline derived from T0
        self.history_theoretical: Dict[int, np.ndarray] = {}
        # actual: What the agents actually reported
        self.history_actual: Dict[int, np.ndarray] = {}
        
        self.total_agents = width * height
        self._running = False
        
        # Stats
        self.absolute_errors = 0
        self.relative_errors = 0
        self.max_gen_verified = -1

    async def run(self):
        self._running = True
        if self.renderer:
            self.renderer.start()
        else:
            print(f"⚖️  Validator active. Grid: {self.width}x{self.height}. Dual-Truth Mode Enabled.")
        
        sub = await self.connector.subscribe("validator/report", self.on_report)
        
        try:
            while self._running:
                self._process_buffers()
                await asyncio.sleep(0.01)
        finally:
            await sub.unsubscribe()
            if self.renderer:
                self.renderer.stop()

    async def on_report(self, topic: str, payload: Any):
        """
        Payload: {id, coords: [x, y], gen, state}
        """
        gen = payload['gen']
        agent_id = payload['id']
        
        if gen not in self.buffer:
            self.buffer[gen] = {}
            
        self.buffer[gen][agent_id] = payload

    def _process_buffers(self):
        # We process generations in strict order
        next_gen = self.max_gen_verified + 1
        
        # If no data at all yet, just return
        if next_gen not in self.buffer:
            if self.renderer:
                self.renderer.render_waiting(next_gen, 0, self.total_agents)
            return

        current_buffer = self.buffer[next_gen]
        
        # If incomplete, update UI but don't verify yet
        if len(current_buffer) < self.total_agents:
            if self.renderer:
                self.renderer.render_waiting(next_gen, len(current_buffer), self.total_agents)
            return
            
        self._verify_generation(next_gen, current_buffer)
        
        # Cleanup to save memory, keeping only immediate history needed for next step
        del self.buffer[next_gen]
        # We need history_actual[gen] for verifying gen+1 relative truth, so we keep recent history
        if next_gen - 2 in self.history_actual:
            del self.history_actual[next_gen - 2]
        if next_gen - 2 in self.history_theoretical:
            del self.history_theoretical[next_gen - 2]
            
        self.max_gen_verified = next_gen

    def _verify_generation(self, gen: int, reports: Dict[int, Any]):
        # 1. Construct Actual Grid (The Report)
        actual_grid = np.zeros((self.height, self.width), dtype=np.int8)
        for r in reports.values():
            x, y = r['coords']
            actual_grid[y, x] = r['state']
            
        self.history_actual[gen] = actual_grid

        # 2. Base Case: Gen 0
        if gen == 0:
            self.golden.seed(actual_grid)
            self.history_theoretical[0] = actual_grid
            print("🟦 [Gen 0] Axiom Set. System Initialized.")
            return
        
        # 3. Validation Logic
        
        # --- Check A: Absolute Truth (Trajectory) ---
        # Did we stay on the path defined by T0?
        prev_theo = self.history_theoretical.get(gen - 1)
        is_absolute_match = False
        
        if prev_theo is not None:
            self.golden.seed(prev_theo)
            theo_grid = self.golden.step()
            self.history_theoretical[gen] = theo_grid
            
            diff_abs = np.sum(actual_grid != theo_grid)
            if diff_abs == 0:
                is_absolute_match = True
            else:
                self.absolute_errors += diff_abs
        else:
            # Should not happen if processing in order
            print(f"⚠️  Missing history for Absolute check at Gen {gen}")

        # --- Check B: Relative Truth (Transition) ---
        # Did we calculate correctly based on what we had yesterday?
        prev_actual = self.history_actual.get(gen - 1)
        is_relative_match = False
        
        if prev_actual is not None:
            self.golden.seed(prev_actual)
            expected_relative = self.golden.step()
            
            diff_rel = np.sum(actual_grid != expected_relative)
            if diff_rel == 0:
                is_relative_match = True
            else:
                self.relative_errors += diff_rel
        else:
             print(f"⚠️  Missing history for Relative check at Gen {gen}")

        # 4. Reporting
        stats = {"abs": self.absolute_errors, "rel": self.relative_errors}

        if self.renderer:
            # Visualize the Diff: We compare ACTUAL vs THEORETICAL (Absolute Truth)
            self.renderer.update_frame(gen, actual_grid, theo_grid, stats)
        else:
            if is_absolute_match:
                print(f"✅ [Gen {gen}] PERFECT MATCH (Absolute & Relative)")
            elif is_relative_match:
                print(f"🟡 [Gen {gen}] DRIFT DETECTED. Logic is correct (Relative Pass), but state diverged from T0.")
            else:
                print(f"🔴 [Gen {gen}] LOGIC FAILURE. Transition from T{gen-1} to T{gen} is incorrect. Errors: {self.relative_errors}")

    def stop(self):
        self._running = False