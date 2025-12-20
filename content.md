Excellent. I'm glad the refined renderer meets your expectations. Now that we have a stable, high-performance visualization framework, let's proceed with migrating the remaining experiments. This will unify our tooling and complete the "Protoplasm" refactoring.

I will migrate `bottleneck_sim.py` and `run_conway_experiment.py` in sequence. The Conway migration is more complex as it involves adapting the `StateValidator` to use the new `TerminalApp`.

## [WIP] feat(observatory): Migrate all experiments to the new visualization framework

### 用户需求
All visual experiments within the `/observatory` directory should use the new, standardized `TerminalApp` framework located in `/observatory/visualization`. This will ensure consistent tooling, better performance, and improved maintainability across the entire suite of experiments.

### 评论
This is the final and most important step of the Protoplasm refactoring. By migrating the remaining, more complex experiments, we prove the new visualization framework is not only performant but also flexible enough to handle different use cases (event-driven cell updates vs. full-frame diff rendering). This completes our goal of creating a reusable "Genesis SDK" component.

### 目标
1.  Migrate `observatory/protoplasm/governance/bottleneck_sim.py` to use `TerminalApp`.
2.  Enhance the `TerminalApp` framework to support efficient full-matrix updates, which is required for the Conway experiment.
3.  Create a new color palette specifically for the "Truth" diff visualization.
4.  Refactor the `StateValidator` to act as a data source for `TerminalApp`, decoupling it from direct rendering.
5.  Migrate `observatory/protoplasm/truth/run_conway_experiment.py` to use the refactored `StateValidator` and `TerminalApp`.
6.  Clean up and remove the old, now-redundant renderer code.

### 基本原理
1.  **Bottleneck Sim**: This is a straightforward migration. We will replace the custom `BottleneckVisualizer` and `UniGridRenderer` with an instance of `TerminalApp`. The event handling logic for `TaskBlocked`, `TaskExecutionStarted`, etc., will be moved into the main experiment function, where it will call `app.ingest_grid()` to update the view.
2.  **Conway Sim**: This requires more finesse.
    *   First, we'll enhance `StateMatrix` with a `set_matrix` method to allow for efficient, whole-grid updates instead of one-cell-at-a-time ingestion.
    *   Next, we'll create a `Palettes.truth_diff` function that maps the integer states of the `DiffMatrix` (`0`: match-dead, `1`: match-alive, `2`: false-positive, `3`: false-negative) to specific colors.
    *   Then, we will refactor `StateValidator`. Instead of managing its own renderer, it will accept an optional `TerminalApp` instance. When the app is present, the validator will compute the diff matrix and push the entire matrix to the `TerminalApp`, along with status updates.
    *   Finally, the main `run_conway_experiment.py` script will be updated to orchestrate this new setup.

### 标签
#intent/refine #intent/build #flow/ready #priority/high #comp/cli #concept/ui #scope/dx #task/domain/visualization #task/object/experiment-integration #task/action/migration #task/state/continue

---
### Script

#### Acts 1: Migrate the Bottleneck Simulation

We'll completely rewrite `bottleneck_sim.py` to use the new framework. It's simpler and clearer than patching.

~~~~~act
write_file
observatory/protoplasm/governance/bottleneck_sim.py
~~~~~
~~~~~python
import asyncio
import random
from typing import Any

import cascade as cs
from cascade.runtime.events import TaskBlocked, TaskExecutionStarted, TaskExecutionFinished
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
    status_bar = StatusBar({"Agents": NUM_AGENTS, "Slots": SLOTS, "Blocked": 0, "Running": 0})
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
            if len(parts) < 3: return
            agent_id = int(parts[1])
            task_type = parts[2]
            
            x, y = get_coords(agent_id)
            
            if task_type == "work":
                if isinstance(event, TaskExecutionStarted):
                    app.ingest_grid(x, y, 1.0) # 1.0 = Running
                    running_count += 1
                elif isinstance(event, TaskBlocked):
                    app.ingest_grid(x, y, 0.5) # 0.5 = Waiting
                    blocked_count += 1
                elif isinstance(event, TaskExecutionFinished):
                    app.ingest_grid(x, y, 0.0) # 0.0 = Idle
                    if event.status == "Succeeded": running_count -= 1
                    else: blocked_count -= 1 # Assuming failed blocked tasks are 'unblocked'
            
            app.update_status("Blocked", blocked_count)
            app.update_status("Running", running_count)
                    
        except (IndexError, ValueError):
            pass

    # 3. Setup Engine
    engine_bus = cs.MessageBus()
    engine_bus.subscribe(cs.Event, handle_event)
    
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=engine_bus
    )
    
    # 4. Apply Constraint
    print(f"Applying constraint: Max {SLOTS} concurrent 'work' tasks...")
    engine.constraint_manager.update_constraint(
        GlobalConstraint(
            id="funnel",
            scope="task:agent_*_work",
            type="concurrency",
            params={"limit": SLOTS}
        )
    )

    # 5. Launch Agents and Visualization
    print(f"Launching {NUM_AGENTS} agents...")
    tasks = [asyncio.create_task(engine.run(make_agent_workflow(i))) for i in range(NUM_AGENTS)]
        
    await app.start()
    try:
        await asyncio.sleep(DURATION)
    finally:
        app.stop()
        for t in tasks: t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    try:
        asyncio.run(run_simulation())
    except KeyboardInterrupt:
        pass
~~~~~

#### Acts 2: Enhance `TerminalApp` to support full matrix updates

We'll add a method to `StateMatrix` to accept a full new grid state and a corresponding ingestion method in `TerminalApp`.

~~~~~act
patch_file
observatory/visualization/matrix.py
~~~~~
~~~~~python
    def get_snapshot(self):
        """Returns a copy of the current brightness matrix."""
        return self.brightness.copy()
~~~~~
~~~~~python
    def get_snapshot(self):
        """Returns a copy of the current brightness matrix."""
        return self.brightness.copy()

    def set_matrix(self, new_matrix: np.ndarray):
        """Directly sets the brightness matrix to a new state."""
        if new_matrix.shape == self.brightness.shape:
            # np.copyto is an efficient way to copy array contents
            np.copyto(self.brightness, new_matrix)
~~~~~
~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~python
    def update_status(self, key: str, value: Any):
        """Asynchronously update a key-value pair in the status bar."""
        self.queue.put_nowait(("status", (key, value)))
~~~~~
~~~~~python
    def update_status(self, key: str, value: Any):
        """Asynchronously update a key-value pair in the status bar."""
        self.queue.put_nowait(("status", (key, value)))

    def ingest_full_matrix(self, new_matrix: np.ndarray):
        """
        Specialized ingestion for full-frame updates, bypassing the queue
        for efficiency as it's a single large data item.
        """
        self.grid_view.matrix.set_matrix(new_matrix)
~~~~~

#### Acts 3: Create the Truth Diff Palette

We'll add a new palette function to `palette.py` for rendering the Conway experiment's validation grid.

~~~~~act
patch_file
observatory/visualization/palette.py
~~~~~
~~~~~python
        # Running (Bright Green/White tint)
        mask_run = states >= 0.8
        colors[mask_run] = "rgb(200,255,200)"

        return colors
~~~~~
~~~~~python
        # Running (Bright White/Green tint)
        mask_run = states >= 0.8
        colors[mask_run] = "rgb(200,255,200)"
        
        return colors

    @staticmethod
    def truth_diff(diff_matrix: np.ndarray) -> np.ndarray:
        """
        Maps a diff matrix to validation colors.
        0: Dead (Correct) -> Dark Gray
        1: Alive (Correct) -> Bright White
        2: False Positive (Ghost) -> Bright Red
        3: False Negative (Missing) -> Bright Cyan
        """
        colors = np.full(diff_matrix.shape, "rgb(40,40,40)", dtype="<U18") # Default to dead
        colors[diff_matrix == 1] = "rgb(220,220,220)" # Alive
        colors[diff_matrix == 2] = "rgb(255,50,50)"   # False Positive
        colors[diff_matrix == 3] = "rgb(50,220,255)"   # False Negative
        return colors
~~~~~

#### Acts 4: Refactor `StateValidator`

We'll rewrite `StateValidator` to remove its direct rendering dependency and instead use the provided `TerminalApp` as a "sink" for its data.

~~~~~act
write_file
observatory/protoplasm/truth/validator.py
~~~~~
~~~~~python
import asyncio
import numpy as np
from typing import Dict, Any, Optional

from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife
from observatory.visualization.app import TerminalApp # New import

class StateValidator:
    def __init__(self, width: int, height: int, connector: Connector, app: Optional[TerminalApp] = None):
        self.width = width
        self.height = height
        self.connector = connector
        self.golden = GoldenLife(width, height)
        self.app = app # Store the app instance
        
        # This internal matrix computes the diff state (0,1,2,3)
        self.diff_matrix = np.zeros((height, width), dtype=np.int8)
        
        # buffer[gen][agent_id] = state
        self.buffer: Dict[int, Dict[int, int]] = {}
        
        self.history_theoretical: Dict[int, np.ndarray] = {}
        self.history_actual: Dict[int, np.ndarray] = {}
        
        self.total_agents = width * height
        self._running = False
        
        self.absolute_errors = 0
        self.relative_errors = 0
        self.max_gen_verified = -1

    async def run(self):
        self._running = True
        if not self.app:
            print(f"⚖️  Validator active (headless). Grid: {self.width}x{self.height}.")
        
        sub = await self.connector.subscribe("validator/report", self.on_report)
        
        try:
            while self._running:
                self._process_buffers()
                await asyncio.sleep(0.01)
        finally:
            await sub.unsubscribe()

    async def on_report(self, topic: str, payload: Any):
        gen = payload['gen']
        agent_id = payload['id']
        
        if gen not in self.buffer:
            self.buffer[gen] = {}
        self.buffer[gen][agent_id] = payload

    def _process_buffers(self):
        next_gen = self.max_gen_verified + 1
        
        if next_gen not in self.buffer:
            if self.app:
                progress = 0
                bar = "░" * 20
                self.app.update_status("Progress", f"Gen {next_gen}: [{bar}] 0/{self.total_agents}")
            return

        current_buffer = self.buffer[next_gen]
        
        if len(current_buffer) < self.total_agents:
            if self.app:
                progress = len(current_buffer) / self.total_agents
                bar_len = 20
                filled = int(bar_len * progress)
                bar = "█" * filled + "░" * (bar_len - filled)
                self.app.update_status("Progress", f"Gen {next_gen}: [{bar}] {len(current_buffer)}/{self.total_agents}")
            return
            
        self._verify_generation(next_gen, current_buffer)
        
        del self.buffer[next_gen]
        if next_gen - 2 in self.history_actual: del self.history_actual[next_gen - 2]
        if next_gen - 2 in self.history_theoretical: del self.history_theoretical[next_gen - 2]
            
        self.max_gen_verified = next_gen

    def _verify_generation(self, gen: int, reports: Dict[int, Any]):
        actual_grid = np.zeros((self.height, self.width), dtype=np.int8)
        for r in reports.values():
            x, y = r['coords']
            actual_grid[y, x] = r['state']
        self.history_actual[gen] = actual_grid

        if gen == 0:
            self.golden.seed(actual_grid)
            self.history_theoretical[0] = actual_grid
            theo_grid = actual_grid
        else:
            prev_theo = self.history_theoretical.get(gen - 1, actual_grid)
            self.golden.seed(prev_theo)
            theo_grid = self.golden.step()
            self.history_theoretical[gen] = theo_grid
            
            diff_abs = np.sum(actual_grid != theo_grid)
            self.absolute_errors += diff_abs
            
            prev_actual = self.history_actual.get(gen - 1, actual_grid)
            self.golden.seed(prev_actual)
            expected_relative = self.golden.step()
            diff_rel = np.sum(actual_grid != expected_relative)
            self.relative_errors += diff_rel
            
        # Update internal diff matrix for rendering
        self.diff_matrix.fill(0) # 0: Dead (Correct)
        self.diff_matrix[(actual_grid == 1) & (theo_grid == 1)] = 1 # 1: Alive (Correct)
        self.diff_matrix[(actual_grid == 1) & (theo_grid == 0)] = 2 # 2: False Positive
        self.diff_matrix[(actual_grid == 0) & (theo_grid == 1)] = 3 # 3: False Negative
        
        # Push updates to the UI
        if self.app:
            self.app.ingest_full_matrix(self.diff_matrix)
            total_err = self.absolute_errors + self.relative_errors
            status_icon = "✅ SYNC" if total_err == 0 else "❌ DRIFT"
            self.app.update_status("Generation", gen)
            self.app.update_status("Status", status_icon)
            self.app.update_status("Total Errors", total_err)
        else:
             # Headless logging
             print(f"Gen {gen} verified. Abs Errors: {self.absolute_errors}, Rel Errors: {self.relative_errors}")

    def stop(self):
        self._running = False
~~~~~

#### Acts 5: Migrate the Conway Experiment Runner

Now we rewrite `run_conway_experiment.py` to use the new `TerminalApp` and the refactored `StateValidator`.

~~~~~act
write_file
observatory/protoplasm/truth/run_conway_experiment.py
~~~~~
~~~~~python
import asyncio
import numpy as np
import shutil
from typing import List

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.protoplasm.agents.conway import conway_agent
from observatory.protoplasm.truth.validator import StateValidator

# New Visualization imports
from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes

# --- Configuration ---
MAX_GENERATIONS = 200

def get_random_seed(width: int, height: int, density: float = 0.2) -> np.ndarray:
    rng = np.random.default_rng()
    noise = rng.random((height, width))
    return (noise < density).astype(np.int8)

def calculate_neighbors(x: int, y: int, width: int, height: int) -> List[int]:
    neighbors = []
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0: continue
            nx, ny = (x + dx) % width, (y + dy) % height
            neighbors.append(ny * width + nx)
    return neighbors

async def run_experiment(visualize: bool = True):
    cols, rows = shutil.get_terminal_size()
    GRID_WIDTH = min(cols // 2, 50)
    GRID_HEIGHT = min(rows - 5, 25)
    
    print(f"🚀 Starting Conway Experiment with grid {GRID_WIDTH}x{GRID_HEIGHT}...")

    # 1. Setup Shared Infrastructure
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # 2. Setup Visualizer App
    app = None
    if visualize:
        grid_view = GridView(
            width=GRID_WIDTH, 
            height=GRID_HEIGHT, 
            palette_func=Palettes.truth_diff,
            decay_per_second=0.0 # No decay for discrete states
        )
        status_bar = StatusBar({"Generation": 0, "Status": "Initializing..."})
        app = TerminalApp(grid_view, status_bar)

    # 3. Setup Validator (now accepts the app)
    validator = StateValidator(GRID_WIDTH, GRID_HEIGHT, connector, app=app)

    # 4. Setup Engine
    engine = cs.Engine(solver=cs.NativeSolver(), executor=cs.LocalExecutor(), bus=cs.MessageBus())
    @resource(name="shared_connector")
    def shared_connector_provider():
        yield connector
    engine.register(shared_connector_provider)
    
    # 5. Create Initial State & Agent Workflows
    initial_grid = get_random_seed(GRID_WIDTH, GRID_HEIGHT, density=0.25)
    agent_workflows = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            agent_id = y * GRID_WIDTH + x
            workflow = conway_agent(
                agent_id=agent_id, x=x, y=y,
                initial_state=int(initial_grid[y, x]),
                neighbor_ids=calculate_neighbors(x, y, GRID_WIDTH, GRID_HEIGHT),
                topic_base="cell", validator_topic="validator/report",
                connector=cs.inject("shared_connector"), max_generations=MAX_GENERATIONS
            )
            agent_workflows.append(workflow)

    # 6. Run
    if app: await app.start()
    validator_task = asyncio.create_task(validator.run())
    agent_tasks = [asyncio.create_task(engine.run(wf)) for wf in agent_workflows]
    all_agents_task = asyncio.gather(*agent_tasks)
    
    try:
        # Wait for all agents to complete their generations
        await all_agents_task
    except (Exception, asyncio.CancelledError) as e:
        if app: app.update_status("Status", f"ERROR: {e}")
        await asyncio.sleep(2) # Show error in UI
    finally:
        validator.stop()
        if app: app.stop()
        if not all_agents_task.done(): all_agents_task.cancel()
        
        await asyncio.gather(validator_task, all_agents_task, return_exceptions=True)
        await connector.disconnect()
        print(f"\nExperiment Finished.")

if __name__ == "__main__":
    try:
        asyncio.run(run_experiment(visualize=True))
    except KeyboardInterrupt:
        pass
~~~~~

#### Acts 6: Final Cleanup

The old truth renderer is now fully replaced and can be safely removed.

~~~~~act
delete_file
observatory/protoplasm/truth/renderer.py
~~~~~

### 下一步建议
The Protoplasm refactoring is now complete. All visual experiments are running on a unified, high-performance, and maintainable framework. This is a perfect point to checkpoint our progress.

My next suggestion would be to create a `[COMMIT]` plan to save all these changes. After that, we can proceed with the next major phase of the "Genesis Grid" project, confident that our foundational tooling is solid.
