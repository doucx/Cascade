import asyncio
import random
import shutil
import time
from typing import Any

import cascade as cs
from cascade.runtime.events import TaskBlocked, TaskExecutionStarted, TaskExecutionFinished
from cascade.spec.constraint import GlobalConstraint
from observatory.protoplasm.renderer.visualizer_proto import ForestRenderer

# --- Configuration ---
NUM_AGENTS = 500
SLOTS = 20
DURATION = 10.0

# --- Visualizer Logic ---

class BottleneckVisualizer:
    def __init__(self, renderer: ForestRenderer, num_agents: int):
        self.renderer = renderer
        self.grid_width = int(num_agents**0.5) + 1
        
    def get_coords(self, agent_id: int):
        return (agent_id % self.grid_width, agent_id // self.grid_width)

    def handle_event(self, event: Any):
        # We expect task names like "agent_42_work"
        if not hasattr(event, "task_name") or not event.task_name.startswith("agent_"):
            return
            
        try:
            # Format: "agent_{id}_work" or "agent_{id}_loop"
            parts = event.task_name.split("_")
            if len(parts) < 3: return
            agent_id = int(parts[1])
            task_type = parts[2]
            
            x, y = self.get_coords(agent_id)
            
            if task_type == "work":
                if isinstance(event, TaskExecutionStarted):
                    # Acquired Slot = Bright White
                    self.renderer.ingest(x, y, 1.0)
                elif isinstance(event, TaskBlocked):
                    # Waiting for Slot = Mid Cyan
                    self.renderer.ingest(x, y, 0.5)
                elif isinstance(event, TaskExecutionFinished):
                    # Released Slot = Dim
                    self.renderer.ingest(x, y, 0.0)
                    
        except (IndexError, ValueError):
            pass

# --- Agent Definition ---

def make_agent_workflow(i: int):
    # This task simulates the resource-intensive work
    # It will be named "agent_{i}_work" so it matches the constraint "task:agent_*_work"
    @cs.task(name=f"agent_{i}_work")
    async def work(val):
        # Hold the slot for a bit
        await asyncio.sleep(random.uniform(0.1, 0.3))
        return val + 1

    # This task is the recursive driver, it is NOT constrained
    @cs.task(name=f"agent_{i}_loop")
    def loop(val):
        return make_agent_workflow(i)

    return loop(work(0))

# --- Main ---

async def run_simulation():
    # 1. Setup Renderer
    cols, rows = shutil.get_terminal_size()
    render_height = max(10, rows - 4)
    renderer = ForestRenderer(width=cols, height=render_height)
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
    # "task:agent_*_work" matches our work tasks
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
    # We launch them all on the SAME engine instance
    print(f"Launching {NUM_AGENTS} agents...")
    tasks = []
    for i in range(NUM_AGENTS):
        # We use asyncio.create_task to fire them off
        tasks.append(asyncio.create_task(engine.run(make_agent_workflow(i))))
        
    # 5. Run Visualization
    try:
        renderer_task = asyncio.create_task(renderer.start())
        
        # Let it run for DURATION
        await asyncio.sleep(DURATION)
        
    finally:
        renderer.stop()
        # Cancel all agents
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