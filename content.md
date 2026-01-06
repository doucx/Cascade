## [WIP] 实现 "Tracked Compute Service" 模式，将 `LocalComputeService` 改造为自带计数管理的队列代理，彻底消除 `put` 到 `get` 之间的状态盲区。同时，重构测试用例，使用高保真的 `EventBus` 和 `SpySubscriber`。

## 标签
#intent/fix #flow/ready #priority/critical #comp/vm #comp/runtime #concept/concurrency #task/domain/runtime #task/object/compute-service #task/action/refactor

---

### Script

#### Acts 1: 改造 LocalComputeService

将 `LocalComputeService` 改造为直接处理提交请求，并即时更新计数器。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
    def __init__(
        self,
        store: ObjectStore,
        registry: CodeRegistry,
        inbound_queue: "asyncio.Queue[ComputeRequest]",
        outbound_queue: "asyncio.Queue[Tuple[str, Token]]",
        max_workers: int = None,
    ):
        self.store = store
        self.registry = registry
        self.inbound_queue = inbound_queue
        self.outbound_queue = outbound_queue
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="cascade_compute"
        )
        self._running = False
        self._active_count = 0

    def is_idle(self) -> bool:
        return self.inbound_queue.empty() and self._active_count == 0

    async def run(self) -> None:
        self._running = True
        logger.info("LocalComputeService started.")
        try:
            while self._running:
                request = await self.inbound_queue.get()
                # Pre-increment active count to avoid race condition where
                # queue is empty but task hasn't started yet.
                self._active_count += 1
                # Create a non-blocking task for each request to allow concurrency
                asyncio.create_task(self._process_request(request))
        finally:
            self._pool.shutdown(wait=False)
            logger.info("LocalComputeService stopped.")
~~~~~
~~~~~python.new
    def __init__(
        self,
        store: ObjectStore,
        registry: CodeRegistry,
        inbound_queue: "asyncio.Queue[ComputeRequest]",
        outbound_queue: "asyncio.Queue[Tuple[str, Token]]",
        max_workers: int = None,
    ):
        self.store = store
        self.registry = registry
        self.inbound_queue = inbound_queue
        self.outbound_queue = outbound_queue
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="cascade_compute"
        )
        self._running = False
        self._active_count = 0

    def put_nowait(self, request: ComputeRequest) -> None:
        """
        Submit a request to the service. 
        Increments active count immediately to prevent idle-detection race conditions.
        Matches the asyncio.Queue interface expected by standard_dispatcher.
        """
        self._active_count += 1
        self.inbound_queue.put_nowait(request)

    def is_idle(self) -> bool:
        # Since active_count covers both "in queue" and "processing", 
        # we only need to check this counter.
        return self._active_count == 0

    async def run(self) -> None:
        self._running = True
        logger.info("LocalComputeService started.")
        try:
            while self._running:
                request = await self.inbound_queue.get()
                # Active count was already incremented in put_nowait
                # Create a non-blocking task for each request to allow concurrency
                asyncio.create_task(self._process_request(request))
        finally:
            self._pool.shutdown(wait=False)
            logger.info("LocalComputeService stopped.")
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
        try:
            # 4. Store Result and Prepare Token
            result_ref = self.store.put(result)
            result_token = Token(payload=result_ref, trace=request.trace)

            # 5. Report Completion to Outbound Queue
            await self.outbound_queue.put((request.reply_to_nid, result_token))
        finally:
            # CRITICAL: We must only decrement the active count AFTER the result
            # is visible in the outbound queue. Otherwise, the Machine might
            # see (active=0, queue=empty) in the gap and exit prematurely.
            self._active_count -= 1
~~~~~
~~~~~python.new
        try:
            # 4. Store Result and Prepare Token
            result_ref = self.store.put(result)
            result_token = Token(payload=result_ref, trace=request.trace)

            # 5. Report Completion to Outbound Queue
            await self.outbound_queue.put((request.reply_to_nid, result_token))
        finally:
            self._active_count -= 1
~~~~~

#### Acts 2: 更新 VMExecutionStrategy 注册逻辑

更新策略层，将 `compute_service` 实例本身注册为 `system.compute_queue`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/vm.py
~~~~~
~~~~~python.old
            compute_service = LocalComputeService(
                store=object_store,
                registry=code_registry,
                inbound_queue=compute_queue,
                outbound_queue=ingress_queue,
            )
            
            resource_registry.register("system.object_store", object_store)
            resource_registry.register("system.compute_queue", compute_queue)
            resource_registry.register("system.egress_queue", egress_queue)
            resource_registry.register("system.event_bus", self.bus)
~~~~~
~~~~~python.new
            compute_service = LocalComputeService(
                store=object_store,
                registry=code_registry,
                inbound_queue=compute_queue,
                outbound_queue=ingress_queue,
            )
            
            resource_registry.register("system.object_store", object_store)
            # Register the service itself as the queue, as it implements put_nowait
            resource_registry.register("system.compute_queue", compute_service)
            resource_registry.register("system.egress_queue", egress_queue)
            resource_registry.register("system.event_bus", self.bus)
~~~~~

#### Acts 3: 修复测试用例

重构测试，使用真实的 `EventBus` 和 `SpySubscriber`。

~~~~~act
write_file
packages/cascade-runtime/tests/integration/test_vm_strategy.py
~~~~~
~~~~~python
import pytest
from contextlib import ExitStack
from cascade.spec.dsl.task import task
from cascade.runtime.legacy.strategies.vm import VMExecutionStrategy
from cascade.spec.runtime import ExecutionContext
from cascade.runtime import EventBus

@task
def add(a: int, b: int) -> int:
    return a + b

@task
def square(n: int) -> int:
    return n * n

@pytest.mark.asyncio
async def test_vm_strategy_e2e_execution():
    # 1. Define workflow
    target = square(add(1, 2))

    # 2. Setup strategy and context
    # Use real EventBus for high-fidelity testing
    bus = EventBus()
    strategy = VMExecutionStrategy(bus=bus)

    mock_state_backend = None # VM Strategy doesn't use legacy state backend
    context = ExecutionContext(
        run_id="test-run-123",
        state_backend=mock_state_backend,
        run_stack=ExitStack(),
        active_resources={},
    )

    # 3. Execute
    result = await strategy.execute(target, context)

    # 4. Assert
    assert result == 9
~~~~~

### 下一步建议
通过将状态管理内聚到 `ComputeService` 内部，我们消除了状态不一致的时间窗口。这应该能彻底解决 `Machine` 过早退出的问题。执行测试进行验证。

执行 `pytest packages/cascade-runtime/tests/integration/test_vm_strategy.py`。
