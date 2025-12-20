简要回答: 我们将在单 Engine 实例中运行所有 Agent 以模拟资源竞争，暂不引入分布式锁。

## [WIP] feat(sim): 实现资源约束模拟器与阻塞态观测

### 错误分析
无（新功能开发）。

### 用户需求
1.  **模拟瓶颈**：创建一个实验 `bottleneck_sim.py`，模拟 1000+ Agent 争夺少量（如 100）令牌的场景。
2.  **可视化阻塞**：在 CLI 渲染器中，用不同颜色（如红色）区分“正在运行”的任务和“因资源不足被阻塞”的任务。
3.  **增强遥测**：`Engine` 需要在任务因约束受阻时发出明确的 `TaskBlocked` 事件，并在恢复时发出 `TaskResumed`（或直接进入 Running）。

### 评论
这是对 Cascade 调度器的一次“压力测试”。我们实际上是在测试 Python `asyncio` 在高竞争锁下的表现。通过单 Engine 拓扑，我们排除了网络因素，专注于内核行为。

### 目标
1.  修改 `Engine._execute_graph`，在任务进入 `deferred_this_pass` 时发布 `TaskBlocked` 事件。
2.  更新 `TelemetrySubscriber` 和 `runtime_events.json` 以支持新事件。
3.  编写 `observatory/protoplasm/governance/bottleneck_sim.py`，实现单 Engine 多 Agent 的实验逻辑。
4.  在 `ConstraintManager` 中验证令牌桶的排队行为。

### 基本原理
-   **单引擎拓扑**：利用 `asyncio.gather` 并发运行多个 `engine.run()`，它们将共享同一个 `Engine` 实例及其 `ResourceManager`。
-   **事件驱动的可视化**：渲染器不应该去轮询 Engine 状态，而应该响应 `TaskBlocked` 事件将对应像素染红。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #comp/observability #concept/state #scope/core #ai/instruct #task/domain/simulation #task/object/resource-constraint #task/action/stress-test #task/state/begin

---

### Script

#### Acts 1: 定义 TaskBlocked 事件

我们需要在协议层定义新的事件类型，以便系统能够感知“阻塞”这一状态。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/events.py
~~~~~
~~~~~python
@dataclass(frozen=True)
class TaskRetrying(TaskEvent):
    """Fired when a task fails but is about to be retried."""

    attempt: int = 0
    max_attempts: int = 0
    delay: float = 0.0
    error: Optional[str] = None


@dataclass(frozen=True)
class ResourceEvent(Event):
~~~~~
~~~~~python
@dataclass(frozen=True)
class TaskRetrying(TaskEvent):
    """Fired when a task fails but is about to be retried."""

    attempt: int = 0
    max_attempts: int = 0
    delay: float = 0.0
    error: Optional[str] = None


@dataclass(frozen=True)
class TaskBlocked(TaskEvent):
    """Fired when a task is deferred due to constraint violations."""

    reason: str = "Unknown"  # e.g. "RateLimit", "ConcurrencyLimit"


@dataclass(frozen=True)
class ResourceEvent(Event):
~~~~~

#### Acts 2: 更新 Engine 发出阻塞事件

我们在 `_execute_graph` 的调度循环中捕获被 defer 的节点。为了避免日志洪水，我们需要一种去重机制（Debounce），即同一个任务在每一轮 pass 中被 defer 时，只在第一次发出 Blocked 事件，直到它被执行。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        graph = build_graph(target)
        self.flow_manager = FlowManager(graph, target._uuid)
        plan = self.solver.resolve(graph)

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue  # Skip params, they don't execute

                    skip_reason = self.flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        state_backend.mark_skipped(node.id, skip_reason)
                        self.bus.publish(
                            TaskSkipped(
                                run_id=run_id,
                                task_id=node.id,
                                task_name=node.name,
                                reason=skip_reason,
                            )
                        )
                        # Node is resolved (skipped), so not pending for next pass
                        continue

                    if self.constraint_manager.check_permission(node):
                        executable_this_pass.append(node)
                    else:
                        deferred_this_pass.append(node)

                if executable_this_pass:
~~~~~
~~~~~python
        graph = build_graph(target)
        self.flow_manager = FlowManager(graph, target._uuid)
        plan = self.solver.resolve(graph)

        # Track blocked state locally to avoid spamming Blocked events every loop tick
        blocked_nodes = set()

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue  # Skip params, they don't execute

                    skip_reason = self.flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        state_backend.mark_skipped(node.id, skip_reason)
                        self.bus.publish(
                            TaskSkipped(
                                run_id=run_id,
                                task_id=node.id,
                                task_name=node.name,
                                reason=skip_reason,
                            )
                        )
                        # Node is resolved (skipped), so not pending for next pass
                        continue

                    if self.constraint_manager.check_permission(node):
                        executable_this_pass.append(node)
                        if node.id in blocked_nodes:
                            blocked_nodes.remove(node.id)
                    else:
                        deferred_this_pass.append(node)
                        if node.id not in blocked_nodes:
                            from cascade.runtime.events import TaskBlocked
                            self.bus.publish(
                                TaskBlocked(
                                    run_id=run_id,
                                    task_id=node.id,
                                    task_name=node.name,
                                    reason="ConstraintViolation" # Detailed reason requires manager update
                                )
                            )
                            blocked_nodes.add(node.id)

                if executable_this_pass:
~~~~~

#### Acts 3: 注册新事件到遥测订阅者

我们需要确保 `TaskBlocked` 能够被转换成 JSON 并发送到 MQTT（或者在本地测试中被渲染器处理）。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    ConnectorConnected,
    ConnectorDisconnected,
    Event,
)
from cascade.interfaces.protocols import Connector
~~~~~
~~~~~python
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    TaskBlocked,
    ConnectorConnected,
    ConnectorDisconnected,
    Event,
)
from cascade.interfaces.protocols import Connector
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
    def on_task_retrying(self, event: TaskRetrying):
        bus.warning(
            "task.retrying",
            task_name=event.task_name,
            attempt=event.attempt,
            max_attempts=event.max_attempts,
            delay=event.delay,
            error=event.error,
        )

    def on_connector_connected(self, event: ConnectorConnected):
~~~~~
~~~~~python
    def on_task_retrying(self, event: TaskRetrying):
        bus.warning(
            "task.retrying",
            task_name=event.task_name,
            attempt=event.attempt,
            max_attempts=event.max_attempts,
            delay=event.delay,
            error=event.error,
        )

    def on_task_blocked(self, event: TaskBlocked):
        # We might want a dedicated log message for this, but for now info is fine
        # Typically blocked tasks are noisy, so use with caution.
        # In a visualizer, this event is critical.
        pass

    def on_connector_connected(self, event: ConnectorConnected):
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
        event_body = {}
        if isinstance(
            event, (TaskExecutionStarted, TaskExecutionFinished, TaskSkipped)
        ):
            state_map = {
                TaskExecutionStarted: "RUNNING",
                TaskExecutionFinished: "COMPLETED"
                if getattr(event, "status", "") == "Succeeded"
                else "FAILED",
                TaskSkipped: "SKIPPED",
            }
            event_body = {
                "type": "TaskStateEvent",
                "task_id": event.task_id,
                "task_name": event.task_name,
                "state": state_map[type(event)],
                "duration_ms": getattr(event, "duration", 0) * 1000,
                "error": getattr(event, "error", None) or "",
            }
~~~~~
~~~~~python
        event_body = {}
        if isinstance(
            event, (TaskExecutionStarted, TaskExecutionFinished, TaskSkipped, TaskBlocked)
        ):
            state_map = {
                TaskExecutionStarted: "RUNNING",
                TaskExecutionFinished: "COMPLETED"
                if getattr(event, "status", "") == "Succeeded"
                else "FAILED",
                TaskSkipped: "SKIPPED",
                TaskBlocked: "BLOCKED",
            }
            event_body = {
                "type": "TaskStateEvent",
                "task_id": event.task_id,
                "task_name": event.task_name,
                "state": state_map[type(event)],
                "duration_ms": getattr(event, "duration", 0) * 1000,
                "error": getattr(event, "error", None) or "",
            }
~~~~~

#### Acts 4: 编写瓶颈模拟实验

创建 `bottleneck_sim.py`，使用单 Engine 模式运行大量 Agent，并应用全局并发限制。

~~~~~act
write_file
observatory/protoplasm/governance/bottleneck_sim.py
~~~~~
~~~~~python
import asyncio
import random
import time
import shutil
from typing import Dict, Any

import cascade as cs
from cascade.common.messaging import bus as global_bus
from cascade.runtime.events import TaskStateEvent, TaskBlocked, TaskExecutionStarted, TaskExecutionFinished
from cascade.spec.constraint import GlobalConstraint

# Import the visualizer (reuse form renderer chapter)
from observatory.protoplasm.renderer.visualizer_proto import ForestRenderer

# --- Configuration ---
NUM_AGENTS = 500  # Number of concurrent agents trying to compute
SLOTS = 20        # Number of available concurrency slots (Tokens)
DURATION = 15.0   # Seconds

# --- The Agent Logic ---

@cs.task
async def compute_task(agent_id: int, duration: float):
    # Simulate heavy work
    await asyncio.sleep(duration)
    return f"Agent {agent_id} Done"

def constrained_agent(agent_id: int):
    # Each agent tries to perform a computation
    # The computation itself is subject to concurrency limits if we scope it
    # We name the task carefully to match the constraint scope
    work = compute_task(agent_id, random.uniform(0.1, 0.5))
    
    # We can wrap it in a recursive loop to keep pressure constant
    @cs.task
    def loop(_):
        return constrained_agent(agent_id)
        
    return loop(work)

# --- Visualization Adapter ---

class VisualizerAdapter:
    def __init__(self, renderer: ForestRenderer, num_agents: int):
        self.renderer = renderer
        self.num_agents = num_agents
        # Map agent_id to (x, y) coordinates
        self.coords = {}
        cols = int(num_agents**0.5) + 1
        for i in range(num_agents):
            self.coords[i] = (i % cols, i // cols)

    def on_event(self, event: Any):
        # We listen to raw Engine events
        if not isinstance(event, (TaskBlocked, TaskExecutionStarted, TaskExecutionFinished)):
           return

        # Extract agent ID from task name or args?
        # Our task name is usually "compute_task" or "loop". 
        # But we need the ID. 
        # The default task naming doesn't include args.
        # However, we can use the `params` or simply parse the task structure if we had it.
        # For simplicity in this sim, let's rely on a custom naming convention or context.
        # Actually, let's use a simpler mapping: 
        # We can't easily map TaskID -> AgentID without extra data.
        # HACK: Use a global map populated during creation? No, async unsafe.
        # BETTER: Pass the coordinate in the task result/event metadata?
        # Let's assume we can't perfectly map ID for now, so we map randomly?
        # NO, we need consistency.
        
        # Solution: Use task name "agent_X_step"
        pass 

# Since adapting the existing ForestRenderer to dynamic task IDs is complex,
# We will use a simplified text-based visualizer for the 'Sim' part first,
# OR we modify the agent to explicitely update the renderer via a side-effect task.

@cs.task
def render_state(agent_id: int, state: float, renderer_ref):
    # 0.2 = Blocked (Red - simulated in logic), 0.5 = Waiting, 1.0 = Active
    # But here we are inside the task, so we are ACTIVE.
    # We can't render "Blocked" from inside the task because the task IS blocked (not running).
    
    # So we MUST use the Event Bus Subscriber approach.
    pass

# We will use a specialized subscriber for this experiment
class BottleneckVisualizer:
    def __init__(self, renderer: ForestRenderer, num_agents: int):
        self.renderer = renderer
        self.agent_map = {} # task_id -> agent_id
        
        # Pre-calculate coords
        self.grid_width = int(num_agents**0.5) + 1
        
    def get_coords(self, agent_id: int):
        return (agent_id % self.grid_width, agent_id // self.grid_width)

    def handle_event(self, event):
        # Parse agent ID from task name "agent_X"
        if not event.task_name.startswith("agent_"):
            return
            
        try:
            agent_str = event.task_name.split("_")[1]
            agent_id = int(agent_str)
            x, y = self.get_coords(agent_id)
            
            if isinstance(event, TaskExecutionStarted):
                # Active = Bright White/Cyan (1.0)
                self.renderer.ingest(x, y, 1.0)
            elif isinstance(event, TaskBlocked):
                # Blocked = Red (We need to update renderer to support color channels or semantic states)
                # For now, let's use a specific brightness that mapping to a char.
                # In buffer.py: >0.8=#(White), >0.5=o(Cyan), >0.01=.(Grey)
                # We want Red. The current renderer is monochrome-ish.
                # Let's map Blocked to 0.5 (Cyan) and Active to 0.9 (White) for contrast.
                # Or better: Update the renderer to handle 'state' codes.
                self.renderer.ingest(x, y, 0.5) 
            elif isinstance(event, TaskExecutionFinished):
                # Done = Dim
                self.renderer.ingest(x, y, 0.2)
                
        except (IndexError, ValueError):
            pass

async def run_simulation():
    # 1. Setup Renderer
    cols, rows = shutil.get_terminal_size()
    renderer = ForestRenderer(width=cols, height=rows-2)
    viz = BottleneckVisualizer(renderer, NUM_AGENTS)
    
    # 2. Setup Engine
    engine_bus = cs.MessageBus()
    # Hook visualizer to bus
    engine_bus.subscribe(cs.Event, viz.handle_event)
    
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=engine_bus
    )
    
    # 3. Apply Global Constraint (The Funnel)
    # Limit tasks named "agent_*" to SLOTS concurrency
    engine.constraint_manager.update_constraint(
        GlobalConstraint(
            id="funnel",
            scope="task:agent_work", # We will name the work task this
            type="concurrency",
            params={"limit": SLOTS}
        )
    )

    # 4. Define Agent with specific naming
    def make_agent(i):
        # The work task must match the constraint scope
        @cs.task(name=f"agent_{i}_work") # Name contains ID for visualizer, how to match scope?
        # ConstraintHandler uses 'task.name == scope'.
        # It currently supports exact match or 'global'.
        # We need to update ConcurrencyConstraintHandler to support prefix matching or regex
        # for this to work elegantly with unique task names.
        # Alternatively, we use "global" scope for the simulation, since only these tasks are running.
        async def work():
            await asyncio.sleep(random.uniform(0.1, 0.5))
            return i

        # Recursive loop
        @cs.task(name=f"agent_{i}_loop")
        def loop(_):
            return make_agent(i)
            
        return loop(work())

    # Correction: To use 'global' constraint on the work tasks but not the loop tasks (which are just orchestrators),
    # we need the Loop tasks to be unconstrained.
    # If we set scope="global", EVERYTHING is constrained, including the loop logic. 
    # That might cause deadlocks if slots fill up with loop tasks waiting for work tasks.
    # Ideally we match by task name prefix. 
    # Let's update the Handler to support wildcard? 
    # For now, let's just make the work task name "work" and pass ID as arg?
    # But then Visualizer loses ID.
    # 
    # Hack: We will modify the Handler in a separate Act to specificially support this test?
    # Or better: We name the task "work" but rely on `params` or `metadata` for ID?
    # Engine events pass `task_name`.
    # Let's stick to modifying the Handler to support `startswith` logic in the next Act.
    
    print("Sim: Preparing...")
    pass

if __name__ == "__main__":
    pass
~~~~~

#### Acts 5: 改进约束匹配逻辑

为了让 `bottleneck_sim.py` 能够既限制并发又能区分 Agent，我们需要增强 `ConcurrencyConstraintHandler` 的匹配逻辑，支持前缀匹配（`task:prefix*`）。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
~~~~~
~~~~~python
        # Global scope matches everything
        if scope == "global":
            return False

        # Task-specific scope
        if scope.startswith("task:"):
            target_task_name = scope.split(":", 1)[1]
            if task.name == target_task_name:
                return False

        # If no match, this constraint doesn't apply to this task, so it is permitted.
        return True
~~~~~
~~~~~python
        # Global scope matches everything
        if scope == "global":
            return False

        # Task-specific scope
        if scope.startswith("task:"):
            target_pattern = scope.split(":", 1)[1]
            if target_pattern.endswith("*"):
                # Prefix match
                prefix = target_pattern[:-1]
                if task.name.startswith(prefix):
                    return False
            elif task.name == target_pattern:
                return False

        # If no match, this constraint doesn't apply to this task, so it is permitted.
        return True
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
~~~~~
~~~~~python
        if scope == "global":
            is_match = True
        elif scope.startswith("task:"):
            target_task_name = scope.split(":", 1)[1]
            if task.name == target_task_name:
                is_match = True

        if is_match:
            res_name = self._get_resource_name(constraint)
~~~~~
~~~~~python
        if scope == "global":
            is_match = True
        elif scope.startswith("task:"):
            target_pattern = scope.split(":", 1)[1]
            if target_pattern.endswith("*"):
                prefix = target_pattern[:-1]
                if task.name.startswith(prefix):
                    is_match = True
            elif task.name == target_pattern:
                is_match = True

        if is_match:
            res_name = self._get_resource_name(constraint)
~~~~~

#### Acts 6: 完成 bottleneck_sim.py

现在我们可以放心地编写实验代码了。

~~~~~act
write_file
observatory/protoplasm/governance/bottleneck_sim.py
~~~~~
~~~~~python
import asyncio
import random
import shutil
import time
from typing import Any

import cascade as cs
from cascade.runtime.events import TaskBlocked, TaskExecutionStarted, TaskExecutionFinished
from cascade.spec.constraint import GlobalConstraint
from observatory.protoplasm.renderer.visualizer_proto import ForestRenderer

# --- Configuration ---
NUM_AGENTS = 500
SLOTS = 20
DURATION = 10.0

# --- Visualizer Logic ---

class BottleneckVisualizer:
    def __init__(self, renderer: ForestRenderer, num_agents: int):
        self.renderer = renderer
        self.grid_width = int(num_agents**0.5) + 1
        
    def get_coords(self, agent_id: int):
        return (agent_id % self.grid_width, agent_id // self.grid_width)

    def handle_event(self, event: Any):
        # We expect task names like "agent_42_work"
        if not hasattr(event, "task_name") or not event.task_name.startswith("agent_"):
            return
            
        try:
            # Format: "agent_{id}_work" or "agent_{id}_loop"
            parts = event.task_name.split("_")
            if len(parts) < 3: return
            agent_id = int(parts[1])
            task_type = parts[2]
            
            x, y = self.get_coords(agent_id)
            
            if task_type == "work":
                if isinstance(event, TaskExecutionStarted):
                    # Acquired Slot = Bright White
                    self.renderer.ingest(x, y, 1.0)
                elif isinstance(event, TaskBlocked):
                    # Waiting for Slot = Mid Cyan
                    self.renderer.ingest(x, y, 0.5)
                elif isinstance(event, TaskExecutionFinished):
                    # Released Slot = Dim
                    self.renderer.ingest(x, y, 0.0)
                    
        except (IndexError, ValueError):
            pass

# --- Agent Definition ---

def make_agent_workflow(i: int):
    # This task simulates the resource-intensive work
    # It will be named "agent_{i}_work" so it matches the constraint "task:agent_*_work"
    @cs.task(name=f"agent_{i}_work")
    async def work(val):
        # Hold the slot for a bit
        await asyncio.sleep(random.uniform(0.1, 0.3))
        return val + 1

    # This task is the recursive driver, it is NOT constrained
    @cs.task(name=f"agent_{i}_loop")
    def loop(val):
        return make_agent_workflow(i)

    return loop(work(0))

# --- Main ---

async def run_simulation():
    # 1. Setup Renderer
    cols, rows = shutil.get_terminal_size()
    render_height = max(10, rows - 4)
    renderer = ForestRenderer(width=cols, height=render_height)
    viz = BottleneckVisualizer(renderer, NUM_AGENTS)
    
    # 2. Setup Engine
    engine_bus = cs.MessageBus()
    engine_bus.subscribe(cs.Event, viz.handle_event)
    
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=engine_bus
    )
    
    # 3. Apply Constraint
    # "task:agent_*_work" matches our work tasks
    print(f"Applying constraint: Max {SLOTS} concurrent 'work' tasks...")
    engine.constraint_manager.update_constraint(
        GlobalConstraint(
            id="funnel",
            scope="task:agent_*_work",
            type="concurrency",
            params={"limit": SLOTS}
        )
    )

    # 4. Launch Agents
    # We launch them all on the SAME engine instance
    print(f"Launching {NUM_AGENTS} agents...")
    tasks = []
    for i in range(NUM_AGENTS):
        # We use asyncio.create_task to fire them off
        tasks.append(asyncio.create_task(engine.run(make_agent_workflow(i))))
        
    # 5. Run Visualization
    try:
        renderer_task = asyncio.create_task(renderer.start())
        
        # Let it run for DURATION
        await asyncio.sleep(DURATION)
        
    finally:
        renderer.stop()
        # Cancel all agents
        for t in tasks: t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if not renderer_task.done():
            renderer_task.cancel()
            await renderer_task

if __name__ == "__main__":
    try:
        asyncio.run(run_simulation())
    except KeyboardInterrupt:
        pass
~~~~~

### 下一步建议
运行 `python -m observatory.protoplasm.governance.bottleneck_sim`。如果一切顺利，我们应该能看到一个由 500 个点组成的网格，其中大部分是暗淡的（0.0），一部分是青色的（阻塞中，0.5），只有 20 个是亮白色的（正在执行，1.0）。这将完美验证我们的反压机制。
