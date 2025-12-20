import asyncio
import random
from typing import Any

import cascade as cs
from cascade.runtime.events import (
    TaskBlocked,
    TaskExecutionStarted,
    TaskExecutionFinished,
)
from cascade.spec.constraint import GlobalConstraint

# New Renderer Imports
from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes

# --- Configuration ---
NUM_AGENTS = 500
SLOTS = 20
DURATION = 15.0

# --- Agent Definition ---


def make_agent_workflow(i: int):
    @cs.task(name=f"agent_{i}_work")
    async def work(val):
        await asyncio.sleep(random.uniform(0.1, 0.3))
        return val + 1

    @cs.task(name=f"agent_{i}_loop")
    def loop(val):
        return make_agent_workflow(i)

    return loop(work(0))


# --- Main ---


async def run_simulation():
    # 1. Setup New Renderer
    grid_width = int(NUM_AGENTS**0.5) + 1
    grid_view = GridView(
        width=grid_width,
        height=grid_width,
        palette_func=Palettes.bottleneck,
        decay_per_second=0.0,  # No decay, states are discrete
    )
    status_bar = StatusBar(
        {"Agents": NUM_AGENTS, "Slots": SLOTS, "Blocked": 0, "Running": 0}
    )
    app = TerminalApp(grid_view, status_bar)

    # 2. Setup Event Handling
    blocked_count = 0
    running_count = 0

    def get_coords(agent_id: int):
        return (agent_id % grid_width, agent_id // grid_width)

    def handle_event(event: Any):
        nonlocal blocked_count, running_count
        if not hasattr(event, "task_name") or not event.task_name.startswith("agent_"):
            return

        try:
            parts = event.task_name.split("_")
            if len(parts) < 3:
                return
            agent_id = int(parts[1])
            task_type = parts[2]

            x, y = get_coords(agent_id)

            if task_type == "work":
                if isinstance(event, TaskExecutionStarted):
                    app.ingest_grid(x, y, 1.0)  # 1.0 = Running
                    running_count += 1
                elif isinstance(event, TaskBlocked):
                    app.ingest_grid(x, y, 0.5)  # 0.5 = Waiting
                    blocked_count += 1
                elif isinstance(event, TaskExecutionFinished):
                    app.ingest_grid(x, y, 0.0)  # 0.0 = Idle
                    if event.status == "Succeeded":
                        running_count -= 1
                    else:
                        blocked_count -= (
                            1  # Assuming failed blocked tasks are 'unblocked'
                        )

            app.update_status("Blocked", blocked_count)
            app.update_status("Running", running_count)

        except (IndexError, ValueError):
            pass

    # 3. Setup Engine
    engine_bus = cs.MessageBus()
    engine_bus.subscribe(cs.Event, handle_event)

    engine = cs.Engine(
        solver=cs.NativeSolver(), executor=cs.LocalExecutor(), bus=engine_bus
    )

    # 4. Apply Constraint
    print(f"Applying constraint: Max {SLOTS} concurrent 'work' tasks...")
    engine.constraint_manager.update_constraint(
        GlobalConstraint(
            id="funnel",
            scope="task:agent_*_work",
            type="concurrency",
            params={"limit": SLOTS},
        )
    )

    # 5. Launch Agents and Visualization
    print(f"Launching {NUM_AGENTS} agents...")
    tasks = [
        asyncio.create_task(engine.run(make_agent_workflow(i)))
        for i in range(NUM_AGENTS)
    ]

    await app.start()
    try:
        await asyncio.sleep(DURATION)
    finally:
        app.stop()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(run_simulation())
    except KeyboardInterrupt:
        pass
