import asyncio
import time
import random
import numpy as np
from asyncio import Queue

from .driver import AnsiDriver
from .matrix import StateMatrix, GridConfig
from .buffer import RenderBuffer

class ForestRenderer:
    """
    The High-Performance CLI Renderer.
    Decouples ingestion (Telemetry) from Rendering (30 FPS Loop).
    """

    def __init__(self, width: int = 100, height: int = 100):
        self.config = GridConfig(width=width, height=height, decay_rate=0.05)
        self.matrix = StateMatrix(self.config)
        
        # Double Buffering
        self.buffer_prev = RenderBuffer(width, height)
        self.buffer_curr = RenderBuffer(width, height)
        
        self.driver = AnsiDriver()
        
        # High-throughput ingestion queue
        # Items are tuples: (x, y, state)
        self.queue: Queue = Queue()
        
        self._running = False
        self._fps_stats = []

    async def start(self):
        self._running = True
        self.driver.clear_screen()
        self.driver.hide_cursor()
        self.driver.flush()
        
        # Start loops
        # In a real app, ingestion is driven by external calls to put(), 
        # but here we consume the queue in the render loop or a separate task.
        # Actually, since matrix update is fast, we can do it in the render loop phase.
        
        await self._render_loop()

    def stop(self):
        self._running = False
        self.driver.show_cursor()
        self.driver.reset # Reset colors
        self.driver.flush()
        self.driver.close()

    def ingest(self, x: int, y: int, state: float = 1.0):
        """Thread-safe / Async-safe ingestion point."""
        self.queue.put_nowait((x, y, state))

    async def _render_loop(self):
        target_fps = 30
        frame_time = 1.0 / target_fps
        
        print(f"Starting Render Loop at {target_fps} FPS...")
        
        last_loop_time = time.perf_counter()

        while self._running:
            loop_start = time.perf_counter()
            
            # 1. Ingestion Phase: Drain the queue
            events_processed = 0
            while not self.queue.empty():
                try:
                    x, y, state = self.queue.get_nowait()
                    self.matrix.update(x, y, state)
                    events_processed += 1
                except asyncio.QueueEmpty:
                    break
            
            # 2. Physics Phase: Decay
            self.matrix.decay()
            
            # 3. Render Phase: Matrix -> Buffer
            self.buffer_curr.update_from_matrix(self.matrix.brightness)
            
            # 4. Diff Phase
            rows, cols = RenderBuffer.compute_diff(self.buffer_prev, self.buffer_curr)
            
            # 5. Draw Phase
            if len(rows) > 0:
                chars = self.buffer_curr.chars[rows, cols]
                colors = self.buffer_curr.colors[rows, cols]
                
                for r, c, char, color in zip(rows, cols, chars, colors):
                    self.driver.move_to(r, c)
                    self.driver.write(char, color)
                
                np.copyto(self.buffer_prev.chars, self.buffer_curr.chars)
                np.copyto(self.buffer_prev.colors, self.buffer_curr.colors)
            
            # Debug Stats overlay
            processing_time = time.perf_counter() - loop_start
            real_fps = 1.0 / (time.perf_counter() - last_loop_time + 0.000001)
            last_loop_time = time.perf_counter()

            self.driver.move_to(self.config.height + 1, 0)
            status_line = (
                f"FPS: {real_fps:.1f} | "
                f"Events: {events_processed:<4} | "
                f"Diff: {len(rows):<4} px | "
                f"ProcT: {processing_time*1000:.2f}ms"
            )
            # Pad the line to clear previous text artifacts
            self.driver.write(f"{status_line:<80}")
            
            self.driver.flush()
            
            # 6. Sleep to maintain Target FPS
            elapsed = time.perf_counter() - loop_start
            sleep_t = max(0, frame_time - elapsed)
            await asyncio.sleep(sleep_t)


# --- Load Generator for Stress Testing ---

async def stress_test_loader(renderer: ForestRenderer):
    """
    Simulates 10,000 agents firing randomly.
    """
    # Wait for the renderer to start
    print("Loader: Waiting for renderer to start...")
    while not renderer._running:
        await asyncio.sleep(0.1)
    print("Loader: Renderer started. Injecting events.")

    width, height = renderer.config.width, renderer.config.height
    
    while renderer._running:
        # Simulate ~10% of agents firing per second
        # Let's be aggressive: 100 events per frame loop
        
        for _ in range(100):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            renderer.ingest(x, y, 1.0)
            
        await asyncio.sleep(0.01)

if __name__ == "__main__":
    # Self-contained run
    renderer = ForestRenderer(width=100, height=50)
    
    loop = asyncio.get_event_loop()
    try:
        # Schedule the stress loader
        loop.create_task(stress_test_loader(renderer))
        # Run the renderer
        loop.run_until_complete(renderer.start())
    except KeyboardInterrupt:
        renderer.stop()
        print("\nRenderer stopped.")