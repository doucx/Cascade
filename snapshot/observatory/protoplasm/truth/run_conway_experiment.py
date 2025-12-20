import asyncio
import numpy as np
import shutil
import random
from typing import List

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.protoplasm.agents.conway import conway_agent
from observatory.protoplasm.truth.validator import StateValidator

# --- Configuration ---
MAX_GENERATIONS = 200
EXPERIMENT_DURATION = 60.0

def get_random_seed(width: int, height: int, density: float = 0.2) -> np.ndarray:
    """Creates a grid initialized with random noise."""
    # Create a random float matrix 0.0-1.0
    rng = np.random.default_rng()
    noise = rng.random((height, width))
    # Threshold it to get binary state
    grid = (noise < density).astype(np.int8)
    return grid

def calculate_neighbors(x: int, y: int, width: int, height: int) -> List[int]:
    """Calculates neighbor IDs for a cell in a toroidal grid."""
    neighbors = []
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue
            nx, ny = (x + dx) % width, (y + dy) % height
            neighbor_id = ny * width + nx
            neighbors.append(neighbor_id)
    return neighbors

async def run_experiment():
    """Sets up and runs the Conway's Game of Life consistency experiment."""
    
    # Auto-detect terminal size to fit the grid
    cols, rows = shutil.get_terminal_size()
    # Leave room for logs and status lines
    # Each cell is 2 chars wide, so logical width is half the terminal width
    GRID_WIDTH = cols // 2
    GRID_HEIGHT = rows - 4 # We only need 2 status lines now
    
    # Ensure reasonable bounds for performance
    GRID_WIDTH = min(GRID_WIDTH, 50) 
    GRID_HEIGHT = min(GRID_HEIGHT, 25)
    
    print(f"🚀 Starting Conway Experiment with grid {GRID_WIDTH}x{GRID_HEIGHT}...")

    # 1. Setup Shared Infrastructure
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # 2. Setup Validator with UI
    validator = StateValidator(GRID_WIDTH, GRID_HEIGHT, connector, enable_ui=True)

    # 3. Setup Engine
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=cs.MessageBus() # Silent bus
    )

    @resource(name="shared_connector")
    def shared_connector_provider():
        yield connector
    engine.register(shared_connector_provider)
    
    # 4. Create Initial State
    initial_grid = get_random_seed(GRID_WIDTH, GRID_HEIGHT, density=0.25)
    
    # 5. Build Agent Workflows
    # Optimization: Batch creation to avoid slow startup
    agent_workflows = []
    total_agents = GRID_WIDTH * GRID_HEIGHT
    
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            agent_id = y * GRID_WIDTH + x
            initial_state = int(initial_grid[y, x])
            neighbor_ids = calculate_neighbors(x, y, GRID_WIDTH, GRID_HEIGHT)
            
            workflow = conway_agent(
                agent_id=agent_id,
                x=x, y=y,
                initial_state=initial_state,
                neighbor_ids=neighbor_ids,
                topic_base="cell",
                validator_topic="validator/report",
                connector=cs.inject("shared_connector"),
                max_generations=MAX_GENERATIONS
            )
            agent_workflows.append(workflow)

    # 6. Run
    validator_task = asyncio.create_task(validator.run())
    
    # Wait a moment for validator to initialize screen
    await asyncio.sleep(0.5)
    
    agent_tasks = [asyncio.create_task(engine.run(wf)) for wf in agent_workflows]
    
    try:
        await asyncio.gather(*agent_tasks)
    except Exception as e:
        # In UI mode, we might not see the error clearly, so we log it after cleanup
        pass
    finally:
        validator.stop()
        for t in agent_tasks: t.cancel()
        await asyncio.gather(*agent_tasks, validator_task, return_exceptions=True)
        await connector.disconnect()
        print(f"\nExperiment Finished. Total Agents: {total_agents}")

if __name__ == "__main__":
    try:
        asyncio.run(run_experiment())
    except KeyboardInterrupt:
        pass