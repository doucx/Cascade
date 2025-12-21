import asyncio
import random
from typing import Dict, Any, List
import time

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
GRID_SIDE = 50  # Increased for higher density wave patterns
NUM_AGENTS = GRID_SIDE * GRID_SIDE
PERIOD = 5.0
INHIBITORY_RATIO = 0.2  # 20% of agents are inhibitory


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
    decay_duty_cycle: float = 0.3,
):
    """
    Sets up and runs the firefly synchronization experiment using a SINGLE Engine
    and a mix of Excitatory/Inhibitory agents.
    """
    grid_width = int(num_agents**0.5)
    print(
        f"🔥 Starting {'VISUAL' if visualize else 'HEADLESS'} firefly experiment with {num_agents} agents ({grid_width}x{grid_width})..."
    )
    print(f"   - Single Engine Mode: ACTIVE")
    print(f"   - Inhibitory Agents: {INHIBITORY_RATIO * 100:.0f}%")

    # 1. Initialize Shared Bus & Connector
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # --- Setup Monitor & Visualizer ---
    monitor = ConvergenceMonitor(num_agents, period, connector)

    app = None
    app_task = None

    if visualize:
        grid_view = GridView(
            width=grid_width,
            height=grid_width,
            palette_func=Palettes.firefly,
            decay_per_second=1 / (period * decay_duty_cycle),
        )
        status_bar = StatusBar(
            initial_status={"Agents": num_agents, "Sync (R)": "Initializing..."}
        )
        log_filename = f"firefly_log_{int(time.time())}.jsonl"
        aggregator = MetricsAggregator(log_filename, interval_s=1.0)
        aggregator.open()
        
        app = TerminalApp(grid_view, status_bar, aggregator=aggregator)
        aggregator_task = asyncio.create_task(aggregator.run())

        def monitor_callback(r_value: float, pulse_count: int):
            bar_len = 20
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            app.update_status("Sync", f"R={r_value:.3f} [{bar}] @ Pulse {pulse_count}")
            asyncio.create_task(aggregator.record("r_value", r_value))
            asyncio.create_task(aggregator.record("pulse", pulse_count))
            asyncio.create_task(aggregator.record("flash_count", monitor._flash_count))

        monitor_task = asyncio.create_task(
            monitor.run(frequency_hz=2.0, callback=monitor_callback)
        )

        async def on_flash_visual(topic: str, payload: Dict[str, Any]):
            aid = payload.get("agent_id")
            atype = payload.get("type", "EXCITATORY")
            if aid is not None and app:
                x = aid % grid_width
                y = aid // grid_width
                # Visual distinction: Inhibitory flashes are slightly dimmer or handled differently by palette?
                # For now, just use 1.0 brightness, palette handles fade.
                intensity = 1.0 if atype == "EXCITATORY" else 0.8
                await app.direct_update_grid_batch([(x, y, intensity)])

        await connector.subscribe("firefly/flash", on_flash_visual)
        app_task = asyncio.create_task(app.start())
    else:
        monitor_task = asyncio.create_task(monitor.run(frequency_hz=2.0))

    # --- Create Topology (DirectChannels) ---
    print("Constructing Network Topology...")
    channels = [DirectChannel(owner_id=f"agent_{i}", capacity=100) for i in range(num_agents)]

    # --- Setup Single Shared Engine ---
    # CRITICAL: We pass connector=None to prevent the Engine from managing its lifecycle.
    # The Engine will be "headless" in terms of external IO, but we will inject the connector as a resource.
    shared_engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=cs.MessageBus(),
        connector=None, 
    )

    @resource(name="_internal_connector", scope="run")
    def shared_connector_provider():
        # This provider allows agents to access the connector managed by this script
        yield connector

    shared_engine.register(shared_connector_provider)

    # --- Create Agents ---
    agent_tasks = []

    print("Generating Agent Workflows...")
    for i in range(num_agents):
        initial_phase = random.uniform(0, period)
        
        # Determine Type
        atype = "INHIBITORY" if random.random() < INHIBITORY_RATIO else "EXCITATORY"

        # Topology Lookup
        neighbor_ids = get_neighbors(i, grid_width, grid_width)
        my_neighbors = [channels[nid] for nid in neighbor_ids]
        my_channel = channels[i]

        # Inhibit stronger than excite to create contrast
        inhibition = 4.0 if atype == "INHIBITORY" else 0.0

        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            neighbors=my_neighbors,
            my_channel=my_channel,
            connector=cs.inject("_internal_connector"), # Use injection
            refractory_period=period * 0.2,
            agent_type=atype,
            inhibition_strength=inhibition
        )

        agent_tasks.append(shared_engine.run(agent_workflow))

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

        if "aggregator" in locals():
            aggregator.close()
            if "aggregator_task" in locals():
                aggregator_task.cancel()
                await asyncio.gather(aggregator_task, return_exceptions=True)

        if not all_agent_tasks.done():
            all_agent_tasks.cancel()
            await asyncio.gather(all_agent_tasks, return_exceptions=True)

        await asyncio.gather(monitor_task, return_exceptions=True)
        if app_task and not app_task.done():
            await app_task

        await connector.disconnect()


if __name__ == "__main__":
    asyncio.run(run_experiment(visualize=True))