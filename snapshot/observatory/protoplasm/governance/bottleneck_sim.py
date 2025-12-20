import asyncio
import random
import numpy as np
from asyncio import Queue
from typing import Any

import cascade as cs
from cascade.runtime.events import TaskBlocked, TaskExecutionStarted, TaskExecutionFinished
from cascade.spec.constraint import GlobalConstraint

# New Visualization Imports
from observatory.visualization import VisualizerApp
from observatory.protoplasm.renderer.palette import Palettes

# --- Configuration ---
NUM_AGENTS = 225  # 15x15 grid
SLOTS = 20
DURATION = 30.0

class BottleneckVisualizer:
    def __init__(self, data_queue: Queue, num_agents: int):
        self.data_queue = data_queue
        self.grid_width = int(num_agents**0.5)
        if self.grid_width * self.grid_width < num_agents:
            self.grid_width += 1
            
        self.grid_height = (num_agents + self.grid_width - 1) // self.grid_width
        self.matrix = np.zeros((self.grid_height, self.grid_width), dtype=np.float32)

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
            
            # State Mapping: 1.0 = Running, 0.5 = Waiting, 0.0 = Idle
            if task_type == "work":
                if isinstance(event, TaskExecutionStarted):
                    self.matrix[y, x] = 1.0
                elif isinstance(event, TaskBlocked):
                    self.matrix[y, x] = 0.5
                elif isinstance(event, TaskExecutionFinished):
                    self.matrix[y, x] = 0.0
                
                # Push the updated matrix to the TUI
                self.data_queue.put_nowait(self.matrix.copy())
                    
        except (IndexError, ValueError):
            pass

def make_agent_workflow(i: int):
    @cs.task(name=f"agent_{i}_work")
    async def work(val):
        await asyncio.sleep(random.uniform(0.1, 0.3))
        return val + 1

    @cs.task(name=f"agent_{i}_loop")
    def loop(val):
        return make_agent_workflow(i)

    return loop(work(0))

async def run_simulation():
    data_queue = Queue()
    status_queue = Queue() # Not used here, but required by App
    
    grid_width = int(NUM_AGENTS**0.5)
    if grid_width * grid_width < NUM_AGENTS: grid_width += 1
    grid_height = (NUM_AGENTS + grid_width - 1) // grid_width

    app = VisualizerApp(
        width=grid_width,
        height=grid_height,
        palette_func=Palettes.bottleneck,
        data_queue=data_queue,
        status_queue=status_queue
    )
    
    viz_handler = BottleneckVisualizer(data_queue, NUM_AGENTS)
    
    engine_bus = cs.MessageBus()
    engine_bus.subscribe(cs.Event, viz_handler.handle_event)
    
    engine = cs.Engine(
        solver=cs.NativeSolver(), executor=cs.LocalExecutor(), bus=engine_bus
    )
    
    engine.constraint_manager.update_constraint(
        GlobalConstraint(
            id="funnel", scope="task:agent_*_work", type="concurrency",
            params={"limit": SLOTS}
        )
    )

    print(f"🚀 Launching Bottleneck Simulation: {NUM_AGENTS} agents, {SLOTS} slots...")
    print("   (UI will launch in a new screen buffer)")
    await asyncio.sleep(2)

    agent_tasks = [
        asyncio.create_task(engine.run(make_agent_workflow(i))) for i in range(NUM_AGENTS)
    ]
    
    ui_task = asyncio.create_task(app.run_async())

    try:
        await asyncio.sleep(DURATION)
    finally:
        app.exit()
        for t in agent_tasks: t.cancel()
        await asyncio.gather(*agent_tasks, ui_task, return_exceptions=True)
        print("\nSimulation finished.")

if __name__ == "__main__":
    try:
        asyncio.run(run_simulation())
    except KeyboardInterrupt:
        pass