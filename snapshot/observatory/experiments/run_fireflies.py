import asyncio
import random
import time
from typing import Dict, Any

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor

# Visualization
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes

async def run_experiment(
    num_agents: int = 400, # Increased for better visual field (20x20)
    period: float = 2.0,
    nudge: float = 0.2,
    duration_seconds: float = 30.0,
    visualize: bool = True
):
    """
    Sets up and runs the firefly synchronization experiment.
    """
    if visualize:
        print(f"🔥 Starting VISUAL firefly experiment with {num_agents} agents...")
    else:
        print(f"🔥 Starting headless firefly experiment...")

    # 1. Initialize Shared Bus
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # --- Setup Monitor & Visualizer ---
    monitor = ConvergenceMonitor(num_agents, period, connector)
    monitor_task = asyncio.create_task(monitor.run(frequency_hz=10.0))

    renderer = None
    renderer_task = None
    
    if visualize:
        # Define visualizer mapping
        grid_width = int(num_agents**0.5)
        # Handle non-perfect squares
        if grid_width * grid_width < num_agents: grid_width += 1
        
        renderer = UniGridRenderer(width=grid_width, height=grid_width, palette_func=Palettes.firefly, decay_rate=0.1)
        
        async def on_flash_visual(topic: str, payload: Dict[str, Any]):
            aid = payload.get("agent_id")
            if aid is not None:
                x = aid % grid_width
                y = aid // grid_width
                # Ingest a "Flash" (1.0 brightness)
                renderer.ingest(x, y, 1.0)
        
        # Subscribe visualizer to bus
        await connector.subscribe("firefly/flash", on_flash_visual)
        renderer_task = asyncio.create_task(renderer.start())

    # --- Create Agents ---
    agent_tasks = []
    
    @resource(name="_internal_connector", scope="run")
    def shared_connector_provider():
        yield connector

    for i in range(num_agents):
        initial_phase = random.uniform(0, period)
        
        engine = cs.Engine(
            solver=cs.NativeSolver(),
            executor=cs.LocalExecutor(),
            bus=cs.MessageBus(),
            connector=None, 
        )
        engine.register(shared_connector_provider)

        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            flash_topic="firefly/flash",
            listen_topic="firefly/flash",
            connector=connector,
            refractory_period=period * 0.2,
        )
        
        agent_tasks.append(engine.run(agent_workflow))

    # --- Run ---
    all_tasks = asyncio.gather(*agent_tasks)
    try:
        # If visualizing, wait for duration
        await asyncio.sleep(duration_seconds)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        monitor.stop()
        if renderer: renderer.stop()
        
        if not all_tasks.done():
            all_tasks.cancel()
            await asyncio.gather(all_tasks, return_exceptions=True)
            
        await asyncio.gather(monitor_task, return_exceptions=True)
        if renderer_task:
            if not renderer_task.done(): renderer_task.cancel()
            await renderer_task
        
        await connector.disconnect()

if __name__ == "__main__":
    asyncio.run(run_experiment(visualize=True))