import asyncio
import numpy as np
from typing import Dict, Any, Optional

from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife
from observatory.visualization.app import TerminalApp # New import

class StateValidator:
    def __init__(self, width: int, height: int, connector: Connector, app: Optional[TerminalApp] = None):
        self.width = width
        self.height = height
        self.connector = connector
        self.golden = GoldenLife(width, height)
        self.app = app # Store the app instance
        
        # This internal matrix computes the diff state (0,1,2,3)
        self.diff_matrix = np.zeros((height, width), dtype=np.int8)
        
        # buffer[gen][agent_id] = state
        self.buffer: Dict[int, Dict[int, int]] = {}
        
        self.history_theoretical: Dict[int, np.ndarray] = {}
        self.history_actual: Dict[int, np.ndarray] = {}
        
        self.total_agents = width * height
        self._running = False
        
        self.absolute_errors = 0
        self.relative_errors = 0
        self.max_gen_verified = -1

    async def run(self):
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
        gen = payload['gen']
        agent_id = payload['id']
        
        if gen not in self.buffer:
            self.buffer[gen] = {}
        self.buffer[gen][agent_id] = payload

    def _process_buffers(self):
        next_gen = self.max_gen_verified + 1
        
        if next_gen not in self.buffer:
            if self.app:
                progress = 0
                bar = "░" * 20
                self.app.update_status("Progress", f"Gen {next_gen}: [{bar}] 0/{self.total_agents}")
            return

        current_buffer = self.buffer[next_gen]
        
        if len(current_buffer) < self.total_agents:
            if self.app:
                progress = len(current_buffer) / self.total_agents
                bar_len = 20
                filled = int(bar_len * progress)
                bar = "█" * filled + "░" * (bar_len - filled)
                self.app.update_status("Progress", f"Gen {next_gen}: [{bar}] {len(current_buffer)}/{self.total_agents}")
            return
            
        self._verify_generation(next_gen, current_buffer)
        
        del self.buffer[next_gen]
        if next_gen - 2 in self.history_actual: del self.history_actual[next_gen - 2]
        if next_gen - 2 in self.history_theoretical: del self.history_theoretical[next_gen - 2]
            
        self.max_gen_verified = next_gen

    def _verify_generation(self, gen: int, reports: Dict[int, Any]):
        actual_grid = np.zeros((self.height, self.width), dtype=np.int8)
        for r in reports.values():
            x, y = r['coords']
            actual_grid[y, x] = r['state']
        self.history_actual[gen] = actual_grid

        if gen == 0:
            self.golden.seed(actual_grid)
            self.history_theoretical[0] = actual_grid
            theo_grid = actual_grid
        else:
            prev_theo = self.history_theoretical.get(gen - 1, actual_grid)
            self.golden.seed(prev_theo)
            theo_grid = self.golden.step()
            self.history_theoretical[gen] = theo_grid
            
            diff_abs = np.sum(actual_grid != theo_grid)
            self.absolute_errors += diff_abs
            
            prev_actual = self.history_actual.get(gen - 1, actual_grid)
            self.golden.seed(prev_actual)
            expected_relative = self.golden.step()
            diff_rel = np.sum(actual_grid != expected_relative)
            self.relative_errors += diff_rel
            
        # Update internal diff matrix for rendering
        self.diff_matrix.fill(0) # 0: Dead (Correct)
        self.diff_matrix[(actual_grid == 1) & (theo_grid == 1)] = 1 # 1: Alive (Correct)
        self.diff_matrix[(actual_grid == 1) & (theo_grid == 0)] = 2 # 2: False Positive
        self.diff_matrix[(actual_grid == 0) & (theo_grid == 1)] = 3 # 3: False Negative
        
        # Push updates to the UI
        if self.app:
            self.app.ingest_full_matrix(self.diff_matrix)
            total_err = self.absolute_errors + self.relative_errors
            status_icon = "✅ SYNC" if total_err == 0 else "❌ DRIFT"
            self.app.update_status("Generation", gen)
            self.app.update_status("Status", status_icon)
            self.app.update_status("Total Errors", total_err)
        else:
             # Headless logging
             print(f"Gen {gen} verified. Abs Errors: {self.absolute_errors}, Rel Errors: {self.relative_errors}")

    def stop(self):
        self._running = False