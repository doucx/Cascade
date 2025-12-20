import asyncio
import random
import time
import shutil
import math
from typing import Any, Dict

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor
from observatory.visualization.grid_renderer import GridRenderer

# --- Visualizer Adapter ---

class FireflyVisualizer:
    def __init__(self, renderer: GridRenderer, num_agents: int):
        self.renderer = renderer
        # Calculate grid dimensions to map agent_id -> (x, y)
        # We aim for a roughly square grid
        self.cols = int(math.ceil(math.sqrt(num_agents)))
        
    def get_coords(self, agent_id: int):
        x = agent_id % self.cols
        y = agent_id // self.cols
        return x, y

    async def on_flash(self, topic: str, payload: Dict[str, Any]):
        """
        Adapts the bus event to a renderer ingestion.
        """
        agent_id = payload.get("agent_id")
        if agent_id is not None:
            x, y = self.get_coords(agent_id)
            # Flash intensity 1.0
            self.renderer.ingest(x, y, 1.0)


async def run_experiment(
    num_agents: int = 100,
    period: float = 2.0,
    nudge: float = 0.2,
    duration_seconds: float = 30.0,
    visualize: bool = True
):
    """
    Sets up and runs the firefly synchronization experiment.
    """
    print(f"🔥 Starting firefly experiment with {num_agents} agents...")

    # 1. Initialize Infrastructure
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # 2. Setup Visualization (if enabled)
    renderer = None
    viz_adapter = None
    monitor = None
    
    if visualize:
        cols, rows = shutil.get_terminal_size()
        render_height = max(10, rows - 4)
        renderer = GridRenderer(width=cols, height=render_height)
        viz_adapter = FireflyVisualizer(renderer, num_agents)
        
        # Subscribe visualizer to flashes
        await connector.subscribe("firefly/flash", viz_adapter.on_flash)
    
    # 3. Setup Monitor
    monitor = ConvergenceMonitor(num_agents, period, connector)
    
    if visualize and renderer:
        # Hook monitor status into renderer
        renderer.set_status_callback(lambda: f"SYNC: {monitor._calculate_order_parameter():.4f}")
        # We don't run the monitor's loop because we don't want it printing to stdout
        # Instead, we just let it passively collect data via its subscription
        # BUT, ConvergenceMonitor.run() handles the subscription. 
        # So we need to call monitor.start_passive() or similar.
        # For now, let's manually subscribe the monitor's callback
        await connector.subscribe("firefly/flash", monitor.on_flash)
    else:
        # Run monitor in active mode (printing to stdout)
        asyncio.create_task(monitor.run())

    # --- Create the population of firefly agents ---
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

    # --- Run the experiment ---
    try:
        renderer_task = None
        if visualize and renderer:
            renderer_task = asyncio.create_task(renderer.start())
        else:
             print(f"\n⏳ Running for {duration_seconds} seconds...")

        # Wait for duration
        all_agents = asyncio.gather(*agent_tasks)
        try:
            await asyncio.wait_for(all_agents, timeout=duration_seconds)
        except asyncio.TimeoutError:
            pass
            
    finally:
        # Graceful Shutdown
        if visualize and renderer:
            renderer.stop()
            if renderer_task:
                await renderer_task
        
        if monitor:
            monitor.stop()

        if not all_agents.done():
            all_agents.cancel()
            await asyncio.gather(all_agents, return_exceptions=True)
        
        await connector.disconnect()
        
        if visualize:
             print(f"\n✅ Experiment finished. Final Sync: {monitor._calculate_order_parameter():.4f}")


if __name__ == "__main__":
    # Adjust params for a good visual show
    # 400 agents fits nicely in a 20x20 grid
    asyncio.run(run_experiment(num_agents=400, duration_seconds=60.0))