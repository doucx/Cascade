import asyncio
import time
import numpy as np
from typing import Dict, Any, List, Optional
from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife

# New Renderer
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes

class StateValidator:
    def __init__(self, width: int, height: int, connector: Connector, enable_ui: bool = True):
        self.width = width
        self.height = height
        self.connector = connector
        self.golden = GoldenLife(width, height)
        
        # UI
        self.enable_ui = enable_ui
        # We use UniGrid now with the 'truth' palette and 0 decay (crisp state)
        self.renderer = UniGridRenderer(
            width=width, 
            height=height, 
            palette_func=Palettes.truth, 
            decay_rate=0.0
        ) if enable_ui else None
        
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
            await self.renderer.start()
        else:
            print(f"⚖️  Validator active. Grid: {self.width}x{self.height}. Dual-Truth Mode Enabled.")
        
        sub = await self.connector.subscribe("validator/report", self.on_report)
        
        try:
            # Main validation loop
            # Since renderer has its own loop, we just process buffers here
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
        next_gen = self.max_gen_verified + 1
        
        if next_gen not in self.buffer:
            if self.renderer:
                self._update_ui_status(next_gen, 0)
            return

        current_buffer = self.buffer[next_gen]
        
        if len(current_buffer) < self.total_agents:
            if self.renderer:
                self._update_ui_status(next_gen, len(current_buffer))
            return
            
        self._verify_generation(next_gen, current_buffer)
        
        del self.buffer[next_gen]
        if next_gen - 2 in self.history_actual:
            del self.history_actual[next_gen - 2]
        if next_gen - 2 in self.history_theoretical:
            del self.history_theoretical[next_gen - 2]
            
        self.max_gen_verified = next_gen

    def _update_ui_status(self, gen: int, current_count: int):
        progress = current_count / self.total_agents if self.total_agents > 0 else 0
        bar_len = 10
        filled = int(bar_len * progress)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        status = (
            f"Gen {gen}: [{bar}] {current_count}/{self.total_agents} | "
            f"Err(Abs/Rel): {self.absolute_errors}/{self.relative_errors}"
        )
        self.renderer.set_extra_info(status)

    def _verify_generation(self, gen: int, reports: Dict[int, Any]):
        # 1. Construct Actual Grid
        actual_grid = np.zeros((self.height, self.width), dtype=np.float32)
        for r in reports.values():
            x, y = r['coords']
            actual_grid[y, x] = float(r['state']) # 0.0 or 1.0
            
        self.history_actual[gen] = actual_grid

        # 2. Validation
        if gen == 0:
            self.golden.seed(actual_grid.astype(np.int8))
            self.history_theoretical[0] = actual_grid
            theo_grid = actual_grid
            diff_grid = actual_grid # 0 or 1
        else:
            prev_theo = self.history_theoretical.get(gen - 1)
            
            if prev_theo is not None:
                self.golden.seed(prev_theo.astype(np.int8))
                theo_grid = self.golden.step().astype(np.float32)
                self.history_theoretical[gen] = theo_grid
                
                # Compute Diff Matrix for Visualization
                # 0.0: Dead Correct
                # 1.0: Alive Correct
                # 2.0: False Positive (actual=1, theo=0)
                # 3.0: False Negative (actual=0, theo=1)
                
                diff_grid = np.zeros_like(actual_grid)
                
                # Matches
                mask_dead = (actual_grid == 0) & (theo_grid == 0)
                mask_alive = (actual_grid == 1) & (theo_grid == 1)
                diff_grid[mask_dead] = 0.0
                diff_grid[mask_alive] = 1.0
                
                # Errors
                mask_fp = (actual_grid == 1) & (theo_grid == 0)
                mask_fn = (actual_grid == 0) & (theo_grid == 1)
                diff_grid[mask_fp] = 2.0
                diff_grid[mask_fn] = 3.0
                
                # Update Stats
                self.absolute_errors += np.sum(mask_fp | mask_fn)
                
                # Relative check (omitted for render logic simplification, logic kept in memory)
                prev_actual = self.history_actual.get(gen - 1)
                if prev_actual is not None:
                     self.golden.seed(prev_actual.astype(np.int8))
                     expected_rel = self.golden.step()
                     self.relative_errors += np.sum(actual_grid != expected_rel)

            else:
                theo_grid = actual_grid
                diff_grid = actual_grid

        # 3. Render
        if self.renderer:
            self.renderer.ingest_full(diff_grid)
            self._update_ui_status(gen, self.total_agents)
        else:
            # Fallback text log
            pass

    def stop(self):
        self._running = False