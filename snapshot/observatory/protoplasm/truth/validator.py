import asyncio
import numpy as np
from typing import Dict, Any, Optional

from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife
from observatory.protoplasm.renderer.unigrid import UniGridRenderer

class StateValidator:
    def __init__(self, width: int, height: int, connector: Connector, renderer: Optional[UniGridRenderer] = None):
        self.width = width
        self.height = height
        self.connector = connector
        self.golden = GoldenLife(width, height)
        self.renderer = renderer
        
        self.buffer: Dict[int, Dict[int, Any]] = {}
        self.history_actual: Dict[int, np.ndarray] = {}
        
        self.total_agents = width * height
        self._running = False
        
        self.absolute_errors = 0
        self.relative_errors = 0
        self.max_gen_verified = -1

    async def run(self):
        self._running = True
        sub = await self.connector.subscribe("validator/report", self.on_report)
        
        try:
            while self._running:
                self._process_buffers()
                await asyncio.sleep(0.01) # Small sleep to yield control
        finally:
            await sub.unsubscribe()

    async def on_report(self, topic: str, payload: Any):
        gen = payload.get('gen')
        agent_id = payload.get('id')
        if gen is None or agent_id is None: return

        if gen not in self.buffer:
            self.buffer[gen] = {}
        self.buffer[gen][agent_id] = payload

    def _process_buffers(self):
        next_gen = self.max_gen_verified + 1
        
        if next_gen not in self.buffer:
            return

        current_buffer = self.buffer[next_gen]
        if len(current_buffer) < self.total_agents:
            return # Wait for all reports
            
        self._verify_and_render_generation(next_gen, current_buffer)
        
        del self.buffer[next_gen]
        if next_gen - 2 in self.history_actual:
            del self.history_actual[next_gen - 2]
            
        self.max_gen_verified = next_gen

    def _verify_and_render_generation(self, gen: int, reports: Dict[int, Any]):
        # 1. Construct Actual Grid from agent reports
        actual_grid = np.zeros((self.height, self.width), dtype=np.int8)
        for r in reports.values():
            x, y = r['coords']
            actual_grid[y, x] = r['state']
        self.history_actual[gen] = actual_grid

        # 2. Calculate Theoretical Grid (Golden Reference)
        if gen == 0:
            self.golden.seed(actual_grid)
            theoretical_grid = actual_grid.copy()
        else:
            prev_actual = self.history_actual.get(gen - 1)
            if prev_actual is not None:
                self.golden.seed(prev_actual)
                theoretical_grid = self.golden.step()
                
                # Update error counts based on diff
                diff = np.sum(actual_grid != theoretical_grid)
                self.absolute_errors += diff
            else:
                # Fallback if history is missing
                theoretical_grid = actual_grid.copy()

        # 3. Render
        if self.renderer:
            # Create the diff matrix for the palette
            # 0=Dead, 1=Alive, 2=Ghost, 3=Missing
            diff_matrix = np.zeros_like(actual_grid, dtype=np.float32)
            diff_matrix[(actual_grid == 1) & (theoretical_grid == 1)] = 1.0 # Match-Alive
            diff_matrix[(actual_grid == 1) & (theoretical_grid == 0)] = 2.0 # Ghost
            diff_matrix[(actual_grid == 0) & (theoretical_grid == 1)] = 3.0 # Missing

            self.renderer.update_full_matrix(diff_matrix)

            status_icon = "✅ SYNC" if self.absolute_errors == 0 else "❌ DRIFT"
            info = f"GEN: {gen} | Status: {status_icon} | Total Errors: {self.absolute_errors}"
            self.renderer.set_extra_info(info)

    def stop(self):
        self._running = False