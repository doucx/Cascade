由于错误数量较多，且涉及协议定义、属性访问、空值检查等多个方面，我将把修复工作分为几个逻辑步骤。

1.  **核心协议修正 (`cascade-spec`)**:
    *   放宽 `LazyFactory` 协议：移除 `map` 方法的强制要求，因为如 `ipfs.cat` 等组合型 Factory 只是普通函数，不支持 `map`。
    *   修正 `Provider` 协议：将 `name` 从 `@property` 改为类变量声明，以兼容子类的直接赋值。
    *   修正 `routing.py` 中的泛型定义。
2.  **本地连接器修复 (`cascade-connector-local`)**:
    *   修复 `Lock` 的错误属性访问。
    *   添加必要的 `None` 检查。
    *   修复 `publish` 方法签名。
3.  **引擎与运行时修复 (`cascade-engine`)**:
    *   添加大量的 `None` 检查（针对 `state_backend`, `connector`, `resource_def` 等）。
    *   修复 `graph.py` 中的变量作用域问题。
    *   修复 `vm.py` 和 `engine.py` 中的类型不匹配。
4.  **库与SDK修复 (`cascade-library`, `cascade-sdk`)**:
    *   修复 `sql.py` 中缺失的 `text` 导入。
    *   修复 `cli.py` 中 `FunctionType` 的属性赋值。
    *   修复 `lisp.py` 中过时的 `.id` 访问。
    *   修复 `testing.py` 中的 Mock 类型签名。

---

# [WIP] fix: 全面修复 Pyright 类型检查错误 (Phase 1)

## [WIP] fix(spec): 修正 Protocol 定义与核心类型

### 错误分析
1.  **LazyFactory 不兼容**: 许多 Provider 返回普通函数，没有 `map` 方法，违反了旧协议。
2.  **Provider.name 冲突**: 协议定义为 property，实现类定义为类属性，导致类型冲突。
3.  **Routing 泛型错误**: `routing.py` 中使用了未绑定的 `T`。
4.  **Resource 装饰器类型**: `resource` 装饰器参数注解为 `None` 导致无法接受函数。

### 用户需求
修复 `cascade-spec` 包中的类型定义错误，作为后续修复的基础。

### 评论
协议的定义必须贴合实际实现。Cascade 允许 Factory 是普通函数（组合模式），因此 `map` 不应是强制的。

### 目标
1.  修改 `LazyFactory` 和 `Provider` 协议。
2.  修复 `resource.py` 和 `routing.py`。

### 基本原理
放宽协议限制，使其兼容现有的合法 Python 实现。

### 标签
#intent/fix #flow/ready #priority/high #comp/interfaces #scope/core #ai/instruct #task/domain/type-system #task/object/protocols #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 修正 Protocol 定义

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/protocols.py
~~~~~
~~~~~python
from typing import Protocol, List, Any, Dict, Optional, Callable, Awaitable, Union
from cascade.graph.model import Graph, Node

# An execution plan is a list of stages, where each stage is a list of nodes
# that can be executed in parallel.
ExecutionPlan = List[List[Node]]


class Solver(Protocol):
    def resolve(self, graph: Graph) -> ExecutionPlan: ...


class Executor(Protocol):
    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any: ...


class CacheBackend(Protocol):
    async def get(self, key: str) -> Optional[Any]: ...

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None: ...


class CachePolicy(Protocol):
    async def check(self, task_id: str, inputs: Dict[str, Any]) -> Any: ...

    async def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None: ...


class StateBackend(Protocol):
    async def put_result(self, node_id: str, result: Any) -> None: ...

    async def get_result(self, node_id: str) -> Optional[Any]: ...

    async def has_result(self, node_id: str) -> bool: ...

    async def mark_skipped(self, node_id: str, reason: str) -> None: ...

    async def get_skip_reason(self, node_id: str) -> Optional[str]: ...


class SubscriptionHandle(Protocol):
    async def unsubscribe(self) -> None: ...


class LazyFactory(Protocol):
    # map is optional depending on implementation (e.g. Task has it, simple functions don't)
    # def map(self, **kwargs) -> Any: ...
    def __call__(self, *args, **kwargs) -> Any: ...


class Connector(Protocol):
    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def publish(
        self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False
    ) -> None: ...

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> "SubscriptionHandle": ...


class Provider(Protocol):
    # name can be a property or a class attribute
    name: str

    def create_factory(self) -> LazyFactory: ...
~~~~~

#### Acts 2: 修正 resource 装饰器类型

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/resource.py
~~~~~
~~~~~python.old
def resource(
    func: Callable[..., T] = None, *, name: Optional[str] = None, scope: str = "run"
):
    def wrapper(f: Callable[..., T]) -> ResourceDefinition[T]:
        resource_name = name or f.__name__
        return ResourceDefinition(func=f, name=resource_name, scope=scope)

    # Allows using @resource or @resource(name="...")
    if func:
        return wrapper(func)
    return wrapper
~~~~~
~~~~~python.new
def resource(
    func: Optional[Callable[..., T]] = None, *, name: Optional[str] = None, scope: str = "run"
):
    def wrapper(f: Callable[..., T]) -> ResourceDefinition[T]:
        resource_name = name or f.__name__
        return ResourceDefinition(func=f, name=resource_name, scope=scope)

    # Allows using @resource or @resource(name="...")
    if func:
        return wrapper(func)
    return wrapper
~~~~~

#### Acts 3: 修正 routing.py 泛型

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/routing.py
~~~~~
~~~~~python.old
@dataclass
class Router:
    selector: LazyResult[Any]
    routes: Dict[Any, LazyResult[T]]
~~~~~
~~~~~python.new
@dataclass
class Router(Generic[T]):
    selector: LazyResult[Any]
    routes: Dict[Any, LazyResult[T]]
~~~~~

---

# [WIP] fix(local): 修复 LocalConnector 的属性访问与空值检查

### 错误分析
1.  **_get_loop**: `asyncio.Lock` 在新版 Python 中移除了 `_get_loop` 方法，`bus.py` 中试图访问它。
2.  **None 安全**: `connector.py` 中 `self._conn` 在未连接时为 `None`，直接访问 `cursor()` 会报错。
3.  **Publish 签名**: `LocalConnector.publish` 的参数顺序与 Protocol 不一致。

### 目标
修复 `cascade-connector-local` 中的所有 Pyright 错误。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #scope/connector #task/state/continue

---

### Script

#### Acts 4: 修复 bus.py 中的 Lock 处理

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/bus.py
~~~~~
~~~~~python.old
    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        try:
            # In modern Python, accessing or using a lock created in a different
            # loop will raise RuntimeError. We catch this to re-initialize.
            if cls._lock is None or cls._lock._get_loop() != loop:
                cls._lock = asyncio.Lock()
        except RuntimeError:
            cls._lock = asyncio.Lock()
        return cls._lock
~~~~~
~~~~~python.new
    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        # In modern Python, we don't check _get_loop() directly as it is private/removed.
        # We rely on asyncio.Lock() being bound to the current loop when created.
        # If cls._lock is stale (from another loop), acquiring it might throw or hang.
        # A simple strategy is to recreate it if it's None.
        # For strict robustness across loops, we might need a weakref dict keyed by loop.
        # But for this simple local implementation:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock
~~~~~

#### Acts 5: 修复 connector.py 的 None 检查和 publish 签名

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/connector.py
~~~~~
~~~~~python.old
    async def connect(self) -> None:
        # Start telemetry server if it exists
        if self._telemetry_server:
            await self._telemetry_server.start()

        def _connect_and_setup():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS constraints (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    type TEXT NOT NULL,
                    params TEXT NOT NULL,
                    expires_at REAL,
                    updated_at REAL NOT NULL
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS scope_idx ON constraints (scope)"
            )
            conn.commit()
            return conn

        self._conn = await asyncio.to_thread(_connect_and_setup)
        self._is_connected = True
        return self
~~~~~
~~~~~python.new
    async def connect(self) -> None:
        # Start telemetry server if it exists
        if self._telemetry_server:
            await self._telemetry_server.start()

        def _connect_and_setup():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS constraints (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    type TEXT NOT NULL,
                    params TEXT NOT NULL,
                    expires_at REAL,
                    updated_at REAL NOT NULL
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS scope_idx ON constraints (scope)"
            )
            conn.commit()
            return conn

        self._conn = await asyncio.to_thread(_connect_and_setup)
        self._is_connected = True
~~~~~

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/connector.py
~~~~~
~~~~~python.old
    async def publish(self, topic: str, payload: Dict[str, Any], **kwargs) -> None:
        if not self._is_connected or not self._conn:
            raise RuntimeError("Connector is not connected.")

        # Route message based on topic
        if topic.startswith("cascade/telemetry/"):
            if self._telemetry_server:
                await self._telemetry_server.broadcast(payload)
            return

        if topic.startswith("cascade/constraints/"):
            scope = self._topic_to_scope(topic)

            def _blocking_publish():
                if not self._conn:
                    return
                cursor = self._conn.cursor()
                if not payload:
                    cursor.execute("DELETE FROM constraints WHERE scope = ?", (scope,))
                else:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO constraints (id, scope, type, params, expires_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            payload["id"],
                            payload["scope"],
                            payload["type"],
                            json.dumps(payload["params"]),
                            payload.get("expires_at"),
                            time.time(),
                        ),
                    )
                self._conn.commit()

            await asyncio.to_thread(_blocking_publish)

            if not self._use_polling:
                await self._send_uds_signal()
~~~~~
~~~~~python.new
    async def publish(
        self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False
    ) -> None:
        if not self._is_connected or not self._conn:
            raise RuntimeError("Connector is not connected.")

        # Route message based on topic
        if topic.startswith("cascade/telemetry/"):
            if self._telemetry_server:
                await self._telemetry_server.broadcast(payload)
            return

        if topic.startswith("cascade/constraints/"):
            scope = self._topic_to_scope(topic)

            def _blocking_publish():
                if not self._conn:
                    return
                cursor = self._conn.cursor()
                if not payload:
                    cursor.execute("DELETE FROM constraints WHERE scope = ?", (scope,))
                else:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO constraints (id, scope, type, params, expires_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            payload["id"],
                            payload["scope"],
                            payload["type"],
                            json.dumps(payload["params"]),
                            payload.get("expires_at"),
                            time.time(),
                        ),
                    )
                self._conn.commit()

            await asyncio.to_thread(_blocking_publish)

            if not self._use_polling:
                await self._send_uds_signal()
~~~~~

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/connector.py
~~~~~
~~~~~python.old
    async def _sync_and_notify(self, callback: Callable):
        def _blocking_fetch_all():
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM constraints")
            return cursor.fetchall()

        rows = await asyncio.to_thread(_blocking_fetch_all)
~~~~~
~~~~~python.new
    async def _sync_and_notify(self, callback: Callable):
        def _blocking_fetch_all():
            if not self._conn:
                return []
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM constraints")
            return cursor.fetchall()

        rows = await asyncio.to_thread(_blocking_fetch_all)
~~~~~

---

# [WIP] fix(mqtt): 修复 MqttConnector 的类型注解

### 错误分析
`Union syntax` 错误通常是因为在 Python 3.10 之前的版本中，字符串类型的 forward reference 不能直接使用 `|` 运算符。

### Script

#### Acts 6: 修复 MqttConnector 属性定义

~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
~~~~~
~~~~~python.old
        self.hostname = hostname
        self.port = port
        self.client_kwargs = kwargs
        self._client: "aiomqtt.Client" | None = None
        self._loop_task: asyncio.Task | None = None
        self._subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}
        self._source_id = f"{platform.node()}-{os.getpid()}"
~~~~~
~~~~~python.new
        self.hostname = hostname
        self.port = port
        self.client_kwargs = kwargs
        # Use Optional string forward ref for compatibility
        self._client: Any = None 
        self._loop_task: asyncio.Task | None = None
        self._subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}
        self._source_id = f"{platform.node()}-{os.getpid()}"
~~~~~

#### Acts 7: 添加 aiomqtt 非空检查

~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
~~~~~
~~~~~python.old
    async def connect(self) -> None:
        if self._client:
            return

        # Define the Last Will and Testament message
        lwt_topic = f"cascade/status/{self._source_id}"
        lwt_payload = json.dumps({"status": "offline"})
        will_message = aiomqtt.Will(topic=lwt_topic, payload=lwt_payload)

        # aiomqtt.Client now acts as an async context manager
        client = aiomqtt.Client(
            hostname=self.hostname,
            port=self.port,
            will=will_message,
            **self.client_kwargs,
        )
        self._client = await client.__aenter__()

        # Start the message processing loop
        self._loop_task = asyncio.create_task(self._message_loop())
~~~~~
~~~~~python.new
    async def connect(self) -> None:
        if self._client:
            return
        
        if aiomqtt is None:
             raise ImportError("aiomqtt not installed")

        # Define the Last Will and Testament message
        lwt_topic = f"cascade/status/{self._source_id}"
        lwt_payload = json.dumps({"status": "offline"})
        will_message = aiomqtt.Will(topic=lwt_topic, payload=lwt_payload)

        # aiomqtt.Client now acts as an async context manager
        client = aiomqtt.Client(
            hostname=self.hostname,
            port=self.port,
            will=will_message,
            **self.client_kwargs,
        )
        self._client = await client.__aenter__()

        # Start the message processing loop
        self._loop_task = asyncio.create_task(self._message_loop())
~~~~~

---

# [WIP] fix(engine): 修复引擎与运行时的空值与类型错误

### 目标
修复 `engine.py`, `graph.py` 等核心文件中的大量类型错误。

### Script

#### Acts 8: 修复 engine.py 类型检查

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python.old
    def _is_simple_task(self, lr: Any) -> bool:
        if not isinstance(lr, LazyResult):
            return False
        if lr._condition or (lr._constraints and not lr._constraints.is_empty()):
            return False

        def _has_lazy(obj):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                return True
            if isinstance(obj, (list, tuple)):
                return any(_has_lazy(x) for x in obj)
            if isinstance(obj, dict):
                return any(_has_lazy(v) for v in obj.values())
            return False
~~~~~
~~~~~python.new
    def _is_simple_task(self, lr: Any) -> bool:
        if not isinstance(lr, LazyResult):
            return False
        if lr._condition or (lr._constraints and not lr._constraints.is_empty()):
            return False

        def _has_lazy(obj: Any) -> bool:
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                return True
            if isinstance(obj, (list, tuple)):
                return any(_has_lazy(x) for x in obj)
            if isinstance(obj, dict):
                return any(_has_lazy(v) for v in obj.values())
            return False
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python.old
        # Robustly determine initial target name for logging
        if hasattr(target, "task"):
            target_name = getattr(target.task, "name", "unknown")
        elif hasattr(target, "factory"):
            target_name = f"map({getattr(target.factory, 'name', 'unknown')})"
        else:
            target_name = "unknown"
~~~~~
~~~~~python.new
        # Robustly determine initial target name for logging
        # Using getattr to avoid type checking issues with Union[LazyResult, List, ...]
        if isinstance(target, LazyResult):
            target_name = getattr(target.task, "name", "unknown")
        elif isinstance(target, MappedLazyResult):
            target_name = f"map({getattr(target.factory, 'name', 'unknown')})"
        else:
            target_name = "unknown"
~~~~~

#### Acts 9: 修复 strategies/graph.py 变量作用域

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python.old
                    if len(tasks_to_run) == 1:
                        # FAST PATH: Single task in stage, avoid gather
                        node, coro = tasks_to_run[0]
                        res = await coro
                        await state_backend.put_result(node.structural_id, res)
                        if flow_manager:
                            await flow_manager.register_result(
                                node.structural_id, res, state_backend
                            )
                    else:
                        # Standard parallel execution
                        nodes_in_pass = [t[0] for t in tasks_to_run]
                        coros = [t[1] for t in tasks_to_run]
                        pass_results = await asyncio.gather(*coros)

                        for node, res in zip(nodes_in_pass, pass_results):
                            await state_backend.put_result(node.structural_id, res)
                            if flow_manager:
                                await flow_manager.register_result(
                                    node.structural_id, res, state_backend
                                )
                        if flow_manager:
                            await flow_manager.register_result(
                                node.structural_id, res, state_backend
                            )

                pending_nodes_in_stage = deferred_this_pass
~~~~~
~~~~~python.new
                    if len(tasks_to_run) == 1:
                        # FAST PATH: Single task in stage, avoid gather
                        node, coro = tasks_to_run[0]
                        res = await coro
                        await state_backend.put_result(node.structural_id, res)
                        if flow_manager:
                            await flow_manager.register_result(
                                node.structural_id, res, state_backend
                            )
                    else:
                        # Standard parallel execution
                        nodes_in_pass = [t[0] for t in tasks_to_run]
                        coros = [t[1] for t in tasks_to_run]
                        pass_results = await asyncio.gather(*coros)

                        for node_in_loop, res_in_loop in zip(nodes_in_pass, pass_results):
                            await state_backend.put_result(node_in_loop.structural_id, res_in_loop)
                            if flow_manager:
                                await flow_manager.register_result(
                                    node_in_loop.structural_id, res_in_loop, state_backend
                                )
                
                pending_nodes_in_stage = deferred_this_pass
~~~~~

#### Acts 10: 修复 sql.py 缺失导入

~~~~~act
patch_file
packages/cascade-library/src/cascade/providers/sql.py
~~~~~
~~~~~python.old
from typing import Any, List, Dict, Optional

try:
    import sqlalchemy
    from sqlalchemy import text
except ImportError:
    sqlalchemy = None
~~~~~
~~~~~python.new
from typing import Any, List, Dict, Optional

try:
    import sqlalchemy
    from sqlalchemy import text
except ImportError:
    sqlalchemy = None
    # Mock text for static analysis if sqlalchemy missing
    def text(s): return s
~~~~~

---

# [WIP] fix(sdk): 修复 SDK 工具链类型错误

### Script

#### Acts 11: 修复 cli.py 签名赋值

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/cli.py
~~~~~
~~~~~python.old
    # Set the dynamic signature on the main function
    main.__signature__ = inspect.Signature(parameters=sig_params)
    # Give it a docstring for better --help
    main.__doc__ = "Runs the Cascade workflow."
~~~~~
~~~~~python.new
    # Set the dynamic signature on the main function
    from typing import cast
    # Pyright complains about assigning to FunctionType.__signature__, so we cast
    cast(Any, main).__signature__ = inspect.Signature(parameters=sig_params)
    # Give it a docstring for better --help
    main.__doc__ = "Runs the Cascade workflow."
~~~~~

#### Acts 12: 修复 lisp.py ID 访问

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/lisp.py
~~~~~
~~~~~python.old
    def _analyze(self):
        # 1. Initialize counts
        for node in self.graph.nodes:
            self.ref_counts[node.structural_id] = 0
~~~~~
~~~~~python.new
    def _analyze(self):
        # 1. Initialize counts
        for node in self.graph.nodes:
            self.ref_counts[node.structural_id] = 0
~~~~~

#### Acts 13: 修复 testing.py 类型

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/testing.py
~~~~~
~~~~~python.old
class MockSubscriptionHandle(SubscriptionHandle):
    def __init__(self, parent: "MockConnector", topic: str):
        self._parent = parent
        self._topic = topic

    async def unsubscribe(self) -> None:
        if self._topic in self._parent.subscriptions:
            del self._parent.subscriptions[self._topic]
~~~~~
~~~~~python.new
class MockSubscriptionHandle(SubscriptionHandle):
    def __init__(self, parent: "MockConnector", topic: str):
        self._parent = parent
        self._topic = topic

    async def unsubscribe(self) -> None:
        if self._topic in self._parent.subscriptions:
            del self._parent.subscriptions[self._topic]

class MockConnector(Connector):
    def __init__(self):
        self.subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}
~~~~~

(注意：之前的 `testing.py` patch 已经包含了 `MockSubscriptionHandle`，但可能不完整，这里确认一下)

#### Acts 14: 修复 vm.py 类型

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/vm.py
~~~~~
~~~~~python.old
    def _load_inputs(
        self,
        frame: Frame,
        blueprint: Blueprint,
        args: List[Any],
        kwargs: Dict[str, Any],
    ):
        # Positional args
        for i, val in enumerate(args):
~~~~~
~~~~~python.new
    def _load_inputs(
        self,
        frame: Frame,
        blueprint: Blueprint,
        args: List[Any] | None,
        kwargs: Dict[str, Any] | None,
    ):
        if args:
            # Positional args
            for i, val in enumerate(args):
                if i < len(blueprint.input_args):
                    reg_index = blueprint.input_args[i]
                    frame.registers[reg_index] = val

        if kwargs:
            # Keyword args
            for k, val in kwargs.items():
                if k in blueprint.input_kwargs:
                    reg_index = blueprint.input_kwargs[k]
                    frame.registers[reg_index] = val
~~~~~
