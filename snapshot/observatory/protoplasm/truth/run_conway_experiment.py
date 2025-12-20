import asyncio
import numpy as np
import shutil

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.protoplasm.agents.conway import conway_agent
from observatory.protoplasm.truth.validator import StateValidator
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes

MAX_GENERATIONS = 500

def get_random_seed(width: int, height: int, density: float = 0.2) -> np.ndarray:
    rng = np.random.default_rng()
    return (rng.random((height, width)) < density).astype(np.int8)

def calculate_neighbors(x, y, width, height):
    neighbors = []
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0: continue
            nx, ny = (x + dx) % width, (y + dy) % height
            neighbors.append(ny * width + nx)
    return neighbors

async def run_experiment():
    # 1. Setup Renderer
    renderer = UniGridRenderer(palette_func=Palettes.conway_diff, decay_rate=0.0)
    
    GRID_WIDTH = renderer.logical_width
    GRID_HEIGHT = renderer.logical_height
    
    print(f"🚀 Starting Conway Experiment with grid {GRID_WIDTH}x{GRID_HEIGHT}...")

    # 2. Setup Shared Infrastructure
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # 3. Setup Validator, injecting the renderer
    validator = StateValidator(GRID_WIDTH, GRID_HEIGHT, connector, renderer=renderer)

    # 4. Setup Engine
    engine = cs.Engine(solver=cs.NativeSolver(), executor=cs.LocalExecutor(), bus=cs.MessageBus())
    @resource(name="shared_connector")
    def shared_connector_provider(): yield connector
    engine.register(shared_connector_provider)
    
    # 5. Create Initial State & Agent Workflows
    initial_grid = get_random_seed(GRID_WIDTH, GRID_HEIGHT, density=0.3)
    agent_workflows = [
        conway_agent(
            agent_id=(y * GRID_WIDTH + x), x=x, y=y,
            initial_state=int(initial_grid[y, x]),
            neighbor_ids=calculate_neighbors(x, y, GRID_WIDTH, GRID_HEIGHT),
            topic_base="cell", validator_topic="validator/report",
            connector=cs.inject("shared_connector"), max_generations=MAX_GENERATIONS
        )
        for y in range(GRID_HEIGHT) for x in range(GRID_WIDTH)
    ]

    # 6. Run all components concurrently
    renderer_task = asyncio.create_task(renderer.start())
    validator_task = asyncio.create_task(validator.run())
    agent_tasks = [asyncio.create_task(engine.run(wf)) for wf in agent_workflows]
    
    try:
        await asyncio.gather(*agent_tasks)
    finally:
        validator.stop()
        renderer.stop() # This is now important to call
        for t in agent_tasks: t.cancel()
        
        # Ensure all tasks are awaited to prevent warnings
        await asyncio.gather(renderer_task, validator_task, *agent_tasks, return_exceptions=True)
        await connector.disconnect()
        print(f"\nExperiment Finished.")

if __name__ == "__main__":
    try:
        asyncio.run(run_experiment())
    except KeyboardInterrupt:
        pass