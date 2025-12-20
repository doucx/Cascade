import asyncio
import time
import numpy as np
from typing import Dict, Any, List, Optional
from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife
# Replace old renderer with UniGrid
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes

class StateValidator:
    def __init__(self, width: int, height: int, connector: Connector, enable_ui: bool = True):
        self.width = width
        self.height = height
        self.connector = connector
        self.golden = GoldenLife(width, height)
        
        # UI: Use UniGrid with Truth Palette and 0 decay
        self.enable_ui = enable_ui
        self.renderer = None
        if enable_ui:
            self.renderer = UniGridRenderer(
                width=width, 
                height=height, 
                palette_func=Palettes.truth,
                decay_rate=0.0 # No decay for discrete CA states
            )
        
        # buffer[gen][agent_id] = state
        self.buffer: Dict[int, Dict[int, int]] = {}
        
        # History
        self.history_theoretical: Dict[int, np.ndarray] = {}
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
            # UniGrid start is an async task
            self._renderer_task = asyncio.create_task(self.renderer.start())
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
                if not self._renderer_task.done():
                    self._renderer_task.cancel()
                    await self._renderer_task

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
        next_gen = self.max_gen_verified + 1
        
        if next_gen not in self.buffer:
            self._update_ui_status(next_gen, 0)
            return

        current_buffer = self.buffer[next_gen]
        
        if len(current_buffer) < self.total_agents:
            self._update_ui_status(next_gen, len(current_buffer))
            return
            
        self._verify_generation(next_gen, current_buffer)
        
        del self.buffer[next_gen]
        if next_gen - 2 in self.history_actual:
            del self.history_actual[next_gen - 2]
        if next_gen - 2 in self.history_theoretical:
            del self.history_theoretical[next_gen - 2]
            
        self.max_gen_verified = next_gen

    def _update_ui_status(self, gen: int, current: int):
        if not self.renderer:
            return
            
        total = self.total_agents
        progress = current / total if total > 0 else 0
        bar_len = 10
        filled = int(bar_len * progress)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        status_icon = "✅" if (self.absolute_errors + self.relative_errors) == 0 else "❌"
        
        info = (
            f"Gen {gen}: [{bar}] | "
            f"{status_icon} Err: {self.absolute_errors+self.relative_errors} "
            f"(Abs:{self.absolute_errors} Rel:{self.relative_errors})"
        )
        self.renderer.set_extra_info(info)

    def _verify_generation(self, gen: int, reports: Dict[int, Any]):
        # 1. Construct Actual Grid
        actual_grid = np.zeros((self.height, self.width), dtype=np.int8)
        for r in reports.values():
            x, y = r['coords']
            actual_grid[y, x] = r['state']
            
        self.history_actual[gen] = actual_grid

        # 2. Base Case: Gen 0
        if gen == 0:
            self.golden.seed(actual_grid)
            self.history_theoretical[0] = actual_grid
            theo_grid = actual_grid
        else:
            # 3. Validation Logic
            prev_theo = self.history_theoretical.get(gen - 1)
            theo_grid = actual_grid # Fallback
            
            if prev_theo is not None:
                self.golden.seed(prev_theo)
                theo_grid = self.golden.step()
                self.history_theoretical[gen] = theo_grid
                
                diff_abs = np.sum(actual_grid != theo_grid)
                if diff_abs > 0:
                    self.absolute_errors += diff_abs

            # Check B: Relative Truth
            prev_actual = self.history_actual.get(gen - 1)
            if prev_actual is not None:
                self.golden.seed(prev_actual)
                expected_relative = self.golden.step()
                diff_rel = np.sum(actual_grid != expected_relative)
                if diff_rel > 0:
                    self.relative_errors += diff_rel

        # 4. Visualization Update
        if self.renderer:
            # Encode states for Palette.truth
            # 0.0: Match Dead
            # 1.0: Match Alive
            # 2.0: False Positive
            # 3.0: False Negative
            
            display_grid = np.zeros(actual_grid.shape, dtype=np.float32)
            
            # Match Alive
            display_grid[(actual_grid == 1) & (theo_grid == 1)] = 1.0
            # False Positive
            display_grid[(actual_grid == 1) & (theo_grid == 0)] = 2.0
            # False Negative
            display_grid[(actual_grid == 0) & (theo_grid == 1)] = 3.0
            
            # Ingest Full Frame
            self.renderer.ingest_full(display_grid)
            
            # Force status update
            self._update_ui_status(gen + 1, 0)

    def stop(self):
        self._running = False