简要回答
好的，我们将启动 **战役 I**。首先必须突破 `LocalBusConnector` 在海量订阅下的性能瓶颈（从 O(N) 优化到 O(1)），然后重构 Fireflies 为局部通信模式，最后扩容至 2500 Agent。

## [WIP] refactor(runtime): 优化 LocalBus 路由算法并重构 Fireflies 为局部耦合以支持 2500+ Agent

### 用户需求
1.  **基础设施升级**: 优化 `LocalBusConnector`，使其能支持数千个精确订阅（Exact Subscriptions）而不降低发布性能。
2.  **代理重构**: 将 `kuramoto.py` 中的 Firefly Agent 从“全网广播”重构为“邻居单播（Fan-out）”，以减少无效消息风暴。
3.  **实验扩容**: 修改 `run_fireflies.py`，建立 50x50 (2500 Agent) 的网格拓扑，并验证大规模渲染的稳定性。

### 评论
当前的 `LocalBusConnector` 在 `publish` 时会遍历所有订阅来检查通配符匹配。当 N=2500 且每个 Agent 都有独立 Inbox 时，这意味着每次消息发送都要进行 2500 次字符串匹配，导致 O(N^2) 的整体复杂度，系统必崩。
通过分离“精确订阅”和“通配符订阅”，我们可以将精确路由的复杂度降至 O(1)。结合 Fireflies 的局部化改造，这将使系统具备线性扩展能力。

### 目标
1.  优化 `LocalBusConnector` 的路由逻辑。
2.  重构 `firefly_agent` 逻辑以支持目标列表。
3.  在 `run_fireflies.py` 中实现 2500 Agent 的网格模拟。

### 基本原理
1.  **LocalBus 分离存储**: 引入 `_wildcard_subscriptions` 和 `_exact_subscriptions`。`publish` 时优先 O(1) 查找精确匹配，再 O(W) 遍历通配符（W通常很小）。
2.  **空间局部性**: 萤火虫同步依赖于物理邻近性。在 2500 规模下，全连接是不现实且无必要的。我们将构建 8-邻域（Moore Neighborhood）拓扑。

### 标签
#intent/refine #intent/build #flow/ready #priority/high #comp/runtime #comp/observatory #scope/core #scope/perf #task/domain/observatory #task/object/fireflies #task/action/scale-up #task/state/begin

---

### Script

#### Acts 1: 优化 LocalBusConnector 性能

我们将重写 `LocalBusConnector` 的订阅管理逻辑，分离精确匹配和通配符匹配。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~old
    # --- Broker State (Shared across all instances) ---
    _subscriptions: Dict[str, List["asyncio.Queue"]] = defaultdict(list)
    _retained_messages: Dict[str, Any] = {}
    _lock: Optional[asyncio.Lock] = None

    def __init__(self):
        # Default to True to support pre-run configuration in E2E tests
        self._is_connected = True
        self._listener_tasks = []

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
~~~~~
~~~~~new
    # --- Broker State (Shared across all instances) ---
    _exact_subscriptions: Dict[str, List["asyncio.Queue"]] = defaultdict(list)
    _wildcard_subscriptions: Dict[str, List["asyncio.Queue"]] = defaultdict(list)
    _retained_messages: Dict[str, Any] = {}
    _lock: Optional[asyncio.Lock] = None

    def __init__(self):
        # Default to True to support pre-run configuration in E2E tests
        self._is_connected = True
        self._listener_tasks = []

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~old
    @classmethod
    def _reset_broker_state(cls):
        """Helper for tests to clear the 'broker'."""
        cls._subscriptions.clear()
        cls._retained_messages.clear()
        # Setting to None ensures _get_lock will create a fresh one for the current loop
        cls._lock = None
~~~~~
~~~~~new
    @classmethod
    def _reset_broker_state(cls):
        """Helper for tests to clear the 'broker'."""
        cls._exact_subscriptions.clear()
        cls._wildcard_subscriptions.clear()
        cls._retained_messages.clear()
        # Setting to None ensures _get_lock will create a fresh one for the current loop
        cls._lock = None
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~old
            # Route to all matching queues
            # We iterate over all subscription topics in the broker
            for sub_topic, queues in self._subscriptions.items():
                if self._topic_matches(sub_topic, topic):
                    for q in queues:
                        await q.put((topic, payload))

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> SubscriptionHandle:
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")

        queue = asyncio.Queue()

        async with self._get_lock():
            self._subscriptions[topic].append(queue)

            # Deliver Retained Messages Synchronously for the caller.
            for retained_topic, payload in self._retained_messages.items():
                if self._topic_matches(topic, retained_topic):
                    try:
                        await callback(retained_topic, payload)
                    except Exception as e:
                        bus.error(
                            "localbus.retained_callback_error",
                            topic=retained_topic,
                            error=e,
                        )

        # Start a background listener for NEW incoming messages
        task = asyncio.create_task(self._listener_loop(queue, callback))
        self._listener_tasks.append(task)

        return _LocalSubscriptionHandle(self, topic, queue, task)
~~~~~
~~~~~new
            # Route to all matching queues

            # 1. Exact Matches (O(1))
            if topic in self._exact_subscriptions:
                for q in self._exact_subscriptions[topic]:
                    await q.put((topic, payload))

            # 2. Wildcard Matches (O(W))
            for sub_topic, queues in self._wildcard_subscriptions.items():
                if self._topic_matches(sub_topic, topic):
                    for q in queues:
                        await q.put((topic, payload))

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> SubscriptionHandle:
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")

        queue = asyncio.Queue()
        is_wildcard = "+" in topic or "#" in topic

        async with self._get_lock():
            if is_wildcard:
                self._wildcard_subscriptions[topic].append(queue)
            else:
                self._exact_subscriptions[topic].append(queue)

            # Deliver Retained Messages Synchronously for the caller.
            # Note: Retained messages iteration is still O(R), which is acceptable
            # as it happens only once per subscription.
            for retained_topic, payload in self._retained_messages.items():
                # Check match logic:
                # If I subscribe to "a/+", I want retained "a/1", "a/2".
                # _topic_matches(sub=topic, topic=retained)
                if self._topic_matches(topic, retained_topic):
                    try:
                        await callback(retained_topic, payload)
                    except Exception as e:
                        bus.error(
                            "localbus.retained_callback_error",
                            topic=retained_topic,
                            error=e,
                        )

        # Start a background listener for NEW incoming messages
        task = asyncio.create_task(self._listener_loop(queue, callback))
        self._listener_tasks.append(task)

        return _LocalSubscriptionHandle(self, topic, queue, task)
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~old
        # 2. Remove the queue from the broker's shared state
        async with self._parent._get_lock():
            if self._topic in self._parent._subscriptions:
                try:
                    self._parent._subscriptions[self._topic].remove(self._queue)
                    if not self._parent._subscriptions[self._topic]:
                        del self._parent._subscriptions[self._topic]
                except ValueError:
                    # Queue already removed, which is fine
                    pass
~~~~~
~~~~~new
        # 2. Remove the queue from the broker's shared state
        async with self._parent._get_lock():
            is_wildcard = "+" in self._topic or "#" in self._topic
            target_dict = (
                self._parent._wildcard_subscriptions
                if is_wildcard
                else self._parent._exact_subscriptions
            )

            if self._topic in target_dict:
                try:
                    target_dict[self._topic].remove(self._queue)
                    if not target_dict[self._topic]:
                        del target_dict[self._topic]
                except ValueError:
                    # Queue already removed, which is fine
                    pass
~~~~~

#### Acts 2: 重构 Fireflies Agent

修改 `observatory/agents/kuramoto.py`，支持向多个目标 topic 发送 Fan-out 信号。

~~~~~act
patch_file
observatory/agents/kuramoto.py
~~~~~
~~~~~old
from typing import Any, Dict

import cascade as cs
from cascade.interfaces.protocols import Connector


# --- Atomic Primitives for Agent Behavior ---


@cs.task
async def send_signal(
    topic: str,
    payload: Dict[str, Any],
    should_send: bool,
    connector: Connector,
) -> None:
    """A task to publish a message to the shared bus."""
    if should_send and connector:
        await connector.publish(topic, payload)


@cs.task
async def safe_recv(
    topic: str,
    timeout: float,
    connector: Connector,
) -> Dict[str, Any]:
~~~~~
~~~~~new
from typing import Any, Dict, List

import cascade as cs
from cascade.interfaces.protocols import Connector


# --- Atomic Primitives for Agent Behavior ---


@cs.task
async def fanout_signal(
    topics: List[str],
    payload: Dict[str, Any],
    should_send: bool,
    connector: Connector,
) -> None:
    """A task to publish a message to multiple topics (Fan-out)."""
    if should_send and connector and topics:
        # Optimistic fan-out: we just fire tasks or await in loop.
        # Since LocalBus.publish is non-blocking (just puts to queue), loop is fine.
        for topic in topics:
            await connector.publish(topic, payload)


@cs.task
async def safe_recv(
    topic: str,
    timeout: float,
    connector: Connector,
) -> Dict[str, Any]:
~~~~~

~~~~~act
patch_file
observatory/agents/kuramoto.py
~~~~~
~~~~~old
def firefly_agent(
    agent_id: int,
    initial_phase: float,
    period: float,
    nudge: float,
    flash_topic: str,
    listen_topic: str,
    connector: Connector,
    refractory_period: float = 2.0,  # Blind period after flash
):
    """
    This is the main entry point for a single firefly agent.
    """

    def firefly_cycle(
        agent_id: int,
        phase: float,
        period: float,
        nudge: float,
        flash_topic: str,
        listen_topic: str,
        connector: Connector,
        refractory_period: float,
    ):
        # --- Logic Branching ---

        # 1. Refractory Check: If we are in the "blind" zone, just wait.
        if phase < refractory_period:
            # We are blind. Wait until we exit refractory period.
            blind_wait_duration = refractory_period - phase

            # Use cs.wait for pure time passage (no listening)
            wait_action = cs.wait(blind_wait_duration)

            @cs.task
            def after_refractory(_):
                # We have advanced time by 'blind_wait_duration'.
                # Our phase is now exactly 'refractory_period'.
                return firefly_cycle(
                    agent_id,
                    refractory_period,
                    period,
                    nudge,
                    flash_topic,
                    listen_topic,
                    connector,
                    refractory_period,
                )

            return after_refractory(wait_action)

        # 2. Sensitive Check: We are past refractory. Listen for neighbors.
        else:
            time_to_flash = period - phase
            # Ensure we don't have negative timeout due to floating point drift
            wait_timeout = max(0.01, time_to_flash)

            perception = safe_recv(
                listen_topic, timeout=wait_timeout, connector=connector
            )

            @cs.task
            def process_perception(p: Dict[str, Any]) -> cs.LazyResult:
                is_timeout = p.get("timeout", False)
                elapsed_time = p.get("elapsed", 0.0)

                # Update actual phase based on real time passed
                current_actual_phase = phase + elapsed_time

                # Determine Action
                if is_timeout:
                    # We reached the end of the period. FLASH!
                    flash_payload = {
                        "agent_id": agent_id,
                        "phase": current_actual_phase,
                    }

                    # We send the signal *then* recurse with phase 0
                    flash = send_signal(
                        topic=flash_topic,
                        payload=flash_payload,
                        should_send=True,
                        connector=connector,
                    )

                    @cs.task
                    def loop_reset(_, _flash):
                        jitter = random.uniform(0.0, 0.1)
                        return firefly_cycle(
                            agent_id,
                            0.0 + jitter,
                            period,
                            nudge,
                            flash_topic,
                            listen_topic,
                            connector,
                            refractory_period,
                        )

                    return loop_reset(p, flash)

                else:
                    # We heard a neighbor! NUDGE!
                    # Advance phase, but cap at period (so we don't flash immediately,
                    # we just get closer).
                    # NOTE: In some models, if nudge pushes > period, we flash immediately.
                    # Here we keep it simple: just advance.
                    next_phase = current_actual_phase + nudge

                    # If the nudge pushes us past the period, we wrap around or clamp.
                    # Standard PCO: Jump to 1 (fire). But here let's just jump forward.
                    # If next_phase > period, the next cycle loop will see time_to_flash < 0 and fire immediately.

                    return firefly_cycle(
                        agent_id,
                        next_phase,
                        period,
                        nudge,
                        flash_topic,
                        listen_topic,
                        connector,
                        refractory_period,
                    )

            return process_perception(perception)

    return firefly_cycle(
        agent_id,
        initial_phase,
        period,
        nudge,
        flash_topic,
        listen_topic,
        connector,
        refractory_period,
    )
~~~~~
~~~~~new
def firefly_agent(
    agent_id: int,
    initial_phase: float,
    period: float,
    nudge: float,
    neighbor_inboxes: List[str],
    my_inbox: str,
    connector: Connector,
    refractory_period: float = 2.0,  # Blind period after flash
):
    """
    This is the main entry point for a single firefly agent.
    """

    def firefly_cycle(
        agent_id: int,
        phase: float,
        period: float,
        nudge: float,
        neighbor_inboxes: List[str],
        my_inbox: str,
        connector: Connector,
        refractory_period: float,
    ):
        # --- Logic Branching ---

        # 1. Refractory Check: If we are in the "blind" zone, just wait.
        if phase < refractory_period:
            # We are blind. Wait until we exit refractory period.
            blind_wait_duration = refractory_period - phase

            # Use cs.wait for pure time passage (no listening)
            wait_action = cs.wait(blind_wait_duration)

            @cs.task
            def after_refractory(_):
                # We have advanced time by 'blind_wait_duration'.
                # Our phase is now exactly 'refractory_period'.
                return firefly_cycle(
                    agent_id,
                    refractory_period,
                    period,
                    nudge,
                    neighbor_inboxes,
                    my_inbox,
                    connector,
                    refractory_period,
                )

            return after_refractory(wait_action)

        # 2. Sensitive Check: We are past refractory. Listen for neighbors.
        else:
            time_to_flash = period - phase
            # Ensure we don't have negative timeout due to floating point drift
            wait_timeout = max(0.01, time_to_flash)

            # Listen only to MY inbox
            perception = safe_recv(
                my_inbox, timeout=wait_timeout, connector=connector
            )

            @cs.task
            def process_perception(p: Dict[str, Any]) -> cs.LazyResult:
                is_timeout = p.get("timeout", False)
                elapsed_time = p.get("elapsed", 0.0)

                # Update actual phase based on real time passed
                current_actual_phase = phase + elapsed_time

                # Determine Action
                if is_timeout:
                    # We reached the end of the period. FLASH!
                    flash_payload = {
                        "agent_id": agent_id,
                        "phase": current_actual_phase,
                    }

                    # We fan-out the signal to all neighbors
                    # Also publish to the global visualization topic (optional, but good for debug)
                    # For performance, visualizer could subscribe to 'firefly/+/inbox' or a dedicated vis topic.
                    # Let's add 'firefly/visualizer' to the target list if we want centralized viz.
                    # For now, we assume visualizer subscribes to ALL inboxes or we add a specific one.
                    # Let's add 'firefly/flash' for the visualizer to keep it simple.
                    targets = neighbor_inboxes + ["firefly/flash"]

                    flash = fanout_signal(
                        topics=targets,
                        payload=flash_payload,
                        should_send=True,
                        connector=connector,
                    )

                    @cs.task
                    def loop_reset(_, _flash):
                        jitter = random.uniform(0.0, 0.1)
                        return firefly_cycle(
                            agent_id,
                            0.0 + jitter,
                            period,
                            nudge,
                            neighbor_inboxes,
                            my_inbox,
                            connector,
                            refractory_period,
                        )

                    return loop_reset(p, flash)

                else:
                    # We heard a neighbor! NUDGE!
                    next_phase = current_actual_phase + nudge
                    return firefly_cycle(
                        agent_id,
                        next_phase,
                        period,
                        nudge,
                        neighbor_inboxes,
                        my_inbox,
                        connector,
                        refractory_period,
                    )

            return process_perception(perception)

    return firefly_cycle(
        agent_id,
        initial_phase,
        period,
        nudge,
        neighbor_inboxes,
        my_inbox,
        connector,
        refractory_period,
    )
~~~~~

#### Acts 3: 扩容实验脚本

修改 `observatory/experiments/run_fireflies.py`，实现网格生成和 2500 Agent 的配置。

~~~~~act
write_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
import asyncio
import random
from typing import Dict, Any, List

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

# --- Constants ---
GRID_SIDE = 50
NUM_AGENTS = GRID_SIDE * GRID_SIDE  # 2500
PERIOD = 3.0


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
    decay_duty_cycle: float = 0.5,
):
    """
    Sets up and runs the firefly synchronization experiment.
    """
    grid_width = int(num_agents**0.5)
    print(
        f"🔥 Starting {'VISUAL' if visualize else 'HEADLESS'} firefly experiment with {num_agents} agents ({grid_width}x{grid_width})..."
    )

    # 1. Initialize Shared Bus
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # --- Setup Monitor & Visualizer ---
    # Monitor now needs to handle many more agents.
    monitor = ConvergenceMonitor(num_agents, period, connector)

    app = None
    app_task = None

    if visualize:
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
        # Agents now also publish to "firefly/flash" for the visualizer/monitor
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

    # Batch creation to avoid freezing UI loop
    print("Generating Agent Workflows...")
    for i in range(num_agents):
        initial_phase = random.uniform(0, period)
        
        neighbor_ids = get_neighbors(i, grid_width, grid_width)
        neighbor_inboxes = [f"firefly/{nid}/inbox" for nid in neighbor_ids]
        my_inbox = f"firefly/{i}/inbox"

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
            neighbor_inboxes=neighbor_inboxes,
            my_inbox=my_inbox,
            connector=connector,
            refractory_period=period * 0.2,
        )

        agent_tasks.append(engine.run(agent_workflow))
        
        # Yield every 500 agents to keep UI responsive during setup
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

        if not all_agent_tasks.done():
            all_agent_tasks.cancel()
            await asyncio.gather(all_agent_tasks, return_exceptions=True)

        await asyncio.gather(monitor_task, return_exceptions=True)
        if app_task and not app_task.done():
            await app_task

        await connector.disconnect()


if __name__ == "__main__":
    asyncio.run(run_experiment(visualize=True))
~~~~~

### 下一步建议
我们已经完成了代码层面的优化和重构。现在应该运行 `observatory/experiments/run_fireflies.py` 来验证 2500 Agent 规模下的性能表现。如果 `TerminalApp` 在 2500 Agent 下出现渲染卡顿，我们可能需要进一步优化 `GridView` 的渲染逻辑，例如采用差异渲染或降低刷新率。
