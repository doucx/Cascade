import asyncio
import random
import shutil
import time
from typing import Any

import cascade as cs
from cascade.runtime.events import TaskBlocked, TaskExecutionStarted, TaskExecutionFinished
from cascade.spec.constraint import GlobalConstraint

# New Renderer Imports
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes

# --- Configuration ---
NUM_AGENTS = 500
SLOTS = 20
DURATION = 15.0

# --- Visualizer Logic ---

class BottleneckVisualizer:
    def __init__(self, renderer: UniGridRenderer, num_agents: int):
        self.renderer = renderer
        # Ensure grid is roughly square logic
        self.grid_width = int(num_agents**0.5) + 1
        
    def get_coords(self, agent_id: int):
        return (agent_id % self.grid_width, agent_id // self.grid_width)

    def handle_event(self, event: Any):
        if not hasattr(event, "task_name") or not event.task_name.startswith("agent_"):
            return
            
        try:
            parts = event.task_name.split("_")
            if len(parts) < 3: return
            agent_id = int(parts[1])
            task_type = parts[2]
            
            x, y = self.get_coords(agent_id)
            
            # Map Events to States for Palette
            # 1.0 = Running (White)
            # 0.5 = Waiting (Cyan)
            # 0.0 = Idle (Dim)
            
            if task_type == "work":
                if isinstance(event, TaskExecutionStarted):
                    self.renderer.ingest(x, y, 1.0)
                elif isinstance(event, TaskBlocked):
                    self.renderer.ingest(x, y, 0.5)
                elif isinstance(event, TaskExecutionFinished):
                    self.renderer.ingest(x, y, 0.0)
                    
        except (IndexError, ValueError):
            pass

# --- Agent Definition ---

def make_agent_workflow(i: int):
    @cs.task(name=f"agent_{i}_work")
    async def work(val):
        await asyncio.sleep(random.uniform(0.1, 0.3))
        return val + 1

    @cs.task(name=f"agent_{i}_loop")
    def loop(val):
        return make_agent_workflow(i)

    return loop(work(0))

# --- Main ---

async def run_simulation():
    # 1. Setup New Renderer
    # Note: We rely on auto-sizing, passing only palette
    renderer = UniGridRenderer(palette_func=Palettes.bottleneck, decay_rate=0.0)
    
    viz = BottleneckVisualizer(renderer, NUM_AGENTS)
    
    # 2. Setup Engine
    engine_bus = cs.MessageBus()
    engine_bus.subscribe(cs.Event, viz.handle_event)
    
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=engine_bus
    )
    
    # 3. Apply Constraint
    print(f"Applying constraint: Max {SLOTS} concurrent 'work' tasks...")
    engine.constraint_manager.update_constraint(
        GlobalConstraint(
            id="funnel",
            scope="task:agent_*_work",
            type="concurrency",
            params={"limit": SLOTS}
        )
    )

    # 4. Launch Agents
    print(f"Launching {NUM_AGENTS} agents...")
    tasks = []
    for i in range(NUM_AGENTS):
        tasks.append(asyncio.create_task(engine.run(make_agent_workflow(i))))
        
    # 5. Run Visualization
    try:
        renderer_task = asyncio.create_task(renderer.start())
        await asyncio.sleep(DURATION)
    finally:
        renderer.stop()
        for t in tasks: t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if not renderer_task.done():
            renderer_task.cancel()
            await renderer_task

if __name__ == "__main__":
    try:
        asyncio.run(run_simulation())
    except KeyboardInterrupt:
        pass