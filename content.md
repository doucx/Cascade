好的，我们来解决 `Machine` 的低效轮询问题。

当前的实现通过 `asyncio.sleep(0.001)` 进行忙等，这在系统空闲时会持续消耗 CPU 周期。我们将用一个真正的事件驱动机制来取代它，以实现更高的效率。

## [WIP] refactor(vm): 将 Machine 中的轮询休眠替换为事件驱动等待

### 用户需求
*   **债务**: `Machine` 在空闲时使用 `asyncio.sleep(0.001)` 进行轮询。这比之前的 `break` 要好，但仍然是低效的“忙等”。
*   **影响**: 在系统真正空闲时，它仍然会每毫秒消耗一次 CPU 周期来检查队列。
*   **偿还路径**: 引入 `asyncio.Condition` 或 `asyncio.Event`。`Reactor` 在 `_process_ingress` 成功处理一个项目后 `set()` 事件，`Machine` 在 `fired_count == 0` 时 `await` 这个事件，从而实现真正的事件驱动调度，避免轮询。

### 评论
用 `asyncio.Event` 替换 `asyncio.sleep` 是一个标准的、正确的异步设计模式。它将使 `Machine` 的主循环在系统真正静止时完全挂起，将 CPU 资源让给其他任务，并在有新工作（计算结果返回）到达时立即被唤醒，从而兼顾了低延迟和低资源消耗。

### 目标
1.  引入一个 `asyncio.Event` (`wakeup_event`) 作为 `Machine` 和 `LocalComputeService` 之间的通信信标。
2.  修改 `LocalComputeService`，使其在向 `ingress_queue` 放入新结果后，立即设置此事件。
3.  修改 `Machine` 的主循环，使其在系统空闲时 `await` 此事件，而不是固定时间的 `sleep`。
4.  更新 `EventDrivenRunner` 和相关集成测试，以正确创建和传递这个新的 `wakeup_event`。

### 基本原理
我们将建立一个清晰的生产者-消费者信号模型：
-   **生产者**: `LocalComputeService` 在完成计算并将结果放入 `ingress_queue` 后，它扮演了“新工作”生产者的角色。
-   **消费者**: `Machine` 的主循环是工作的消费者。
-   **信号**: `wakeup_event` 是连接两者的信号。当 `Machine` 发现系统（`Reactor` 和 `ingress_queue`）暂时空闲时，它会等待 `wakeup_event`。当 `LocalComputeService` 生产了新工作时，它会设置该事件，从而精确地唤醒 `Machine`，避免了无效轮询。

### 标签
#intent/refine #flow/ready #priority/medium #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/runtime #task/object/event-loop #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修改 `LocalComputeService` 以接受并设置唤醒事件

我们将更新其构造函数和 `_process_request` 方法。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
class LocalComputeService:
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
~~~~~
~~~~~python.new
class LocalComputeService:
    def __init__(
        self,
        store: ObjectStore,
        registry: CodeRegistry,
        inbound_queue: "asyncio.Queue[ComputeRequest]",
        outbound_queue: "asyncio.Queue[Tuple[str, Token]]",
        max_workers: int = None,
        wakeup_event: Optional[asyncio.Event] = None,
    ):
        self.store = store
        self.registry = registry
        self.inbound_queue = inbound_queue
        self.outbound_queue = outbound_queue
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="cascade_compute"
        )
        self._wakeup_event = wakeup_event
        self._running = False
        self._active_count = 0
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
        # 5. Report Completion to Outbound Queue
        await self.outbound_queue.put((request.reply_to_nid, result_token))
~~~~~
~~~~~python.new
        # 5. Report Completion to Outbound Queue
        await self.outbound_queue.put((request.reply_to_nid, result_token))

        # 6. Signal that new work is available
        if self._wakeup_event:
            self._wakeup_event.set()
~~~~~

#### Acts 2: 更新 `Machine` 以使用事件等待

修改 `Machine` 的构造函数和 `run` 循环。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
class Machine:
    def __init__(
        self,
        reactor: Reactor,
        compute_service: LocalComputeService,
        ingress_queue: "asyncio.Queue[Tuple[str, Token]]",
    ):
        self.reactor = reactor
        self.compute_service = compute_service
        self.ingress_queue = ingress_queue

    async def run(self) -> None:
~~~~~
~~~~~python.new
class Machine:
    def __init__(
        self,
        reactor: Reactor,
        compute_service: LocalComputeService,
        wakeup_event: asyncio.Event,
    ):
        self.reactor = reactor
        self.compute_service = compute_service
        self.wakeup_event = wakeup_event
        # We can get the queue from the reactor, which is the canonical consumer
        self.ingress_queue = reactor.ingress_queue

    async def run(self) -> None:
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
                    # 3. Adaptive Throttling
                    if fired_count > 0:
                        await asyncio.sleep(0)
                    else:
                        if not self.ingress_queue.empty():
                            await asyncio.sleep(0)
                        else:
                            await asyncio.sleep(0.001)
~~~~~
~~~~~python.new
                    # 3. Adaptive Throttling / Waiting
                    if fired_count > 0 or (
                        self.ingress_queue and not self.ingress_queue.empty()
                    ):
                        # If physics fired or ingress is pending, yield but loop again immediately.
                        await asyncio.sleep(0)
                    else:
                        # System is physically idle. Wait for new ingress.
                        try:
                            # Use a timeout to periodically re-check for drain completion
                            await asyncio.wait_for(self.wakeup_event.wait(), timeout=0.1)
                            self.wakeup_event.clear()
                        except asyncio.TimeoutError:
                            pass  # Loop again to check state
~~~~~

#### Acts 3: 更新 `EventDrivenRunner` 以注入依赖

`EventDrivenRunner` 作为测试工具，现在负责创建和连接 `wakeup_event`。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
        from cascade.runtime.storage import InMemoryObjectStore

        self.object_store = InMemoryObjectStore()
        self.compute_service = LocalComputeService(
            store=self.object_store,
            registry=code_registry,
            inbound_queue=self.compute_queue,
            outbound_queue=self.ingress_queue,
        )

        # 3. Setup Event Bus & Resource Registry
        self.event_bus = EventBus()
~~~~~
~~~~~python.new
        from cascade.runtime.storage import InMemoryObjectStore

        self.object_store = InMemoryObjectStore()
        self.wakeup_event = asyncio.Event()
        self.compute_service = LocalComputeService(
            store=self.object_store,
            registry=code_registry,
            inbound_queue=self.compute_queue,
            outbound_queue=self.ingress_queue,
            wakeup_event=self.wakeup_event,
        )

        # 3. Setup Event Bus & Resource Registry
        self.event_bus = EventBus()
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
        factory = reactor_factory or Reactor
        self.reactor = factory(
            self.graph,
            self.memory,
            function_map,
            self.resource_registry,
            ingress_queue=self.ingress_queue,
        )
        self._loop_task: Optional[asyncio.Task] = None
~~~~~
~~~~~python.new
        factory = reactor_factory or Reactor
        self.reactor = factory(
            self.graph,
            self.memory,
            function_map,
            self.resource_registry,
            ingress_queue=self.ingress_queue,
        )
        # The Machine is now a component managed by the harness
        from cascade.vm.machine import Machine

        self.machine = Machine(self.reactor, self.compute_service, self.wakeup_event)
        self._loop_task: Optional[asyncio.Task] = None
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
        self._stop_event.clear()
        # Start both the reactor and the compute service as background tasks
        self._service_task = asyncio.create_task(self.compute_service.run())
        self._loop_task = asyncio.create_task(self._run_loop())
~~~~~
~~~~~python.new
        self._stop_event.clear()
        # The machine now manages starting the compute service.
        self._loop_task = asyncio.create_task(self.machine.run())
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
    async def _run_loop(self):
        logger.info("Reactor loop with ingress handling started.")
        try:
            while not self._stop_event.is_set():
                # In v3.1 Phase 4, the Reactor handles ingress internally during step().
                fired = self.reactor.step()
                if fired == 0 and self.ingress_queue.empty():
                    await asyncio.sleep(0.001)
                else:
                    # Yield to allow other tasks (like ComputeService) to run
                    await asyncio.sleep(0)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Reactor loop crashed")
            raise
~~~~~
~~~~~python.new
    # The _run_loop is now managed by the Machine, so we can remove it.
    # async def _run_loop(self): ...
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
    async def stop_loop(self):
        self._stop_event.set()
        if self._service_task:
            self.compute_service.stop()
            self._service_task.cancel()
            try:
                await self._service_task
            except asyncio.CancelledError:
                pass
            self._service_task = None
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
~~~~~
~~~~~python.new
    async def stop_loop(self):
        # Trigger shutdown via the reactor's event, which the machine listens for
        self.reactor.shutdown_event.set()
        if self._loop_task:
            try:
                # Wait for the machine's run() to finish its cleanup
                await asyncio.wait_for(self._loop_task, timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Machine did not shut down cleanly, cancelling task.")
                self._loop_task.cancel()
            except asyncio.CancelledError:
                pass  # It's already cancelled, that's fine.
            self._loop_task = None
~~~~~

#### Acts 4: 更新集成测试

最后，更新 `test_machine_integration.py` 以适应新的 `Machine` 构造函数。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_machine_integration.py
~~~~~
~~~~~python.old
    # Instantiate Core Components
    reactor = Reactor(graph, memory, function_map, resource_registry, ingress_queue)
    compute_service = LocalComputeService(
        store=object_store,
        registry=code_registry,
        inbound_queue=compute_queue,
        outbound_queue=ingress_queue,
    )
    machine = Machine(reactor, compute_service, ingress_queue)
~~~~~
~~~~~python.new
    # Instantiate Core Components
    wakeup_event = asyncio.Event()
    reactor = Reactor(graph, memory, function_map, resource_registry, ingress_queue)
    compute_service = LocalComputeService(
        store=object_store,
        registry=code_registry,
        inbound_queue=compute_queue,
        outbound_queue=ingress_queue,
        wakeup_event=wakeup_event,
    )
    machine = Machine(reactor, compute_service, wakeup_event)
~~~~~

### 下一步建议
我们已经成功地将 `Machine` 的调度模型从低效的轮询升级为高效的事件驱动模式。

下一个合乎逻辑的步骤是改进我们的测试基础设施。`test_machine_integration.py` 中使用的 `observer_task` 是一个外部停止器，它使得测试无法验证一个能够自我终结的图。

我建议我们开始实施：**重构集成测试，使其包含一个完整的控制流路径，实现自我终结**。
