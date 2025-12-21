import asyncio
import random
import time
import math
import multiprocessing as mp
from typing import Dict, Any, List, Optional
import typer

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource
from cascade.runtime.resource_manager import ResourceManager

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor
from observatory.monitors.aggregator import MetricsAggregator
from observatory.networking.direct_channel import DirectChannel
from observatory.networking.ipc import IpcUplinkConnector

# Visualization
from observatory.visualization.palette import Palettes
from observatory.visualization.raw_app import RawTerminalApp as TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar

# --- Constants ---
GRID_SIDE = 30
NUM_AGENTS = GRID_SIDE * GRID_SIDE  # 900
PERIOD = 5.0

app = typer.Typer()


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


# --- Worker Logic ---

def worker_main(
    worker_id: int,
    agent_indices: List[int],
    total_agents: int,
    uplink_queue: mp.Queue,
    concurrency_limit: Optional[int],
    grid_width: int,
    grid_height: int,
    period: float,
    nudge: float,
):
    """
    The entry point for a worker process.
    Runs a subset of agents (Sharding).
    """
    # Create a new event loop for this process
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run_worker():
        # 1. Setup Uplink
        connector = IpcUplinkConnector(uplink_queue)
        await connector.connect()

        # 2. Setup Resources
        # We partition the global limit proportionally among workers.
        local_limit = None
        if concurrency_limit:
            # Formula: (Global Limit * Agents in this Worker) / Total Agents
            # Using math.ceil to ensure we don't end up with 0 due to rounding
            local_limit = math.ceil(concurrency_limit * (len(agent_indices) / total_agents))
        
        resource_manager = None
        if local_limit:
            resource_manager = ResourceManager(capacity={"cpu_slot": local_limit})

        # 3. Setup Topology (Local Island)
        # We only create channels for agents assigned to THIS worker.
        # Cross-process neighbors are currently severed (Open Boundary).
        local_channels = {i: DirectChannel(f"agent_{i}") for i in agent_indices}

        # 4. Create Agents
        agent_tasks = []

        @resource(name="_internal_connector", scope="run")
        def shared_connector_provider():
            yield connector

        for i in agent_indices:
            initial_phase = random.uniform(0, period)
            
            # Resolve neighbors
            # If a neighbor is not in local_channels, we skip it (Partitioned Grid)
            potential_neighbors = get_neighbors(i, grid_width, grid_height)
            my_neighbors = []
            for nid in potential_neighbors:
                if nid in local_channels:
                    my_neighbors.append(local_channels[nid])
            
            my_channel = local_channels[i]

            engine = cs.Engine(
                solver=cs.NativeSolver(),
                executor=cs.LocalExecutor(),
                bus=cs.MessageBus(),
                connector=None,
                resource_manager=resource_manager
            )
            engine.register(shared_connector_provider)

            workflow = firefly_agent(
                agent_id=i,
                initial_phase=initial_phase,
                period=period,
                nudge=nudge,
                neighbors=my_neighbors,
                my_channel=my_channel,
                connector=connector,
                refractory_period=period * 0.2,
            )

            if local_limit:
                workflow = workflow.with_constraints(cpu_slot=1)

            agent_tasks.append(engine.run(workflow, use_vm=True))
        
        # 5. Run Forever
        try:
            await asyncio.gather(*agent_tasks)
        except asyncio.CancelledError:
            pass

    try:
        loop.run_until_complete(_run_worker())
    except KeyboardInterrupt:
        pass


# --- Orchestrator Logic ---

async def run_orchestrator(
    num_agents: int,
    grid_width: int,
    workers: int,
    concurrency_limit: Optional[int],
    visualize: bool,
    period: float,
    nudge: float,
    duration_seconds: float,
    decay_duty_cycle: float,
):
    print(f"🔥 Starting MULTI-CORE Firefly Experiment")
    print(f"   - Agents: {num_agents} ({grid_width}x{grid_width})")
    print(f"   - Workers: {workers}")
    print(f"   - Mode: Partitioned Islands (Cross-process links severed)")

    # 1. Setup Telemetry Hub (Main Process LocalBus)
    LocalBusConnector._reset_broker_state()
    main_connector = LocalBusConnector()
    await main_connector.connect()

    # 2. Setup Monitor & Visualizer (Same as before!)
    monitor = ConvergenceMonitor(num_agents, period, main_connector)
    app = None
    app_task = None
    aggregator = None
    aggregator_task = None

    if visualize:
        grid_view = GridView(
            width=grid_width,
            height=grid_width,
            palette_func=Palettes.firefly,
            decay_per_second=1 / (period * decay_duty_cycle),
        )
        status_bar = StatusBar(initial_status={"Agents": num_agents, "Workers": workers, "Period": period, "Nudge": nudge})
        
        log_filename = f"firefly_mp_log_{int(time.time())}.jsonl"
        aggregator = MetricsAggregator(log_filename, interval_s=1.0)
        aggregator.open()
        
        app = TerminalApp(grid_view, status_bar, aggregator=aggregator)
        aggregator_task = asyncio.create_task(aggregator.run())

        # Bridge Monitor -> UI
        def monitor_callback(r_value: float, pulse_count: int):
            bar_len = 20
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            app.update_status("Sync", f"R={r_value:.3f} [{bar}]")
            app.update_status("Pulse", pulse_count)
            # Expose raw flash count to make the relationship clear
            app.update_status("Flashes", f"{monitor._flash_count:,}")
            
            asyncio.create_task(aggregator.record("r_value", r_value))

        monitor_task = asyncio.create_task(
            monitor.run(frequency_hz=2.0, callback=monitor_callback)
        )

        # Bridge Flash -> UI
        async def on_flash_visual(topic: str, payload: Dict[str, Any]):
            aid = payload.get("agent_id")
            if aid is not None and app:
                x = aid % grid_width
                y = aid // grid_width
                await app.direct_update_grid_batch([(x, y, 1.0)])

        await main_connector.subscribe("firefly/flash", on_flash_visual)
        app_task = asyncio.create_task(app.start())
    else:
        monitor_task = asyncio.create_task(monitor.run(frequency_hz=2.0))

    # 3. Spawn Workers
    uplink_queue = mp.Queue()
    all_indices = list(range(num_agents))
    chunk_size = math.ceil(num_agents / workers)
    
    processes = []
    for w_id in range(workers):
        start = w_id * chunk_size
        end = min(start + chunk_size, num_agents)
        indices = all_indices[start:end]
        
        if not indices:
            continue

        p = mp.Process(
            target=worker_main,
            args=(
                w_id, indices, num_agents, uplink_queue, concurrency_limit,
                grid_width, grid_width, period, nudge # grid_height is same as grid_width for square
            )
        )
        p.start()
        processes.append(p)

    # 4. Telemetry Pump Loop
    # Reads from MP Queue and replays to LocalBus for the Monitor/Visualizer
    print("🚀 Workers launched. Bridging telemetry...")
    
    # 4. Telemetry Pump Loop & Experiment Timer
    print("🚀 Workers launched. Bridging telemetry...")
    
    start_time = time.time()
    try:
        while time.time() - start_time < duration_seconds:
            if not any(p.is_alive() for p in processes):
                print("🛑 All workers terminated prematurely.")
                break
            try:
                while not uplink_queue.empty():
                    topic, payload = uplink_queue.get_nowait()
                    await main_connector.publish(topic, payload)
                
                await asyncio.sleep(0.01)
            except Exception:
                await asyncio.sleep(0.01)

    except asyncio.CancelledError:
        pass
    finally:
        print("\nShutting down...")
        for p in processes:
            p.terminate()
        
        if app: app.stop()
        if aggregator: aggregator.close()
        
        # Cleanup tasks
        tasks = [t for t in [app_task, monitor_task, aggregator_task] if t]
        for t in tasks: t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@app.command()
def main(
    visualize: bool = typer.Option(True, help="Enable visualizer UI"),
    grid_side: int = typer.Option(GRID_SIDE, help="Side length of the square agent grid."),
    workers: int = typer.Option(1, help="Number of worker processes"),
    limit: Optional[int] = typer.Option(None, help="Global concurrency limit (per process)"),
    period: float = typer.Option(PERIOD, help="Oscillation period for agents."),
    nudge: float = typer.Option(0.2, help="Coupling strength (phase nudge)."),
    duration: float = typer.Option(300.0, help="Duration of the experiment in seconds."),
    decay_duty_cycle: float = typer.Option(0.3, help="Flash visibility duration as a fraction of period."),
):
    num_agents = grid_side * grid_side
    asyncio.run(run_orchestrator(
        num_agents=num_agents,
        grid_width=grid_side,
        workers=workers,
        concurrency_limit=limit,
        visualize=visualize,
        period=period,
        nudge=nudge,
        duration_seconds=duration,
        decay_duty_cycle=decay_duty_cycle,
    ))

if __name__ == "__main__":
    app()
