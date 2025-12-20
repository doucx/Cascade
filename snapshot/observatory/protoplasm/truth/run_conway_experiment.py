import asyncio
import numpy as np
import shutil
from typing import List

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.protoplasm.agents.conway import conway_agent
from observatory.protoplasm.truth.validator import StateValidator

# New Visualization imports
from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes

# --- Configuration ---
MAX_GENERATIONS = 200

def get_random_seed(width: int, height: int, density: float = 0.2) -> np.ndarray:
    rng = np.random.default_rng()
    noise = rng.random((height, width))
    return (noise < density).astype(np.int8)

def calculate_neighbors(x: int, y: int, width: int, height: int) -> List[int]:
    neighbors = []
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0: continue
            nx, ny = (x + dx) % width, (y + dy) % height
            neighbors.append(ny * width + nx)
    return neighbors

async def run_experiment(visualize: bool = True):
    cols, rows = shutil.get_terminal_size()
    GRID_WIDTH = min(cols // 2, 50)
    GRID_HEIGHT = min(rows - 5, 25)
    
    print(f"🚀 Starting Conway Experiment with grid {GRID_WIDTH}x{GRID_HEIGHT}...")

    # 1. Setup Shared Infrastructure
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # 2. Setup Visualizer App
    app = None
    if visualize:
        grid_view = GridView(
            width=GRID_WIDTH, 
            height=GRID_HEIGHT, 
            palette_func=Palettes.truth_diff,
            decay_per_second=0.0 # No decay for discrete states
        )
        status_bar = StatusBar({"Generation": 0, "Status": "Initializing..."})
        app = TerminalApp(grid_view, status_bar)

    # 3. Setup Validator (now accepts the app)
    validator = StateValidator(GRID_WIDTH, GRID_HEIGHT, connector, app=app)

    # 4. Setup Engine
    engine = cs.Engine(solver=cs.NativeSolver(), executor=cs.LocalExecutor(), bus=cs.MessageBus())
    @resource(name="shared_connector")
    def shared_connector_provider():
        yield connector
    engine.register(shared_connector_provider)
    
    # 5. Create Initial State & Agent Workflows
    initial_grid = get_random_seed(GRID_WIDTH, GRID_HEIGHT, density=0.25)
    agent_workflows = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            agent_id = y * GRID_WIDTH + x
            workflow = conway_agent(
                agent_id=agent_id, x=x, y=y,
                initial_state=int(initial_grid[y, x]),
                neighbor_ids=calculate_neighbors(x, y, GRID_WIDTH, GRID_HEIGHT),
                topic_base="cell", validator_topic="validator/report",
                connector=cs.inject("shared_connector"), max_generations=MAX_GENERATIONS
            )
            agent_workflows.append(workflow)

    # 6. Run
    if app: await app.start()
    validator_task = asyncio.create_task(validator.run())
    agent_tasks = [asyncio.create_task(engine.run(wf)) for wf in agent_workflows]
    all_agents_task = asyncio.gather(*agent_tasks)
    
    try:
        # Wait for all agents to complete their generations
        await all_agents_task
    except (Exception, asyncio.CancelledError) as e:
        if app: app.update_status("Status", f"ERROR: {e}")
        await asyncio.sleep(2) # Show error in UI
    finally:
        validator.stop()
        if app: app.stop()
        if not all_agents_task.done(): all_agents_task.cancel()
        
        await asyncio.gather(validator_task, all_agents_task, return_exceptions=True)
        await connector.disconnect()
        print(f"\nExperiment Finished.")

if __name__ == "__main__":
    try:
        asyncio.run(run_experiment(visualize=True))
    except KeyboardInterrupt:
        pass