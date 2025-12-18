我将实现里程碑 3.3：速率限制 (Rate Limiting)。这包括在 Runtime 中实现基于令牌桶算法的 `RateLimiter` 和相应的 `RateLimitConstraintHandler`，并更新 `Engine` 和 `ConstraintManager` 以支持基于时间的唤醒机制。同时，我将更新 `cs-controller` CLI 以支持发布速率限制约束。

## [WIP] feat(runtime): Implement Rate Limiting and Time-based Wakeup

### 用户需求
用户需要能够对 Cascade 工作流施加“速率限制”约束（例如，“每分钟最多执行 10 个 API 调用任务”），以防止下游服务过载或由于超出配额而被封禁。

### 评论
速率限制与并发限制不同，它涉及时间维度。这意味着当任务被拒绝时，引擎不能仅仅是被动等待外部事件（如 MQTT 消息）来唤醒，而是需要根据令牌桶的填充时间主动唤醒。这需要对 `ConstraintManager` 和 `Engine` 的协作模式进行增强。

### 目标
1.  在 `cascade-runtime` 中实现 `RateLimiter` 类（令牌桶算法）。
2.  更新 `ConstraintManager`，增加 `request_wakeup(delay)` 能力。
3.  实现 `RateLimitConstraintHandler`，处理 `rate_limit` 类型的约束，并在受限时请求唤醒。
4.  更新 `Engine` 以注册新组件并连接唤醒回调。
5.  更新 `cs-controller` 以支持 `--rate` 参数。

### 基本原理
我们采用标准的令牌桶算法，因为它允许一定的突发流量（burst），这在实际工程中通常比漏桶算法更实用。为了保持架构的解耦，具体的速率限制逻辑封装在 Handler 中，通过 `ConstraintManager` 暴露的通用接口与 Engine 交互。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #comp/cli #concept/constraint #scope/core #ai/instruct #task/domain/runtime #task/object/rate-limiter #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 RateLimiter 组件

我们在 `cascade/runtime/constraints/rate_limiter.py` 中实现核心的令牌桶逻辑。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/constraints/rate_limiter.py
~~~~~
~~~~~python
import time
from typing import Dict, Tuple
from dataclasses import dataclass


@dataclass
class Bucket:
    capacity: float
    tokens: float
    rate: float  # tokens per second
    last_refill: float


class RateLimiter:
    """
    Implements a Token Bucket algorithm for rate limiting.
    Manages multiple independent buckets identified by a key (scope).
    """

    def __init__(self):
        self._buckets: Dict[str, Bucket] = {}

    def update_bucket(self, key: str, rate: float, capacity: float = None):
        """
        Updates or creates a bucket configuration.
        
        Args:
            key: Unique identifier for the bucket.
            rate: Tokens per second.
            capacity: Max tokens. Defaults to rate (i.e., 1 second worth of tokens).
        """
        if capacity is None:
            capacity = rate

        now = time.time()
        
        if key not in self._buckets:
            # Initialize full
            self._buckets[key] = Bucket(
                capacity=capacity,
                tokens=capacity,
                rate=rate,
                last_refill=now
            )
        else:
            # Update existing parameters, keeping current level (clamped)
            b = self._buckets[key]
            # Refill first to be fair
            self._refill(b, now)
            b.rate = rate
            b.capacity = capacity
            b.tokens = min(b.tokens, b.capacity)

    def try_acquire(self, key: str, cost: float = 1.0) -> float:
        """
        Attempts to acquire tokens from the bucket.

        Returns:
            0.0 if successful.
            >0.0 if failed, representing the seconds to wait until enough tokens are available.
        """
        bucket = self._buckets.get(key)
        if not bucket:
            # No limit defined for this key implies infinite tokens
            return 0.0

        now = time.time()
        self._refill(bucket, now)

        if bucket.tokens >= cost:
            bucket.tokens -= cost
            return 0.0
        else:
            # Calculate time to wait
            missing = cost - bucket.tokens
            if bucket.rate <= 0:
                return float("inf") # Should not happen in normal config
            return missing / bucket.rate

    def _refill(self, bucket: Bucket, now: float):
        elapsed = now - bucket.last_refill
        if elapsed > 0:
            added = elapsed * bucket.rate
            bucket.tokens = min(bucket.capacity, bucket.tokens + added)
            bucket.last_refill = now
~~~~~

#### Acts 2: 增强 ConstraintManager

我们需要在 `ConstraintManager` 中添加 `request_wakeup` 方法，允许 Handler 请求未来的唤醒。这需要 `Engine` 注入一个回调。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
~~~~~
~~~~~python
    def __init__(self, resource_manager: ResourceManager):
        self.resource_manager = resource_manager
        # Stores active constraints by their unique ID
        self._constraints: Dict[str, GlobalConstraint] = {}
        # Stores registered handlers by the constraint type they handle
        self._handlers: Dict[str, ConstraintHandler] = {}

    def register_handler(self, handler: ConstraintHandler) -> None:
        """Registers a constraint handler for the type it handles."""
~~~~~
~~~~~python
    def __init__(self, resource_manager: ResourceManager):
        self.resource_manager = resource_manager
        # Stores active constraints by their unique ID
        self._constraints: Dict[str, GlobalConstraint] = {}
        # Stores registered handlers by the constraint type they handle
        self._handlers: Dict[str, ConstraintHandler] = {}
        # Callback to wake up the engine loop
        self._wakeup_callback: Any = None

    def set_wakeup_callback(self, callback: Any) -> None:
        """Sets the callback to trigger an engine wakeup."""
        self._wakeup_callback = callback

    def request_wakeup(self, delay: float) -> None:
        """
        Requests the engine to wake up after a specified delay (in seconds).
        Used by time-based constraints (like rate limits).
        """
        if self._wakeup_callback:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.call_later(delay, self._wakeup_callback)
            except RuntimeError:
                # Fallback if no loop is running (e.g. during sync tests), though less likely in Engine run
                pass

    def register_handler(self, handler: ConstraintHandler) -> None:
        """Registers a constraint handler for the type it handles."""
~~~~~

#### Acts 3: 实现 RateLimitConstraintHandler

我们将实现解析速率字符串（如 "10/m"）和与 `RateLimiter` 交互的 Handler。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
~~~~~
~~~~~python
from .protocols import ConstraintHandler
from cascade.graph.model import Node
from cascade.spec.constraint import GlobalConstraint


if TYPE_CHECKING:
    from .manager import ConstraintManager
~~~~~
~~~~~python
from .protocols import ConstraintHandler
from cascade.graph.model import Node
from cascade.spec.constraint import GlobalConstraint
from .rate_limiter import RateLimiter


if TYPE_CHECKING:
    from .manager import ConstraintManager

def _parse_rate_string(rate_str: str) -> float:
    """Parses '10/m', '5/s', '300/h' into tokens per second."""
    if not isinstance(rate_str, str):
        return float(rate_str)
    
    parts = rate_str.split("/")
    if len(parts) != 2:
        try:
            return float(rate_str)
        except ValueError:
             # Default fallback or error
            return 1.0

    count = float(parts[0])
    unit = parts[1].lower()
    
    divisor = 1.0
    if unit in ("s", "sec", "second"):
        divisor = 1.0
    elif unit in ("m", "min", "minute"):
        divisor = 60.0
    elif unit in ("h", "hr", "hour"):
        divisor = 3600.0
    
    return count / divisor
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
~~~~~
~~~~~python
        if is_match:
            res_name = self._get_resource_name(constraint)
            # We require 1 slot of this concurrency resource
            requirements[res_name] = 1
~~~~~
~~~~~python
        if is_match:
            res_name = self._get_resource_name(constraint)
            # We require 1 slot of this concurrency resource
            requirements[res_name] = 1


class RateLimitConstraintHandler(ConstraintHandler):
    """
    Handles 'rate_limit' constraints using a Token Bucket algorithm.
    """

    def __init__(self):
        self.limiter = RateLimiter()

    def handles_type(self) -> str:
        return "rate_limit"

    def _get_scope_key(self, constraint: GlobalConstraint) -> str:
        return constraint.scope

    def on_constraint_add(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        rate_val = constraint.params.get("rate", "1/s")
        rate_hertz = _parse_rate_string(str(rate_val))
        
        # We can optionally allow users to set burst capacity via params
        # For now, default burst = rate (1 second worth)
        capacity = constraint.params.get("capacity") 
        if capacity is not None:
            capacity = float(capacity)
        
        self.limiter.update_bucket(self._get_scope_key(constraint), rate_hertz, capacity)

    def on_constraint_remove(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        # Currently RateLimiter doesn't support deleting buckets, which is fine.
        # It just won't be used.
        pass

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
        
        if wait_time == 0.0:
            return True
        else:
            # We are rate limited. Request a wakeup when tokens should be available.
            manager.request_wakeup(wait_time)
            return False

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        manager: "ConstraintManager",
    ) -> None:
        pass
~~~~~

#### Acts 4: 更新 Engine

在 Engine 初始化时连接 `_wakeup_event` 并注册新的 Handler。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.runtime.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
)
from cascade.adapters.state import InMemoryStateBackend
~~~~~
~~~~~python
from cascade.runtime.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)
from cascade.adapters.state import InMemoryStateBackend
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(self.resource_manager)
        self.constraint_manager.register_handler(PauseConstraintHandler())
        self.constraint_manager.register_handler(ConcurrencyConstraintHandler())

        self._wakeup_event = asyncio.Event()
~~~~~
~~~~~python
        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(self.resource_manager)
        self.constraint_manager.register_handler(PauseConstraintHandler())
        self.constraint_manager.register_handler(ConcurrencyConstraintHandler())
        self.constraint_manager.register_handler(RateLimitConstraintHandler())

        self._wakeup_event = asyncio.Event()
        self.constraint_manager.set_wakeup_callback(self._wakeup_event.set)
~~~~~

#### Acts 5: 更新 Controller CLI

更新 `set-limit` 命令以支持速率限制参数。

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
async def _publish_limit(scope: str, concurrency: int, hostname: str, port: int):
    """Core logic for publishing a concurrency limit constraint."""
    connector = MqttConnector(hostname=hostname, port=port)
    try:
        bus.info("controller.connecting", hostname=hostname, port=port)
        await connector.connect()
        bus.info("controller.connected")

        constraint_id = f"concurrency-{scope}-{uuid.uuid4().hex[:8]}"
        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="concurrency",
            params={"limit": concurrency},
        )

        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"

        bus.info(
            "controller.publishing_limit", scope=scope, topic=topic, limit=concurrency
        )
        await connector.publish(topic, payload, retain=True)

        await asyncio.sleep(0.1)
        bus.info("controller.publish_limit_success")

    except Exception as e:
        bus.error("controller.error", error=e)
    finally:
        await connector.disconnect()


@app.command()
def set_limit(
    scope: str = typer.Option(
        ...,
        "--scope",
        help="The scope to apply the limit to (e.g., 'global', 'task:api_call').",
    ),
    concurrency: int = typer.Option(
        ..., "--concurrency", help="The maximum number of concurrent tasks."
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'concurrency' constraint to the MQTT broker.
    """
    try:
        asyncio.run(
            _publish_limit(
                scope=scope, concurrency=concurrency, hostname=hostname, port=port
            )
        )
    except KeyboardInterrupt:
        bus.info("observer.shutdown")
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

    except Exception as e:
        bus.error("controller.error", error=e)
    finally:
        await connector.disconnect()


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
    except KeyboardInterrupt:
        bus.info("observer.shutdown")
~~~~~

#### Acts 6: 添加 CLI 消息模板

我们需要为新的速率限制消息添加模板。

~~~~~act
patch_file
packages/cascade-common/src/cascade/common/locales/en/cli_messages.json
~~~~~
~~~~~json
    "controller.publishing": "📡 Publishing 'pause' constraint for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.publish_success": "✅ Pause constraint published successfully.",
    "controller.publishing_limit": "📡 Publishing concurrency limit of [bold magenta]{limit}[/bold magenta] for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.publish_limit_success": "✅ Concurrency limit published successfully.",
    "controller.resuming": "📡 Publishing resume command for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.resume_success": "✅ Resume command published successfully.",
~~~~~
~~~~~json
    "controller.publishing": "📡 Publishing 'pause' constraint for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.publish_success": "✅ Pause constraint published successfully.",
    "controller.publishing_limit": "📡 Publishing concurrency limit of [bold magenta]{limit}[/bold magenta] for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.publishing_rate": "📡 Publishing rate limit of [bold magenta]{rate}[/bold magenta] for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.publish_limit_success": "✅ Limits published successfully.",
    "controller.resuming": "📡 Publishing resume command for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.resume_success": "✅ Resume command published successfully.",
~~~~~
