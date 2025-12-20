import asyncio
import random
from typing import Dict, Any, List
import time

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor
from observatory.monitors.logger import JsonFileLogger

# Visualization
from observatory.visualization.palette import Palettes
from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar

# --- Constants ---
GRID_SIDE = 30
NUM_AGENTS = GRID_SIDE * GRID_SIDE  # 2500
PERIOD = 5.0  # Slowed down to allow CPU to catch up with 2500 agents


def get_neighbors(index: int, width: int, height: int) -> List[int]:
    """Calculate 8-neighbors (Moore neighborhood) with wrap-around (toroidal)."""
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
    decay_duty_cycle: float = 0.5,
):
    """
    Sets up and runs the firefly synchronization experiment.
    """
    grid_width = int(num_agents**0.5)
    print(
        f"🔥 Starting {'VISUAL' if visualize else 'HEADLESS'} firefly experiment with {num_agents} agents ({grid_width}x{grid_width})..."
    )

    # 1. Initialize Shared Bus
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # --- Setup Monitor & Visualizer ---
    # Monitor now needs to handle many more agents.
    monitor = ConvergenceMonitor(num_agents, period, connector)

    app = None
    app_task = None

    if visualize:
        # 1. Create visualization components
        # A decay_per_second of 5.0 means a flash will fade in 1/5 = 0.2 seconds.
        grid_view = GridView(
            width=grid_width,
            height=grid_width,
            palette_func=Palettes.firefly,
            decay_per_second=1 / (period * decay_duty_cycle),
        )
        status_bar = StatusBar(
            initial_status={"Agents": num_agents, "Sync (R)": "Initializing..."}
        )
        app = TerminalApp(grid_view, status_bar)
        
        # --- Setup Logger ---
        log_filename = f"firefly_log_{int(time.time())}.jsonl"
        logger = JsonFileLogger(log_filename)
        logger.open()
        print(f"📝 Logging telemetry to [bold cyan]{log_filename}[/bold cyan]")


        # 2. Bridge Monitor -> Status Bar & Logger
        def monitor_callback(r_value: float, pulse_count: int):
            # UI Update
            bar_len = 20
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            app.update_status("Sync", f"R={r_value:.3f} [{bar}] @ Pulse {pulse_count}")
            
            # Data Logging
            logger.log({"r_value": r_value, "pulse": pulse_count, "flash_count": monitor._flash_count})


        monitor_task = asyncio.create_task(
            # Reduce monitor frequency to reduce CPU load
            monitor.run(frequency_hz=2.0, callback=monitor_callback)
        )

        # 3. Bridge Agent Flashes -> Grid
        # Agents now also publish to "firefly/flash" for the visualizer/monitor
        async def on_flash_visual(topic: str, payload: Dict[str, Any]):
            aid = payload.get("agent_id")
            if aid is not None and app:
                x = aid % grid_width
                y = aid // grid_width
                # Use Fast Path (Direct Update) to avoid queue bottlenecks
                await app.direct_update_grid(x, y, 1.0)

        await connector.subscribe("firefly/flash", on_flash_visual)
        app_task = asyncio.create_task(app.start())
    else:
        # Headless mode: Monitor prints to stdout
        monitor_task = asyncio.create_task(monitor.run(frequency_hz=2.0))

    # --- Create Agents ---
    agent_tasks = []

    @resource(name="_internal_connector", scope="run")
    def shared_connector_provider():
        yield connector

    # Batch creation to avoid freezing UI loop
    print("Generating Agent Workflows...")
    for i in range(num_agents):
        initial_phase = random.uniform(0, period)
        
        neighbor_ids = get_neighbors(i, grid_width, grid_width)
        neighbor_inboxes = [f"firefly/{nid}/inbox" for nid in neighbor_ids]
        my_inbox = f"firefly/{i}/inbox"

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
            neighbor_inboxes=neighbor_inboxes,
            my_inbox=my_inbox,
            connector=connector,
            refractory_period=period * 0.2,
        )

        agent_tasks.append(engine.run(agent_workflow))
        
        # Yield every 500 agents to keep UI responsive during setup
        if i > 0 and i % 500 == 0:
            print(f"   ... {i} agents prepared.")
            await asyncio.sleep(0)

    print("🚀 All agents prepared. Launching...")
    
    # --- Run ---
    all_agent_tasks = asyncio.gather(*agent_tasks)
    try:
        await asyncio.sleep(duration_seconds)
    except (Exception, asyncio.CancelledError) as e:
        print(f"Experiment interrupted or failed: {e}")
    finally:
        monitor.stop()
        if app:
            app.stop()
        if logger:
            logger.close()

        if not all_agent_tasks.done():
            all_agent_tasks.cancel()
            await asyncio.gather(all_agent_tasks, return_exceptions=True)

        await asyncio.gather(monitor_task, return_exceptions=True)
        if app_task and not app_task.done():
            await app_task

        await connector.disconnect()


if __name__ == "__main__":
    asyncio.run(run_experiment(visualize=True))
