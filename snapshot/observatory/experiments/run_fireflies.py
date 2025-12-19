import asyncio
import random
import time

import cascade as cs
from cascade.connectors.local import LocalBusConnector

from observatory.agents.kuramoto import firefly_agent


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
    
    # All agents will run within the same engine and share the same connector
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
        
        # Create the workflow for a single agent
        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            flash_topic="firefly/flash",
            listen_topic="firefly/flash", # All agents listen and talk on the same topic
        )
        
        # Schedule the workflow to be run by the engine
        agent_tasks.append(engine.run(agent_workflow))

    # --- Run the experiment ---
    # We use asyncio.wait_for to run for a fixed duration
    try:
        main_task = asyncio.gather(*agent_tasks)
        await asyncio.wait_for(main_task, timeout=duration_seconds)
    except asyncio.TimeoutError:
        print(f"\n✅ Experiment finished after {duration_seconds}s.")
    finally:
        # Gracefully stop the engine and connector
        # This will cancel all running agent tasks
        if not main_task.done():
            main_task.cancel()
            await asyncio.gather(main_task, return_exceptions=True)
        await engine.connector.disconnect()


if __name__ == "__main__":
    # To run the experiment, execute this script from the project root:
    # python -m observatory.experiments.run_fireflies
    asyncio.run(run_experiment())