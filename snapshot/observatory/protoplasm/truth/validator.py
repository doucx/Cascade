import asyncio
import numpy as np
from typing import Dict, Any

from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes

class StateValidator:
    def __init__(self, width: int, height: int, connector: Connector, enable_ui: bool = True):
        self.width = width
        self.height = height
        self.connector = connector
        self.golden = GoldenLife(width, height)
        
        self.enable_ui = enable_ui
        self.renderer = None
        if enable_ui:
            self.renderer = UniGridRenderer(
                width=width, 
                height=height, 
                palette_func=Palettes.conway_diff, 
                decay_rate=0.0  # Conway state is absolute, no decay
            )
        
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
        renderer_task = None
        if self.renderer:
            renderer_task = asyncio.create_task(self.renderer.start())

        sub = await self.connector.subscribe("validator/report", self.on_report)
        
        try:
            while self._running:
                self._process_buffers()
                await asyncio.sleep(0.01)
        finally:
            await sub.unsubscribe()
            if self.renderer:
                self.renderer.stop()
            if renderer_task and not renderer_task.done():
                renderer_task.cancel()

    async def on_report(self, topic: str, payload: Any):
        gen, agent_id = payload['gen'], payload['id']
        if gen not in self.buffer: self.buffer[gen] = {}
        self.buffer[gen][agent_id] = payload

    def _process_buffers(self):
        next_gen = self.max_gen_verified + 1
        
        if next_gen not in self.buffer:
            if self.renderer:
                self._update_waiting_status(next_gen, 0)
            return

        current_buffer = self.buffer[next_gen]
        if len(current_buffer) < self.total_agents:
            if self.renderer:
                self._update_waiting_status(next_gen, len(current_buffer))
            return
            
        self._verify_generation(next_gen, current_buffer)
        
        del self.buffer[next_gen]
        if next_gen - 2 in self.history_actual: del self.history_actual[next_gen - 2]
        if next_gen - 2 in self.history_theoretical: del self.history_theoretical[next_gen - 2]
            
        self.max_gen_verified = next_gen

    def _update_waiting_status(self, gen: int, current_count: int):
        progress = current_count / self.total_agents if self.total_agents > 0 else 0
        bar = "█" * int(10 * progress) + "░" * (10 - int(10 * progress))
        status = f"Next Gen {gen}: [{bar}] {current_count}/{self.total_agents}"
        self.renderer.set_extra_info(status)

    def _verify_generation(self, gen: int, reports: Dict[int, Any]):
        actual_grid = np.zeros((self.height, self.width), dtype=np.int8)
        for r in reports.values():
            x, y = r['coords']
            actual_grid[y, x] = r['state']
        self.history_actual[gen] = actual_grid

        # --- Calculate theoretical grid ---
        if gen == 0:
            self.golden.seed(actual_grid)
            theo_grid = actual_grid
        else:
            prev_theo = self.history_theoretical.get(gen - 1)
            self.golden.seed(prev_theo)
            theo_grid = self.golden.step()
        
        self.history_theoretical[gen] = theo_grid

        # --- Update Errors ---
        if gen > 0:
            diff_abs = np.sum(actual_grid != theo_grid)
            if diff_abs > 0: self.absolute_errors += diff_abs
            
            prev_actual = self.history_actual.get(gen - 1)
            self.golden.seed(prev_actual)
            expected_relative = self.golden.step()
            diff_rel = np.sum(actual_grid != expected_relative)
            if diff_rel > 0: self.relative_errors += diff_rel

        # --- Render ---
        if self.renderer:
            # Create diff matrix for the palette
            diff_matrix = np.zeros_like(actual_grid)
            diff_matrix[(actual_grid == 1) & (theo_grid == 1)] = 1 # Match Alive
            diff_matrix[(actual_grid == 1) & (theo_grid == 0)] = 2 # False Positive
            diff_matrix[(actual_grid == 0) & (theo_grid == 1)] = 3 # False Negative
            
            # Push the full frame state
            self.renderer.matrix.brightness = diff_matrix
            
            # Update status bar
            total_err = self.absolute_errors + self.relative_errors
            status_icon = "✅ SYNC" if total_err == 0 else "❌ DRIFT"
            status_msg = f"GEN: {gen} | Status: {status_icon} | Total Err: {total_err}"
            self.renderer.set_extra_info(status_msg)

    def stop(self):
        self._running = False