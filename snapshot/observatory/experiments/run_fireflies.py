import asyncio
import random
import time

import cascade as cs
from cascade.connectors.local import LocalBusConnector

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor


async def run_experiment(
    num_agents: int = 50,
    period: float = 10.0,
    nudge: float = 0.5,
    duration_seconds: float = 60.0,
):
    """
    Sets up and runs the firefly synchronization experiment.
    """
    print(f"🔥 Starting firefly experiment with {num_agents} agents for {duration_seconds}s...")

    # Ensure a clean slate for each experiment run
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    
    # --- Setup Monitor ---
    monitor = ConvergenceMonitor(num_agents, period, connector)
    monitor_task = asyncio.create_task(monitor.run())

    # --- Setup Engine for Agents ---
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=cs.MessageBus(),
        connector=connector,
    )

    # --- Create the population of firefly agents ---
    agent_tasks = []
    for i in range(num_agents):
        # Each firefly starts with a random phase in its cycle
        initial_phase = random.uniform(0, period)
        
        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            flash_topic="firefly/flash",
            listen_topic="firefly/flash", # All agents listen and talk on the same topic
        )
        agent_tasks.append(engine.run(agent_workflow))

    # --- Run the experiment ---
    all_tasks = asyncio.gather(*agent_tasks)
    try:
        print(f"\n⏳ Running agents and monitor for {duration_seconds} seconds...")
        start_time = time.time()
        await asyncio.wait_for(all_tasks, timeout=duration_seconds)
    except asyncio.TimeoutError:
        end_time = time.time()
        print(f"\n✅ Experiment finished after {end_time - start_time:.2f}s.")
    finally:
        # Gracefully stop everything
        monitor.stop()
        if not all_tasks.done():
            all_tasks.cancel()
            # Await both agents and monitor to ensure clean shutdown
            await asyncio.gather(all_tasks, monitor_task, return_exceptions=True)
        else:
             await asyncio.gather(monitor_task, return_exceptions=True)
        
        await engine.connector.disconnect()


if __name__ == "__main__":
    # To run the experiment, execute this script from the project root:
    # python -m observatory.experiments.run_fireflies
    asyncio.run(run_experiment())