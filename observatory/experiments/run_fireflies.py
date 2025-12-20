import asyncio
import random
from typing import Dict, Any

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor

# Visualization
from observatory.visualization.palette import Palettes
from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar


async def run_experiment(
    num_agents: int = 15**2,
    period: float = 3.0,
    nudge: float = 0.2,
    duration_seconds: float = 3000.0,
    visualize: bool = True,
    decay_duty_cycle: float = 0.5,
):
    """
    Sets up and runs the firefly synchronization experiment.
    """
    print(
        f"🔥 Starting {'VISUAL' if visualize else 'HEADLESS'} firefly experiment with {num_agents} agents..."
    )

    # 1. Initialize Shared Bus
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # --- Setup Monitor & Visualizer ---
    monitor = ConvergenceMonitor(num_agents, period, connector)

    app = None
    app_task = None

    if visualize:
        grid_width = int(num_agents**0.5)
        if grid_width * grid_width < num_agents:
            grid_width += 1

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

        # 2. Bridge Monitor -> Status Bar
        def monitor_callback(r_value: float):
            bar_len = 20
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            app.update_status("Sync (R)", f"{r_value:.3f} [{bar}]")

        monitor_task = asyncio.create_task(
            monitor.run(frequency_hz=10.0, callback=monitor_callback)
        )

        # 3. Bridge Agent Flashes -> Grid
        async def on_flash_visual(topic: str, payload: Dict[str, Any]):
            aid = payload.get("agent_id")
            if aid is not None and app:
                x = aid % grid_width
                y = aid // grid_width
                app.ingest_grid(x, y, 1.0)

        await connector.subscribe("firefly/flash", on_flash_visual)
        app_task = asyncio.create_task(app.start())
    else:
        # Headless mode: Monitor prints to stdout
        monitor_task = asyncio.create_task(monitor.run(frequency_hz=10.0))

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
    all_agent_tasks = asyncio.gather(*agent_tasks)
    try:
        await asyncio.sleep(duration_seconds)
    except (Exception, asyncio.CancelledError) as e:
        print(f"Experiment interrupted or failed: {e}")
    finally:
        monitor.stop()
        if app:
            app.stop()

        if not all_agent_tasks.done():
            all_agent_tasks.cancel()
            await asyncio.gather(all_agent_tasks, return_exceptions=True)

        await asyncio.gather(monitor_task, return_exceptions=True)
        if app_task and not app_task.done():
            await app_task

        await connector.disconnect()


if __name__ == "__main__":
    asyncio.run(run_experiment(visualize=True))
