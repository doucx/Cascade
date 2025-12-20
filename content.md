这是对 `bottleneck_sim` 问题的完整修复计划。

 核心分析
1.  **`Running` 接近 500 的原因 (Scope Mismatch)**:
    *   在 `ConcurrencyConstraintHandler` 中，通配符匹配逻辑过于简单 (`endswith("*")`)。
    *   你的约束 Scope 是 `task:agent_*_work`，但任务名是 `agent_0_work`。由于通配符在中间，简单的后缀检查失败，导致约束未应用，所有任务都以前所未有的并发度运行。
    *   **修复**: 引入 `fnmatch` 进行标准的 Shell 风格通配符匹配。

2.  **`Blocked` 始终为 0 的原因 (Silent Blocking)**:
    *   `ConcurrencyConstraint` 的实现机制是**资源获取 (Resource Acquisition)**，而不是**权限检查 (Permission Check)**。
    *   任务在 `Engine` 中被标记为可执行，但在执行内部调用 `resource_manager.acquire()` 时挂起（等待资源）。
    *   `Engine` 原生逻辑中，这种“资源等待”不会触发 `TaskBlocked` 事件（该事件目前仅由 `check_permission` 返回 `False` 时触发）。
    *   **修复**: 
        1.  在 `ResourceManager` 中暴露 `can_acquire` 检查。
        2.  在 `Engine` 执行节点前，预检资源是否可用。若不可用，主动发射 `TaskBlocked` 事件，以提高可观测性。

3.  **视觉编码更新**:
    *   需要更新 `Palette` 和仿真器逻辑，以支持新的三态显示：休眠 (Grey)、阻塞 (Red)、运行 (White)。

---

 摘要头
## [WIP] fix: 修复瓶颈模拟器的约束匹配与阻塞状态可观测性

### 错误分析
用户报告 `bottleneck_sim.py` 中 `Blocked` 计数为 0 且 `Running` 计数异常高。
1.  **约束失效**: `ConcurrencyConstraintHandler` 中的 `check_permission` 和 `append_requirements` 方法使用简单的字符串切片处理通配符，无法处理 `agent_*_work` 这种中间含通配符的模式。导致约束未匹配到任何任务，资源限制未生效。
2.  **可观测性缺失**: 并发限制是通过 `ResourceManager.acquire` 在异步任务内部实现的。当任务因资源不足而 `await` 时，它在 Engine 层面仍被视为 "Running" (或 Started)，没有发出任何表明其处于等待状态的事件。

### 用户需求
1.  修复约束匹配逻辑，使其支持 `agent_*_work` 模式。
2.  使 Engine 能够感知并广播因资源获取导致的阻塞事件。
3.  更新 `bottleneck_sim` 的视觉呈现，区分休眠、阻塞和计算状态。

### 评论
这是一个涉及核心运行时（Engine/ResourceManager）的修复。增加资源争用的可观测性（发射 `TaskBlocked`）不仅修复了可视化问题，也增强了整个系统的调试能力。

### 目标
1.  在 `cascade-runtime` 中引入 `fnmatch` 修复 Scope 匹配。
2.  在 `ResourceManager` 中添加非阻塞的 `can_acquire` 检查。
3.  在 `Engine` 中利用预检机制发射 `TaskBlocked` 事件。
4.  更新 `palette.py` 和 `bottleneck_sim.py` 适配新的视觉规范。

### 基本原理
通过 `fnmatch` 标准库处理通配符是 Pythonic 且健壮的。在 Engine 执行循环中加入 `can_acquire` 预检是一个低成本的探测，它允许我们在不改变异步等待机制的前提下，向外界（观察者）泄露“即将阻塞”的意图。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #comp/cli #concept/governance #scope/core #ai/instruct #task/domain/governance #task/object/constraint-handler #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修复约束处理器的通配符匹配

我们将修改 `handlers.py`，引入 `fnmatch` 来处理 Scope 匹配，确保 `task:agent_*_work` 能正确匹配到 `agent_0_work`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
~~~~~
~~~~~python
from typing import TYPE_CHECKING, Dict, Any

from .protocols import ConstraintHandler
from cascade.graph.model import Node
from cascade.spec.constraint import GlobalConstraint
from .rate_limiter import RateLimiter


if TYPE_CHECKING:
    from .manager import ConstraintManager


def _parse_rate_string(rate_str: str) -> float:
~~~~~
~~~~~python
from typing import TYPE_CHECKING, Dict, Any
import fnmatch

from .protocols import ConstraintHandler
from cascade.graph.model import Node
from cascade.spec.constraint import GlobalConstraint
from .rate_limiter import RateLimiter


if TYPE_CHECKING:
    from .manager import ConstraintManager


def _matches(scope: str, task_name: str) -> bool:
    """Helper to check if a task name matches a scope pattern."""
    if scope == "global":
        return True
    
    if scope.startswith("task:"):
        pattern = scope.split(":", 1)[1]
        return fnmatch.fnmatch(task_name, pattern)
    
    return False


def _parse_rate_string(rate_str: str) -> float:
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
~~~~~
~~~~~python
    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        """
        Returns False (permission denied) if the task matches the constraint's scope.
        """
        scope = constraint.scope

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
~~~~~python
    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        """
        Returns False (permission denied) if the task matches the constraint's scope.
        """
        if _matches(constraint.scope, task.name):
            return False
        return True
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
~~~~~
~~~~~python
    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        manager: "ConstraintManager",
    ) -> None:
        # Check scope match
        scope = constraint.scope
        is_match = False

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
            # We require 1 slot of this concurrency resource
            requirements[res_name] = 1
~~~~~
~~~~~python
    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        manager: "ConstraintManager",
    ) -> None:
        if _matches(constraint.scope, task.name):
            res_name = self._get_resource_name(constraint)
            # We require 1 slot of this concurrency resource
            requirements[res_name] = 1
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
~~~~~
~~~~~python
    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        # Check scope match
        scope = constraint.scope
        is_match = False

        if scope == "global":
            is_match = True
        elif scope.startswith("task:"):
            target_task_name = scope.split(":", 1)[1]
            if task.name == target_task_name:
                is_match = True

        if not is_match:
            return True

        # Try acquire
        wait_time = self.limiter.try_acquire(self._get_scope_key(constraint))
~~~~~
~~~~~python
    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        if not _matches(constraint.scope, task.name):
            return True

        # Try acquire
        wait_time = self.limiter.try_acquire(self._get_scope_key(constraint))
~~~~~

#### Acts 2: 增强 ResourceManager 以支持预检

我们需要在 `ResourceManager` 中暴露 `can_acquire` 方法，以便 Engine 在尝试获取资源前进行非阻塞检查。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resource_manager.py
~~~~~
~~~~~python
    def update_resource(self, name: str, capacity: float):
        """Dynamically updates or creates a single resource's capacity."""
        self._capacity[name] = float(capacity)
        if name not in self._usage:
            self._usage[name] = 0.0
        # If we reduced capacity below current usage, that's allowed (soft limit),
        # but new acquisitions will block.

    async def acquire(self, requirements: Dict[str, Union[int, float]]):
        """
        Atomically acquires the requested resources.
        Waits until all resources are available.
        """
~~~~~
~~~~~python
    def update_resource(self, name: str, capacity: float):
        """Dynamically updates or creates a single resource's capacity."""
        self._capacity[name] = float(capacity)
        if name not in self._usage:
            self._usage[name] = 0.0
        # If we reduced capacity below current usage, that's allowed (soft limit),
        # but new acquisitions will block.

    def can_acquire(self, requirements: Dict[str, Union[int, float]]) -> bool:
        """
        Checks if the requested resources are currently available without blocking.
        """
        if not requirements:
            return True
        return self._can_acquire(requirements)

    async def acquire(self, requirements: Dict[str, Union[int, float]]):
        """
        Atomically acquires the requested resources.
        Waits until all resources are available.
        """
~~~~~

#### Acts 3: 在 Engine 中发射 TaskBlocked 事件

修改 `engine.py`，在执行节点前调用 `can_acquire`。如果资源不足，发射 `TaskBlocked` 事件（但这不阻止它继续调用 `acquire` 并进入等待状态，只是增加了一个通知）。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        requirements = self.constraint_resolver.resolve(
            node, graph, state_backend, self.constraint_manager
        )
        await self.resource_manager.acquire(requirements)
        try:
            return await self._execute_node_internal(
                node, graph, state_backend, active_resources, run_id, params
            )
        finally:
            await self.resource_manager.release(requirements)
~~~~~
~~~~~python
        requirements = self.constraint_resolver.resolve(
            node, graph, state_backend, self.constraint_manager
        )
        
        # Pre-check for blocking to improve observability
        if not self.resource_manager.can_acquire(requirements):
            from cascade.runtime.events import TaskBlocked
            self.bus.publish(
                TaskBlocked(
                    run_id=run_id,
                    task_id=node.id,
                    task_name=node.name,
                    reason="ResourceContention",
                )
            )

        await self.resource_manager.acquire(requirements)
        try:
            return await self._execute_node_internal(
                node, graph, state_backend, active_resources, run_id, params
            )
        finally:
            await self.resource_manager.release(requirements)
~~~~~

#### Acts 4: 更新调色板 (Palette)

修改 `palette.py` 中的 `bottleneck` 调色板，实现用户请求的视觉编码。
我们定义：
- 0.3: Sleeping (Grey)
- 0.7: Blocked (Red)
- 1.0: Running (White)

~~~~~act
patch_file
observatory/visualization/palette.py
~~~~~
~~~~~python
    @staticmethod
    def bottleneck(states: np.ndarray) -> np.ndarray:
        """
        Maps states to bottleneck visualizer colors using Rich-compatible styles.
        0.0: Idle (Dim Gray)
        0.5: Waiting (Cyan)
        1.0: Running (Bright Green/White)
        """
        # Initialize with Dim Gray
        colors = np.full(states.shape, "rgb(40,40,40)", dtype="<U18")

        # Waiting (Cyan)
        mask_wait = (states > 0.4) & (states < 0.8)
        colors[mask_wait] = "rgb(0,200,200)"

        # Running (Bright White/Green tint)
        mask_run = states >= 0.8
        colors[mask_run] = "rgb(200,255,200)"

        return colors
~~~~~
~~~~~python
    @staticmethod
    def bottleneck(states: np.ndarray) -> np.ndarray:
        """
        Maps states to bottleneck visualizer colors.
        0.0: Idle (Black/Dim)
        0.3: Sleeping (Grey)      -> .
        0.7: Blocked (Red)        -> x
        1.0: Running (White)      -> o
        """
        # Initialize with Black/Dim
        colors = np.full(states.shape, "rgb(20,20,20)", dtype="<U18")

        # Sleeping (Grey) ~ 0.3
        mask_sleep = (states > 0.2) & (states < 0.5)
        colors[mask_sleep] = "rgb(100,100,100)"

        # Blocked (Red) ~ 0.7
        mask_blocked = (states >= 0.5) & (states < 0.9)
        colors[mask_blocked] = "rgb(255,50,50)"

        # Running (Bright White) ~ 1.0
        mask_run = states >= 0.9
        colors[mask_run] = "rgb(255,255,255)"

        return colors
~~~~~

#### Acts 5: 更新仿真实验 (Bottleneck Sim)

修改 `bottleneck_sim.py`，更新 Workflow 以包含显式的 `cs.wait` (产生 Grey 状态)，并更新事件处理逻辑以映射新的状态值。

~~~~~act
patch_file
observatory/protoplasm/governance/bottleneck_sim.py
~~~~~
~~~~~python
def make_agent_workflow(i: int):
    @cs.task(name=f"agent_{i}_work")
    async def work(val):
        await asyncio.sleep(random.uniform(0.1, 0.3))
        return val + 1

    @cs.task(name=f"agent_{i}_loop")
    def loop(val):
        return make_agent_workflow(i)

    return loop(work(0))
~~~~~
~~~~~python
def make_agent_workflow(i: int):
    @cs.task(name=f"agent_{i}_wait")
    async def wait_step(val):
        # Simulate thinking/sleeping state (Grey)
        await asyncio.sleep(random.uniform(0.5, 1.5))
        return val

    @cs.task(name=f"agent_{i}_work")
    async def work(val):
        # Critical section (White), resource constrained
        await asyncio.sleep(random.uniform(0.1, 0.3))
        return val + 1

    @cs.task(name=f"agent_{i}_loop")
    def loop(val):
        return make_agent_workflow(i)

    return loop(work(wait_step(0)))
~~~~~

~~~~~act
patch_file
observatory/protoplasm/governance/bottleneck_sim.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
            if task_type == "wait":
                if isinstance(event, TaskExecutionStarted):
                    app.ingest_grid(x, y, 0.3)  # 0.3 = Sleeping (Grey)
                elif isinstance(event, TaskExecutionFinished):
                    # Cleared by next state, but set to 0.0 momentarily
                    app.ingest_grid(x, y, 0.0)

            elif task_type == "work":
                if isinstance(event, TaskExecutionStarted):
                    app.ingest_grid(x, y, 1.0)  # 1.0 = Running (White)
                    running_count += 1
                    # If it was blocked before, decrement blocked count
                    # Note: We don't strictly track if *this* specific one was blocked,
                    # but heuristic is fine for sim.
                elif isinstance(event, TaskBlocked):
                    app.ingest_grid(x, y, 0.7)  # 0.7 = Blocked (Red)
                    blocked_count += 1
                elif isinstance(event, TaskExecutionFinished):
                    app.ingest_grid(x, y, 0.0)  # 0.0 = Idle
                    if event.status == "Succeeded":
                        running_count -= 1
                    # Note: Blocked count decrement logic is tricky with just events.
                    # Since Started overwrites Blocked visually, we just rely on visual.
                    # For the counter, we might drift if we don't track state per agent.
                    # Let's simple reset:
                    pass
~~~~~

为了更准确的计数，我们需要稍微改进一下 `handle_event` 中的计数器逻辑，不再盲目增减，而是基于 Agent 状态追踪。

~~~~~act
patch_file
observatory/protoplasm/governance/bottleneck_sim.py
~~~~~
~~~~~python
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

            if task_type == "wait":
                if isinstance(event, TaskExecutionStarted):
                    app.ingest_grid(x, y, 0.3)  # 0.3 = Sleeping (Grey)
                elif isinstance(event, TaskExecutionFinished):
                    # Cleared by next state, but set to 0.0 momentarily
                    app.ingest_grid(x, y, 0.0)

            elif task_type == "work":
                if isinstance(event, TaskExecutionStarted):
                    app.ingest_grid(x, y, 1.0)  # 1.0 = Running (White)
                    running_count += 1
                    # If it was blocked before, decrement blocked count
                    # Note: We don't strictly track if *this* specific one was blocked,
                    # but heuristic is fine for sim.
                elif isinstance(event, TaskBlocked):
                    app.ingest_grid(x, y, 0.7)  # 0.7 = Blocked (Red)
                    blocked_count += 1
                elif isinstance(event, TaskExecutionFinished):
                    app.ingest_grid(x, y, 0.0)  # 0.0 = Idle
                    if event.status == "Succeeded":
                        running_count -= 1
                    # Note: Blocked count decrement logic is tricky with just events.
                    # Since Started overwrites Blocked visually, we just rely on visual.
                    # For the counter, we might drift if we don't track state per agent.
                    # Let's simple reset:
                    pass

            app.update_status("Blocked", blocked_count)
            app.update_status("Running", running_count)

        except (IndexError, ValueError):
            pass
~~~~~
~~~~~python
    # 2. Setup Event Handling
    # Track state per agent to ensure accurate counters
    # States: 'idle', 'sleeping', 'blocked', 'running'
    agent_states = {} 

    def get_coords(agent_id: int):
        return (agent_id % grid_width, agent_id // grid_width)

    def update_agent_state(agent_id: int, new_state: str):
        agent_states[agent_id] = new_state
        # Recalculate totals
        blocked = sum(1 for s in agent_states.values() if s == 'blocked')
        running = sum(1 for s in agent_states.values() if s == 'running')
        app.update_status("Blocked", blocked)
        app.update_status("Running", running)

    def handle_event(event: Any):
        if not hasattr(event, "task_name") or not event.task_name.startswith("agent_"):
            return

        try:
            parts = event.task_name.split("_")
            if len(parts) < 3:
                return
            agent_id = int(parts[1])
            task_type = parts[2]

            x, y = get_coords(agent_id)

            if task_type == "wait":
                if isinstance(event, TaskExecutionStarted):
                    app.ingest_grid(x, y, 0.3)  # 0.3 = Sleeping (Grey)
                    update_agent_state(agent_id, 'sleeping')
                
            elif task_type == "work":
                if isinstance(event, TaskBlocked):
                    app.ingest_grid(x, y, 0.7)  # 0.7 = Blocked (Red)
                    update_agent_state(agent_id, 'blocked')
                elif isinstance(event, TaskExecutionStarted):
                    app.ingest_grid(x, y, 1.0)  # 1.0 = Running (White)
                    update_agent_state(agent_id, 'running')
                elif isinstance(event, TaskExecutionFinished):
                    app.ingest_grid(x, y, 0.0)  # 0.0 = Idle
                    update_agent_state(agent_id, 'idle')

        except (IndexError, ValueError):
            pass
~~~~~

### 下一步建议
我们已经完成了对 `bottleneck_sim` 的修复和增强。现在它可以正确显示资源争用导致的阻塞状态。建议运行 `python -m observatory.protoplasm.governance.bottleneck_sim` 来验证效果。如果效果符合预期，下一步可以考虑将这种“预检阻塞”模式标准化，甚至集成到 Dashboard 中。
