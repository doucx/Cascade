import asyncio
import random
import time
from typing import Dict, Any
from asyncio import Queue
import numpy as np

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor

# New Visualization Imports
from observatory.visualization import VisualizerApp
from observatory.protoplasm.renderer.palette import Palettes


async def run_experiment(
    num_agents: int = 144, # Use a square number like 12x12
    period: float = 2.0,
    nudge: float = 0.2,
    duration_seconds: float = 60.0,
    visualize: bool = True
):
    """
    Sets up and runs the firefly synchronization experiment with Textual TUI.
    """
    grid_width = int(num_agents**0.5)
    
    if visualize:
        print(f"🔥 Starting VISUAL firefly experiment with {num_agents} agents ({grid_width}x{grid_width})...")
        print("   (UI will launch in a new screen buffer)")
        time.sleep(2)
    else:
        print(f"🔥 Starting headless firefly experiment...")

    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    monitor = ConvergenceMonitor(num_agents, period, connector)
    
    # --- Setup Queues and Visualizer App ---
    grid_queue = Queue()
    status_queue = Queue()
    app = None
    ui_task = None
    
    if visualize:
        app = VisualizerApp(
            width=grid_width,
            height=grid_width,
            palette_func=Palettes.firefly,
            data_queue=grid_queue,
            status_queue=status_queue
        )

        def monitor_callback(r_value: float):
            bar_len = 10
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            status_queue.put_nowait(f"Sync(R): {r_value:.3f} [{bar}]")

        monitor_task = asyncio.create_task(monitor.run(frequency_hz=10.0, callback=monitor_callback))

        # This task will manage the brightness decay logic for the visualizer
        async def visualizer_decay_loop():
            matrix = np.zeros((grid_width, grid_width), dtype=np.float32)
            while True:
                matrix -= 0.05 # Decay rate
                np.clip(matrix, 0.0, 1.0, out=matrix)
                # Check for new flashes to update matrix
                try:
                    while True: # Drain queue
                        x, y = grid_queue.get_nowait()
                        matrix[y, x] = 1.0
                except asyncio.QueueEmpty:
                    pass
                
                # We need a new queue for the app, or push full frames
                # Let's create a new data queue for the app
                app.data_queue.put_nowait(matrix.copy())
                await asyncio.sleep(1/30.0)

        async def on_flash_visual(topic: str, payload: Dict[str, Any]):
            aid = payload.get("agent_id")
            if aid is not None:
                x = aid % grid_width
                y = aid // grid_width
                grid_queue.put_nowait((x, y)) # Push coordinates to decay loop
        
        await connector.subscribe("firefly/flash", on_flash_visual)
        # The visualizer task now runs the decay loop
        ui_task = asyncio.create_task(app.run_async())
        visualizer_task = asyncio.create_task(visualizer_decay_loop())

    else:
        monitor_task = asyncio.create_task(monitor.run(frequency_hz=1.0))

    # --- Create & Run Agents ---
    agent_coroutines = []
    
    @resource(name="_internal_connector", scope="run")
    def shared_connector_provider():
        yield connector

    for i in range(num_agents):
        initial_phase = random.uniform(0, period)
        engine = cs.Engine(solver=cs.NativeSolver(), executor=cs.LocalExecutor(), bus=cs.MessageBus(), connector=None)
        engine.register(shared_connector_provider)

        agent_workflow = firefly_agent(
            agent_id=i, initial_phase=initial_phase, period=period, nudge=nudge,
            flash_topic="firefly/flash", listen_topic="firefly/flash",
            connector=connector, refractory_period=period * 0.2,
        )
        agent_coroutines.append(engine.run(agent_workflow))

    all_agents_task = asyncio.gather(*agent_coroutines)

    try:
        await asyncio.wait_for(all_agents_task, timeout=duration_seconds)
    except asyncio.TimeoutError:
        pass # Expected
    except Exception as e:
        print(f"Error during agent execution: {e}")
    finally:
        monitor.stop()
        if app: app.exit()
        
        # Cleanup
        all_agents_task.cancel()
        monitor_task.cancel()
        
        tasks_to_await = [all_agents_task, monitor_task]
        if ui_task:
            visualizer_task.cancel()
            tasks_to_await.append(ui_task)
            tasks_to_await.append(visualizer_task)
            
        await asyncio.gather(*tasks_to_await, return_exceptions=True)
        await connector.disconnect()
        print("Experiment finished.")

if __name__ == "__main__":
    try:
        asyncio.run(run_experiment(visualize=True))
    except Exception as e:
        print(f"Main loop error: {e}")