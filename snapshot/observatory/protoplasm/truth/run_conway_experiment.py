import asyncio
import numpy as np
from typing import List

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.protoplasm.agents.conway import conway_agent
from observatory.protoplasm.truth.validator import StateValidator

# --- Experiment Configuration ---
GRID_WIDTH = 20
GRID_HEIGHT = 20
MAX_GENERATIONS = 50
EXPERIMENT_DURATION = 30.0  # Seconds

def get_glider_seed(width: int, height: int) -> np.ndarray:
    """Creates a simple Glider pattern on the grid."""
    grid = np.zeros((height, width), dtype=np.int8)
    #   .X.
    #   ..X
    #   XXX
    grid[1, 2] = 1
    grid[2, 3] = 1
    grid[3, 1:4] = 1
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
    print("🚀 Starting Conway's Game of Life Experiment...")
    print(f"   Grid: {GRID_WIDTH}x{GRID_HEIGHT}, Agents: {GRID_WIDTH * GRID_HEIGHT}, Generations: {MAX_GENERATIONS}")

    # 1. Setup Shared Infrastructure
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # 2. Setup Validator
    validator = StateValidator(GRID_WIDTH, GRID_HEIGHT, connector)

    # 3. Setup Engine (Single-Engine, Multi-Tenant)
    # We create one powerful engine to run all agents.
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=cs.MessageBus() # Silent bus for clean output
    )

    # The conway_agent needs a connector. We inject it as a resource.
    @resource(name="shared_connector")
    def shared_connector_provider():
        yield connector
    engine.register(shared_connector_provider)
    
    # 4. Create Initial State and Agent Workflows
    initial_grid = get_glider_seed(GRID_WIDTH, GRID_HEIGHT)
    agent_workflows = []

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

    # 5. Run the Simulation
    validator_task = asyncio.create_task(validator.run())
    
    print(f"\nLaunching {len(agent_workflows)} agents on a single engine...")
    # Launch all agents concurrently on the same engine
    agent_tasks = [asyncio.create_task(engine.run(wf)) for wf in agent_workflows]
    all_agents_task = asyncio.gather(*agent_tasks)
    
    try:
        # Wait for all agents to finish or for the timeout
        await asyncio.wait_for(all_agents_task, timeout=EXPERIMENT_DURATION)
        print("\n✅ All agents completed their lifecycle.")
    except asyncio.TimeoutError:
        print(f"\n⚠️  Experiment timed out after {EXPERIMENT_DURATION}s.")
    except Exception as e:
        print(f"\n❌ Experiment failed with an unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 6. Cleanup
        print("--- Shutting down ---")
        validator.stop()
        if not all_agents_task.done():
            all_agents_task.cancel()
            await asyncio.gather(all_agents_task, validator_task, return_exceptions=True)
        else:
            await asyncio.gather(validator_task, return_exceptions=True)
            
        await connector.disconnect()
        print("Shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(run_experiment())
    except KeyboardInterrupt:
        print("\nExperiment interrupted by user.")