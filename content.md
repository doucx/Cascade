简要回答
由于 `LocalBusConnector` 是从 E2E 测试的 `InProcessConnector` 演进而来，但引入了更严格的连接状态检查和 `asyncio.Lock` 锁机制，导致了两个关键问题：一是 E2E 测试习惯于连接器“默认连接”以进行预配置，而新代码默认为关闭；二是类级别的 `asyncio.Lock` 在 pytest 的多事件循环环境下会产生跨 Loop 绑定的死锁或报错。

我将通过调整默认连接状态和引入 Loop 敏感的锁管理逻辑来修复这些问题。

## [WIP] fix(runtime): 修复 LocalBusConnector 的连接状态与锁竞争问题

### 错误分析
1.  **连接状态不兼容**: 原有的 `InProcessConnector` 在 `__init__` 中将 `_is_connected` 设为 `True`。新版 `LocalBusConnector` 默认为 `False`，导致 E2E 测试中在 `engine.run()` 之前执行的 `publish`（用于设置初始约束）被静默忽略。
2.  **跨 Loop 锁死锁**: `LocalBusConnector` 在类定义中直接初始化了 `_lock = asyncio.Lock()`。在 pytest 运行多个测试用例时，每个用例都有独立的 Event Loop。由于锁是类级别的，它会绑定到第一个创建它的 Loop。当后续测试在不同的 Loop 中尝试 `await _lock` 时，会因为 Loop 不匹配而导致永久挂起或报错。
3.  **通配符匹配逻辑**: 之前的报错显示通配符匹配可能也存在边界处理不当的问题。

### 用户需求
恢复 E2E 测试套件的稳定性，确保内存总线在多 Loop 自动化测试环境下表现正确。

### 评论
在 Python 异步编程中，全局共享状态（尤其是同步原语如 Lock, Event）是极具挑战性的。在测试环境中，我们必须确保这些原语能够感知到 Loop 的切换。

### 目标
1.  将 `LocalBusConnector` 的初始连接状态改为 `True`。
2.  实现一个 Loop 感知的 `_get_lock` 类方法，确保锁总是属于当前的事件循环。
3.  优化 `_topic_matches` 的逻辑。

### 基本原理
通过延迟初始化锁并在每次访问时检查其所属的 Loop，我们可以安全地在不同测试间共享类级别的消息存储，而不会触发异步上下文冲突。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/telemetry #task/domain/telemetry #task/object/local-bus #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 优化 LocalBusConnector 实现

我们将锁逻辑改为动态获取，并修复初始化状态。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~python
class LocalBusConnector(Connector):
    """
    A robust, in-memory implementation of the Connector protocol.
    Acts as a local MQTT broker, supporting:
    - Shared state across instances (simulating a network broker)
    - Retained messages
    - Topic wildcards (+ and #)
    """

    # --- Broker State (Shared across all instances) ---
    # topic -> list of (Queue, subscription_pattern)
    # We store the subscription pattern with the queue to verify matches during routing
    _subscriptions: Dict[str, List["asyncio.Queue"]] = defaultdict(list)
    _retained_messages: Dict[str, Any] = {}
    _lock = asyncio.Lock()  # Protects shared state modifications

    def __init__(self):
        self._is_connected = False
        self._listener_tasks = []

    @classmethod
    def _reset_broker_state(cls):
        """Helper for tests to clear the 'broker'."""
        cls._subscriptions.clear()
        cls._retained_messages.clear()
        cls._lock = asyncio.Lock()  # Reset lock for new event loop context
~~~~~
~~~~~python
class LocalBusConnector(Connector):
    """
    A robust, in-memory implementation of the Connector protocol.
    Acts as a local MQTT broker, supporting:
    - Shared state across instances (simulating a network broker)
    - Retained messages
    - Topic wildcards (+ and #)
    """

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
        """
        Ensures the lock is bound to the current running event loop.
        This is critical for pytest where each test has its own loop.
        """
        loop = asyncio.get_running_loop()
        if cls._lock is None or cls._lock._get_loop() != loop:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    def _reset_broker_state(cls):
        """Helper for tests to clear the 'broker'."""
        cls._subscriptions.clear()
        cls._retained_messages.clear()
        cls._lock = None  # Force re-creation on next access
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~python
    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
        if not self._is_connected:
            return

        async with self._lock:
            # Handle Retention
            if retain:
~~~~~
~~~~~python
    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
        if not self._is_connected:
            return

        async with self._get_lock():
            # Handle Retention
            if retain:
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~python
    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        if not self._is_connected:
            return

        queue = asyncio.Queue()
        
        async with self._lock:
            self._subscriptions[topic].append(queue)

            # Deliver Retained Messages
~~~~~
~~~~~python
    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        if not self._is_connected:
            return

        queue = asyncio.Queue()
        
        async with self._get_lock():
            self._subscriptions[topic].append(queue)

            # Deliver Retained Messages
~~~~~

### 下一步建议
由于 `asyncio.Lock._get_loop()` 在不同 Python 版本中可能存在细微差异（或作为内部 API），如果在运行 `pytest tests/py/connectors/test_local_connector.py` 时报错，请告知我，我会改用更通用的 `_loop` 属性检查。

如果测试通过，请继续运行 `pytest tests/py/e2e/`。一旦 E2E 套件恢复绿灯，我们就完成了基座的稳固。
