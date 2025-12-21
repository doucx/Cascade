import asyncio
import random
from typing import Dict, Any, List
import time
import numpy as np

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor
from observatory.monitors.aggregator import MetricsAggregator
from observatory.networking.direct_channel import DirectChannel

# Visualization
from observatory.visualization.palette import Palettes
from observatory.visualization.raw_app import RawTerminalApp as TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar

# --- Constants ---
GRID_SIDE = 50
NUM_AGENTS = GRID_SIDE * GRID_SIDE
PERIOD = 5.0


def get_neighbors(index: int, width: int, height: int) -> List[int]:
    x, y = index % width, index // width
    neighbors = []
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue
            nx, ny = (x + dx) % width, (y + dy) % height
            neighbors.append(ny * width + nx)
    return neighbors


async def run_experiment(
    num_agents: int = NUM_AGENTS,
    period: float = PERIOD,
    nudge: float = 0.2,
    duration_seconds: float = 3000.0,
    visualize: bool = True,
    decay_duty_cycle: float = 0.3,
):
    grid_width = int(num_agents**0.5)
    print(f"🔥 Starting {'VISUAL' if visualize else 'HEADLESS'} firefly experiment...")

    # --- Setup Infrastructure ---
    LocalBusConnector._reset_broker_state()
    # Connector is now ONLY for the convergence monitor
    monitor_connector = LocalBusConnector()
    await monitor_connector.connect()

    # 1. THE SHARED STATE VECTOR
    # This vector holds the normalized phase (0-1) for rendering.
    # It is written to by agents and read by the renderer.
    state_vector = np.zeros(num_agents, dtype=np.float32)

    # --- Setup Monitor & Visualizer ---
    monitor = ConvergenceMonitor(num_agents, period, monitor_connector)

    app = None
    app_task = None

    if visualize:
        grid_view = GridView(
            width=grid_width,
            height=grid_width,
            palette_func=Palettes.firefly,
            decay_per_second=1 / (period * decay_duty_cycle),
        )
        status_bar = StatusBar({"Agents": num_agents, "Sync (R)": "Initializing..."})
        log_filename = f"firefly_log_{int(time.time())}.jsonl"
        aggregator = MetricsAggregator(log_filename, interval_s=1.0)
        aggregator.open()
        print(f"📝 Logging telemetry to [bold cyan]{log_filename}[/bold cyan]")
        
        # Pass the state_vector to the app
        app = TerminalApp(grid_view, status_bar, state_vector, aggregator=aggregator)
        aggregator_task = asyncio.create_task(aggregator.run())

        def monitor_callback(r_value: float, pulse_count: int):
            bar_len = 20
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            app.update_status("Sync", f"R={r_value:.3f} [{bar}] @ Pulse {pulse_count}")
            asyncio.create_task(aggregator.record("r_value", r_value))

        monitor_task = asyncio.create_task(monitor.run(frequency_hz=2.0, callback=monitor_callback))
        
        # The monitor is the ONLY thing that needs the slow bus now
        await monitor_connector.subscribe("firefly/flash", monitor.on_flash)

        app_task = asyncio.create_task(app.start())
    else:
        monitor_task = asyncio.create_task(monitor.run(frequency_hz=2.0))

    # --- Create Topology (DirectChannels) ---
    print("Constructing Network Topology...")
    channels = [DirectChannel(owner_id=f"agent_{i}") for i in range(num_agents)]
    
    # --- Create Shared Engine ---
    engine = cs.Engine(solver=cs.NativeSolver(), executor=cs.LocalExecutor(), bus=cs.MessageBus())
    
    # The monitor connector is a resource for agents that need to publish flashes
    @resource(name="monitor_connector")
    def monitor_connector_provider():
        yield monitor_connector
    engine.register(monitor_connector_provider)
    
    # --- Create Agents ---
    agent_tasks = []
    print("Generating Agent Workflows...")
    for i in range(num_agents):
        initial_phase = random.uniform(0, period)
        neighbor_ids = get_neighbors(i, grid_width, grid_width)
        
        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            neighbors=[channels[nid] for nid in neighbor_ids],
            my_channel=channels[i],
            state_vector=state_vector, # Pass the shared vector
            refractory_period=period * 0.2,
        )
        agent_tasks.append(engine.run(agent_workflow))

    print("🚀 All agents prepared. Launching...")
    all_agent_tasks = asyncio.gather(*agent_tasks)
    try:
        await asyncio.sleep(duration_seconds)
    finally:
        monitor.stop()
        if app: app.stop()
        if "aggregator" in locals():
            aggregator.close()
            if "aggregator_task" in locals(): aggregator_task.cancel()
        
        all_agent_tasks.cancel()
        await asyncio.gather(all_agent_tasks, monitor_task, return_exceptions=True)
        if app_task and not app_task.done(): await app_task
        await monitor_connector.disconnect()

if __name__ == "__main__":
    asyncio.run(run_experiment(visualize=True))