简要回答
这是一个非常实用的运维特性。我们将通过“定时唤醒 + 惰性清理”的策略来实现 TTL。

`ConstraintManager` 将负责维护约束的生命周期：当接收到带 `expires_at` 的约束时，它会通过 `loop.call_later` 预约一个唤醒信号。`Engine` 在被唤醒后（无论是因新消息还是定时器），都会主动调用清理逻辑移除过期约束，从而释放资源并恢复被阻塞的任务。同时，我们将更新 CLI 工具以支持 `--ttl` 参数，自动计算绝对过期时间并下发。

这形成了一个闭环的自动化运维机制。

## [WIP] feat(runtime): 实现约束的 TTL (Time-To-Live) 与自动过期清理

### 用户需求
用户希望发布的控制指令（如“暂停”或“限流”）能够只持续一段时间（例如“暂停 5 分钟”），之后自动失效，而不需要人工介入去手动恢复。这对于故障恢复或临时运维操作至关重要。

### 评论
实现 TTL 的关键在于 Runtime 如何在约束过期时自动清理它。由于我们在上一阶段已经实现了基于时间的 `request_wakeup` 机制，我们可以复用它：当添加一个带 TTL 的约束时，我们预约一个在 `expires_at` 时刻的唤醒，然后在唤醒时清理过期约束。

### 目标
1.  在 `ConstraintManager` 中实现 `cleanup_expired_constraints` 方法，并重构删除逻辑。
2.  修改 `update_constraint`，使其能够为带 TTL 的约束自动调度唤醒。
3.  更新 `Engine`，使其在每次循环唤醒后调用清理逻辑。
4.  更新 `cs-controller` 的 `pause` 和 `set-limit` 命令，添加 `--ttl` 参数。
5.  添加 E2E 测试验证 TTL 行为。

### 基本原理
利用 `Engine` 的事件循环特性，我们将 TTL 转换为一个定时的唤醒事件。这不仅能保证约束在过期时“及时”失效（而不是等到下一次任务调度时），还能通过清理逻辑自动触发 Handler 的 `on_constraint_remove`，从而正确释放占用的资源（如并发槽位）。

### 标签
#intent/build #flow/ready #priority/medium #comp/runtime #comp/cli #concept/config #scope/core #ai/instruct #task/domain/ops #task/object/constraint-ttl #task/action/implement #task/state/begin

---

### Script

#### Acts 1: 更新 ConstraintManager 以支持 TTL 和清理

我们需要引入 `time` 模块，提取删除逻辑为 `_remove_constraint_by_id`，并在 `update_constraint` 中调度唤醒。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node
from .protocols import ConstraintHandler
from cascade.runtime.resource_manager import ResourceManager


class ConstraintManager:
    """
    Manages a collection of global constraints and dispatches them to pluggable
    handlers for evaluation.
    """

    def __init__(self, resource_manager: ResourceManager):
        self.resource_manager = resource_manager
        # Stores active constraints by their unique ID
        self._constraints: Dict[str, GlobalConstraint] = {}
        # Stores registered handlers by the constraint type they handle
        self._handlers: Dict[str, ConstraintHandler] = {}
        # Callback to wake up the engine loop
        self._wakeup_callback: Any = None
~~~~~
~~~~~python
import time
from typing import Dict, Any
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node
from .protocols import ConstraintHandler
from cascade.runtime.resource_manager import ResourceManager


class ConstraintManager:
    """
    Manages a collection of global constraints and dispatches them to pluggable
    handlers for evaluation.
    """

    def __init__(self, resource_manager: ResourceManager):
        self.resource_manager = resource_manager
        # Stores active constraints by their unique ID
        self._constraints: Dict[str, GlobalConstraint] = {}
        # Stores registered handlers by the constraint type they handle
        self._handlers: Dict[str, ConstraintHandler] = {}
        # Callback to wake up the engine loop
        self._wakeup_callback: Any = None
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
~~~~~
~~~~~python
    def register_handler(self, handler: ConstraintHandler) -> None:
        """Registers a constraint handler for the type it handles."""
        self._handlers[handler.handles_type()] = handler

    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """Adds a new constraint or updates an existing one."""
        self._constraints[constraint.id] = constraint

        handler = self._handlers.get(constraint.type)
        if handler:
            handler.on_constraint_add(constraint, self)

    def remove_constraints_by_scope(self, scope: str) -> None:
        """Removes all constraints that match the given scope."""
        ids_to_remove = [
            cid for cid, c in self._constraints.items() if c.scope == scope
        ]
        for cid in ids_to_remove:
            constraint = self._constraints[cid]
            handler = self._handlers.get(constraint.type)
            if handler:
                handler.on_constraint_remove(constraint, self)
            del self._constraints[cid]

    def check_permission(self, task: Node) -> bool:
        """
        Evaluates all active constraints against a task. If any handler denies
        permission, the task is deferred.
        """
        # TODO: Implement expiry logic (check constraint.expires_at)

        for constraint in self._constraints.values():
            handler = self._handlers.get(constraint.type)
            if not handler:
                continue  # No handler for this constraint type, so we ignore it

            # If the handler denies permission, we stop immediately.
            if not handler.check_permission(task, constraint, self):
                return False  # Execution is not permitted
~~~~~
~~~~~python
    def register_handler(self, handler: ConstraintHandler) -> None:
        """Registers a constraint handler for the type it handles."""
        self._handlers[handler.handles_type()] = handler

    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """Adds a new constraint or updates an existing one."""
        self._constraints[constraint.id] = constraint

        # Schedule wakeup if TTL is set
        if constraint.expires_at:
            now = time.time()
            if constraint.expires_at > now:
                self.request_wakeup(constraint.expires_at - now)

        handler = self._handlers.get(constraint.type)
        if handler:
            handler.on_constraint_add(constraint, self)

    def _remove_constraint_by_id(self, cid: str) -> None:
        """Helper to remove a constraint and notify handler."""
        if cid not in self._constraints:
            return
        constraint = self._constraints[cid]
        handler = self._handlers.get(constraint.type)
        if handler:
            handler.on_constraint_remove(constraint, self)
        del self._constraints[cid]

    def remove_constraints_by_scope(self, scope: str) -> None:
        """Removes all constraints that match the given scope."""
        ids_to_remove = [
            cid for cid, c in self._constraints.items() if c.scope == scope
        ]
        for cid in ids_to_remove:
            self._remove_constraint_by_id(cid)

    def cleanup_expired_constraints(self) -> None:
        """Removes constraints that have exceeded their TTL."""
        now = time.time()
        expired_ids = [
            cid
            for cid, c in self._constraints.items()
            if c.expires_at is not None and c.expires_at <= now
        ]

        for cid in expired_ids:
            self._remove_constraint_by_id(cid)

        # Reschedule wakeup for the next earliest expiration if any remain
        next_expiry = None
        for c in self._constraints.values():
            if c.expires_at and c.expires_at > now:
                if next_expiry is None or c.expires_at < next_expiry:
                    next_expiry = c.expires_at

        if next_expiry:
            # We add a small buffer (0.1s) to ensure we wake up strictly after expiration
            self.request_wakeup(max(0, next_expiry - now + 0.1))

    def check_permission(self, task: Node) -> bool:
        """
        Evaluates all active constraints against a task. If any handler denies
        permission, the task is deferred.
        """
        for constraint in self._constraints.values():
            handler = self._handlers.get(constraint.type)
            if not handler:
                continue  # No handler for this constraint type, so we ignore it

            # If the handler denies permission, we stop immediately.
            if not handler.check_permission(task, constraint, self):
                return False  # Execution is not permitted
~~~~~

#### Acts 2: 更新 Engine 以触发清理

在 Engine 每次被唤醒（无论是收到消息还是定时器触发）后，都应该检查并清理过期约束。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                if pending_nodes_in_stage and not executable_this_pass:
                    # All remaining nodes are blocked by constraints. Wait for a wakeup
                    # signal (e.g., from a constraint change) before retrying.
                    await self._wakeup_event.wait()
                    self._wakeup_event.clear()
~~~~~
~~~~~python
                if pending_nodes_in_stage and not executable_this_pass:
                    # All remaining nodes are blocked by constraints. Wait for a wakeup
                    # signal (e.g., from a constraint change or TTL expiration) before retrying.
                    await self._wakeup_event.wait()
                    self._wakeup_event.clear()
                    self.constraint_manager.cleanup_expired_constraints()
~~~~~

#### Acts 3: 更新 cs-controller 以支持 --ttl

修改 `set_limit` 和 `pause` 命令，添加 `--ttl` 参数并计算绝对时间戳。

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
import asyncio
import typer
import uuid
from dataclasses import asdict

from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer
from cascade.connectors.mqtt import MqttConnector
from cascade.spec.constraint import GlobalConstraint

app = typer.Typer(
    help="A command-line tool to control running Cascade workflows via MQTT."
)


async def _publish_pause(scope: str, hostname: str, port: int):
    """Core logic for publishing a pause constraint."""
    connector = MqttConnector(hostname=hostname, port=port)
    try:
        bus.info("controller.connecting", hostname=hostname, port=port)
        await connector.connect()
        bus.info("controller.connected")

        # Create a unique, descriptive ID for the constraint
        constraint_id = f"pause-{scope}-{uuid.uuid4().hex[:8]}"
        constraint = GlobalConstraint(
            id=constraint_id, scope=scope, type="pause", params={}
        )

        # Convert to dictionary for JSON serialization
        payload = asdict(constraint)

        # Publish to a structured topic based on scope
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
~~~~~
~~~~~python
import asyncio
import time
import typer
import uuid
from dataclasses import asdict

from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer
from cascade.connectors.mqtt import MqttConnector
from cascade.spec.constraint import GlobalConstraint

app = typer.Typer(
    help="A command-line tool to control running Cascade workflows via MQTT."
)


async def _publish_pause(scope: str, ttl: int | None, hostname: str, port: int):
    """Core logic for publishing a pause constraint."""
    connector = MqttConnector(hostname=hostname, port=port)
    try:
        bus.info("controller.connecting", hostname=hostname, port=port)
        await connector.connect()
        bus.info("controller.connected")

        # Create a unique, descriptive ID for the constraint
        constraint_id = f"pause-{scope}-{uuid.uuid4().hex[:8]}"
        expires_at = time.time() + ttl if ttl else None

        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="pause",
            params={},
            expires_at=expires_at,
        )

        # Convert to dictionary for JSON serialization
        payload = asdict(constraint)

        # Publish to a structured topic based on scope
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
~~~~~

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
async def _publish_limit(
    scope: str,
    concurrency: int | None,
    rate: str | None,
    hostname: str,
    port: int,
):
    """Core logic for publishing concurrency or rate limit constraints."""
    connector = MqttConnector(hostname=hostname, port=port)
    try:
        bus.info("controller.connecting", hostname=hostname, port=port)
        await connector.connect()
        bus.info("controller.connected")

        topic = f"cascade/constraints/{scope.replace(':', '/')}"

        if concurrency is not None:
            constraint_id = f"concurrency-{scope}-{uuid.uuid4().hex[:8]}"
            constraint = GlobalConstraint(
                id=constraint_id,
                scope=scope,
                type="concurrency",
                params={"limit": concurrency},
            )
            bus.info(
                "controller.publishing_limit",
                scope=scope,
                topic=topic,
                limit=concurrency,
            )
            await connector.publish(topic, asdict(constraint), retain=True)

        if rate is not None:
            constraint_id = f"ratelimit-{scope}-{uuid.uuid4().hex[:8]}"
            constraint = GlobalConstraint(
                id=constraint_id,
                scope=scope,
                type="rate_limit",
                params={"rate": rate},
            )
            bus.info(
                "controller.publishing_rate", scope=scope, topic=topic, rate=rate
            )
            await connector.publish(topic, asdict(constraint), retain=True)

        await asyncio.sleep(0.1)
        bus.info("controller.publish_limit_success")
~~~~~
~~~~~python
async def _publish_limit(
    scope: str,
    concurrency: int | None,
    rate: str | None,
    ttl: int | None,
    hostname: str,
    port: int,
):
    """Core logic for publishing concurrency or rate limit constraints."""
    connector = MqttConnector(hostname=hostname, port=port)
    try:
        bus.info("controller.connecting", hostname=hostname, port=port)
        await connector.connect()
        bus.info("controller.connected")

        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        expires_at = time.time() + ttl if ttl else None

        if concurrency is not None:
            constraint_id = f"concurrency-{scope}-{uuid.uuid4().hex[:8]}"
            constraint = GlobalConstraint(
                id=constraint_id,
                scope=scope,
                type="concurrency",
                params={"limit": concurrency},
                expires_at=expires_at,
            )
            bus.info(
                "controller.publishing_limit",
                scope=scope,
                topic=topic,
                limit=concurrency,
            )
            await connector.publish(topic, asdict(constraint), retain=True)

        if rate is not None:
            constraint_id = f"ratelimit-{scope}-{uuid.uuid4().hex[:8]}"
            constraint = GlobalConstraint(
                id=constraint_id,
                scope=scope,
                type="rate_limit",
                params={"rate": rate},
                expires_at=expires_at,
            )
            bus.info(
                "controller.publishing_rate", scope=scope, topic=topic, rate=rate
            )
            await connector.publish(topic, asdict(constraint), retain=True)

        await asyncio.sleep(0.1)
        bus.info("controller.publish_limit_success")
~~~~~

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
@app.command()
def set_limit(
    scope: str = typer.Option(
        ...,
        "--scope",
        help="The scope to apply the limit to (e.g., 'global', 'task:api_call').",
    ),
    concurrency: int = typer.Option(
        None, "--concurrency", help="The maximum number of concurrent tasks."
    ),
    rate: str = typer.Option(
        None, "--rate", help="The rate limit (e.g., '10/m', '5/s')."
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'concurrency' or 'rate_limit' constraint to the MQTT broker.
    You must provide either --concurrency or --rate (or both).
    """
    if concurrency is None and rate is None:
        print("Error: Must provide either --concurrency or --rate.")
        raise typer.Exit(code=1)

    try:
        asyncio.run(
            _publish_limit(
                scope=scope,
                concurrency=concurrency,
                rate=rate,
                hostname=hostname,
                port=port,
            )
        )
~~~~~
~~~~~python
@app.command()
def set_limit(
    scope: str = typer.Option(
        ...,
        "--scope",
        help="The scope to apply the limit to (e.g., 'global', 'task:api_call').",
    ),
    concurrency: int = typer.Option(
        None, "--concurrency", help="The maximum number of concurrent tasks."
    ),
    rate: str = typer.Option(
        None, "--rate", help="The rate limit (e.g., '10/m', '5/s')."
    ),
    ttl: int = typer.Option(
        None, "--ttl", help="Time to live in seconds. Constraint expires automatically."
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'concurrency' or 'rate_limit' constraint to the MQTT broker.
    You must provide either --concurrency or --rate (or both).
    """
    if concurrency is None and rate is None:
        print("Error: Must provide either --concurrency or --rate.")
        raise typer.Exit(code=1)

    try:
        asyncio.run(
            _publish_limit(
                scope=scope,
                concurrency=concurrency,
                rate=rate,
                ttl=ttl,
                hostname=hostname,
                port=port,
            )
        )
~~~~~

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
@app.command()
def pause(
    scope: str = typer.Argument(
        "global",
        help="The scope to pause (e.g., 'global', 'project:etl', 'task:api_call').",
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'pause' constraint to the MQTT broker.
    This will cause running Cascade engines to stop scheduling new tasks that
    match the specified scope until a 'resume' command is sent.
    """
    try:
        asyncio.run(_publish_pause(scope=scope, hostname=hostname, port=port))
~~~~~
~~~~~python
@app.command()
def pause(
    scope: str = typer.Argument(
        "global",
        help="The scope to pause (e.g., 'global', 'project:etl', 'task:api_call').",
    ),
    ttl: int = typer.Option(
        None, "--ttl", help="Time to live in seconds. Pause expires automatically."
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'pause' constraint to the MQTT broker.
    This will cause running Cascade engines to stop scheduling new tasks that
    match the specified scope until a 'resume' command is sent.
    """
    try:
        asyncio.run(
            _publish_pause(scope=scope, ttl=ttl, hostname=hostname, port=port)
        )
~~~~~

#### Acts 4: 添加 E2E TTL 测试

验证短暂的 Pause 是否会自动解除。

~~~~~act
write_file
tests/py/e2e/test_e2e_ttl.py
~~~~~
~~~~~python
import asyncio
import time
from typing import Callable, Awaitable, Dict, Any, List
from collections import defaultdict
import uuid
from dataclasses import asdict

import pytest
import cascade as cs
from cascade.interfaces.protocols import Connector, Executor
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.graph.model import Node
from cascade.spec.constraint import GlobalConstraint


# --- Reusing InProcessConnector (Ideally this should be a shared fixture) ---
class InProcessConnector(Connector):
    _shared_topics: Dict[str, List[asyncio.Queue]] = defaultdict(list)
    _retained_messages: Dict[str, Any] = {}

    def __init__(self):
        self._shared_topics.clear()
        self._retained_messages.clear()

    async def connect(self) -> None: pass
    async def disconnect(self) -> None: pass

    async def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False) -> None:
        if retain:
            if payload:
                self._retained_messages[topic] = payload
            elif topic in self._retained_messages:
                del self._retained_messages[topic]
        for sub_topic, queues in self._shared_topics.items():
            if self._topic_matches(subscription=sub_topic, topic=topic):
                for q in queues:
                    await q.put((topic, payload))

    async def subscribe(self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]) -> None:
        queue = asyncio.Queue()
        self._shared_topics[topic].append(queue)
        for retained_topic, payload in self._retained_messages.items():
            if self._topic_matches(subscription=topic, topic=retained_topic):
                await callback(retained_topic, payload)
        asyncio.create_task(self._listen_on_queue(queue, callback))

    async def _listen_on_queue(self, queue: asyncio.Queue, callback):
        while True:
            try:
                topic, payload = await queue.get()
                await callback(topic, payload)
                queue.task_done()
            except asyncio.CancelledError:
                break

    def _topic_matches(self, subscription: str, topic: str) -> bool:
        if subscription == topic: return True
        if subscription.endswith("/#"):
            prefix = subscription[:-2]
            if topic.startswith(prefix): return True
        return False


class ControllerTestApp:
    def __init__(self, connector: Connector):
        self.connector = connector

    async def pause_with_ttl(self, scope: str, ttl: int):
        constraint_id = f"pause-{scope}-{uuid.uuid4().hex[:8]}"
        expires_at = time.time() + ttl
        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="pause",
            params={},
            expires_at=expires_at
        )
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await self.connector.publish(topic, payload, retain=True)


class MockWorkExecutor(Executor):
    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        return "done"


@pytest.mark.asyncio
async def test_e2e_ttl_expiration():
    """
    Tests that a pause constraint automatically expires after TTL.
    """
    connector = InProcessConnector()
    controller = ControllerTestApp(connector)

    # 1. Publish a pause with short TTL (0.2s)
    # We use a slightly longer TTL than the check interval to ensure we catch the pause state
    await controller.pause_with_ttl(scope="global", ttl=0.25)

    @cs.task
    def simple_task():
        return True

    workflow = simple_task()

    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=MessageBus(),
        connector=connector,
    )

    start_time = time.time()
    
    # 2. Run engine. It should be paused initially.
    # The Engine loop will wait on wakeup.
    # ConstraintManager should have scheduled a wakeup at T+0.25s.
    # At T+0.25s, Engine wakes up, cleans expired constraint, and unblocks.
    await engine.run(workflow)
    
    duration = time.time() - start_time

    # 3. Assertions
    # Duration must be at least the TTL (0.25s), proving it was blocked.
    assert duration >= 0.24, f"Engine didn't wait for TTL! Duration: {duration:.3f}s"
    
    # But it shouldn't wait forever (e.g. < 1s)
    assert duration < 1.0, "Engine waited too long or didn't recover."
~~~~~

### 下一步建议
TTL 功能的加入标志着我们完成了第三阶段的核心目标——环境感知与控制。

现在我们拥有：
1.  **可观测性 (Phase 2)**: MQTT 遥测与 `cs-observer`。
2.  **可控制性 (Phase 3)**: 基于 MQTT 的动态约束与 `cs-controller`。
3.  **自愈能力 (Phase 3)**: 约束的自动过期 (TTL)。

接下来的工作可以转向 **Phase 4 (Tooling)** 的深度优化，或者开始 **Phase 5 (The Soma & Memory Layer)** 的探索。考虑到架构路线图的更新，我认为开始构建 **Redis State Backend (5.1)** 是一个激动人心的方向，它将真正开启分布式协作的大门。
