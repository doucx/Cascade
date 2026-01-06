简要回答：
好的，我将执行“第四阶段：反应堆进化”的核心任务，将 `ingress_queue` 的处理逻辑从测试辅助工具 `Harness` 下沉到核心组件 `Reactor` 中，使其成为一个真正自洽的、能主动处理外部事件的状态机。同时，我将修复因 `EventDrivenRunner` 签名变更导致的测试失败。

## [WIP] feat(vm): 进化 Reactor 以内置处理 Ingress 队列

### 错误分析

用户报告了两个 `TypeError`，均指出 `EventDrivenRunner.__init__()` 缺少 `code_registry` 参数。这是因为在上一阶段引入计算服务时，更新了 `EventDrivenRunner` 的签名，但未同步更新所有相关测试用例。本次计划将一并修复此问题。

### 用户需求

1.  **Reactor 自洽性**: `Reactor` 必须内置 `ingress_queue` 属性，并在 `step()` 循环中主动消费该队列，将外部计算结果（Token）注入到物理图的 DataNode 中。
2.  **Harness 简化**: `EventDrivenRunner` 应剥离手动处理 Ingress 的逻辑，转而只负责组装组件。
3.  **测试修复**: 修复所有因 `EventDrivenRunner` 接口变更而崩溃的测试。

### 评论

这是一个关键的架构重构。将 Ingress 处理移入 Reactor 意味着 Reactor 不再仅仅是一个被动的“图遍历器”，它变成了一个真正的“反应堆”，能够响应外部世界的刺激。这对于实现高吞吐量的异步/同步混合调度至关重要，因为它允许 I/O 密集型任务在后台完成后，自动、低延迟地唤醒 Reactor 的物理周期。

### 目标

1.  修改 `Reactor` 类，使其接收并处理 `ingress_queue`。
2.  重构 `EventDrivenRunner`，移除冗余逻辑并适配新 `Reactor`。
3.  修复 `test_context_injection.py` 和 `test_reactor.py`。

### 基本原理

通过将 Ingress 逻辑标准化为 Reactor 生命周期的一部分（即在每次 `step` 的物理计算之前先处理“入境”），我们保证了所有外部输入都在确定的时机进入系统，消除了 Harness 层面手动调度可能引入的竞态条件或延迟。这也使得 Reactor 在生产环境（非测试环境）下更容易被托管。

### 标签

#intent/refine #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/vm #task/object/reactor #task/action/evolution #task/state/continue

---

### Script

#### Acts 1: 修改 Reactor 以支持 Ingress 处理

我们将向 `Reactor` 添加 `ingress_queue` 并在 `step` 方法的开头处理它。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        executor: PhysicsExecutor,
        function_map: Dict[str, Callable],
        resource_registry: Optional[ResourceRegistry] = None,
    ):
        self.graph = graph
        self.memory = memory
        self.executor = executor
        self.function_map = function_map
        self.resource_registry = resource_registry or ResourceRegistry()

        # State
        self.active_task_count = 0
~~~~~
~~~~~python.new
    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        executor: PhysicsExecutor,
        function_map: Dict[str, Callable],
        resource_registry: Optional[ResourceRegistry] = None,
        ingress_queue: Optional[asyncio.Queue] = None,
    ):
        self.graph = graph
        self.memory = memory
        self.executor = executor
        self.function_map = function_map
        self.resource_registry = resource_registry or ResourceRegistry()
        self.ingress_queue = ingress_queue

        # State
        self.active_task_count = 0
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
    async def step(self) -> int:
        nodes_to_fire: List[PhysicsFuncNode] = []
        inputs_for_fire: Dict[str, Dict[str, Token]] = {}

        # --- ATOMIC SCAN & CONSUME ---
~~~~~
~~~~~python.new
    async def step(self) -> int:
        # 0. Ingress Cycle
        self._process_ingress()

        nodes_to_fire: List[PhysicsFuncNode] = []
        inputs_for_fire: Dict[str, Dict[str, Token]] = {}

        # --- ATOMIC SCAN & CONSUME ---
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
        except Exception as e:
            logger.exception(f"Error executing task {node.id}: {e}")
            # TODO: Emit error token to a special error port or DLQ?
            # For now, we just log. In v3.0 specs, errors are propagated as tokens.
            # If the func raised, it means it crashed HARD.
        finally:
            self.active_task_count -= 1
            # If we hit 0, we might want to signal an event?
            # For now, relying on memory mutation events is enough for forward progress.
~~~~~
~~~~~python.new
        except Exception as e:
            logger.exception(f"Error executing task {node.id}: {e}")
            # TODO: Emit error token to a special error port or DLQ?
            # For now, we just log. In v3.0 specs, errors are propagated as tokens.
            # If the func raised, it means it crashed HARD.
        finally:
            self.active_task_count -= 1
            # If we hit 0, we might want to signal an event?
            # For now, relying on memory mutation events is enough for forward progress.

    def _process_ingress(self):
        if not self.ingress_queue:
            return

        while not self.ingress_queue.empty():
            try:
                reply_to_nid, result_token = self.ingress_queue.get_nowait()
                node = self.graph.nodes.get(reply_to_nid)
                if isinstance(node, PhysicsDataNode):
                    self.memory.put(node, result_token)
                else:
                    logger.warning(
                        f"Invalid reply_to_nid '{reply_to_nid}': not a DataNode."
                    )
            except asyncio.QueueEmpty:
                break
~~~~~

#### Acts 2: 重构 EventDrivenRunner

我们将从 `EventDrivenRunner` 中移除 `_handle_ingress` 逻辑，并将 `ingress_queue` 传递给 `Reactor`。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
        # 4. Setup Reactor
        factory = reactor_factory or Reactor
        self.reactor = factory(
            self.graph,
            self.memory,
            self.executor,
            function_map,
            self.resource_registry,
        )
        self._loop_task: Optional[asyncio.Task] = None
~~~~~
~~~~~python.new
        # 4. Setup Reactor
        factory = reactor_factory or Reactor
        self.reactor = factory(
            self.graph,
            self.memory,
            self.executor,
            function_map,
            self.resource_registry,
            ingress_queue=self.ingress_queue,
        )
        self._loop_task: Optional[asyncio.Task] = None
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
                # This is the core of the v3.1 harness: it simulates the Reactor's
                # ability to handle both internal state changes and external events.
                await self._handle_ingress()
                fired = await self.reactor.step()
                if fired == 0 and self.ingress_queue.empty():
                    await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Reactor loop crashed")
            raise

    async def _handle_ingress(self):
        while not self.ingress_queue.empty():
            reply_to_nid, result_token = self.ingress_queue.get_nowait()
            node = self.graph.nodes.get(reply_to_nid)
            if isinstance(node, PhysicsDataNode):
                self.memory.put(node, result_token)
            else:
                logger.warning(
                    f"Invalid reply_to_nid '{reply_to_nid}': not a DataNode."
                )

    async def stop_loop(self):
~~~~~
~~~~~python.new
    async def _run_loop(self):
        logger.info("Reactor loop with ingress handling started.")
        try:
            while not self._stop_event.is_set():
                # In v3.1 Phase 4, the Reactor handles ingress internally during step().
                fired = await self.reactor.step()
                if fired == 0 and self.ingress_queue.empty():
                    await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Reactor loop crashed")
            raise

    async def stop_loop(self):
~~~~~

#### Acts 3: 修复 Integration Test 中的 Runner 初始化

`test_context_injection.py` 需要更新 `EventDrivenRunner` 的初始化调用，传入一个 Dummy CodeRegistry。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_context_injection.py
~~~~~
~~~~~python.old
from cascade.std.triad.observer import standard_observer


# --- Helper: Build a Physical Triad manually ---
~~~~~
~~~~~python.new
from cascade.std.triad.observer import standard_observer
from cascade.vm.registry import CodeRegistry


# --- Helper: Build a Physical Triad manually ---
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_context_injection.py
~~~~~
~~~~~python.old
    function_map = {
        "task.bleach": standard_bleacher,
        "task.worker": simple_worker,
        "task.stain": standard_stainer,
        "global.observability.observer": standard_observer,
    }

    runner = EventDrivenRunner(graph, function_map)

    # Assert Runner has generated a Run ID
    assert runner.run_id is not None
~~~~~
~~~~~python.new
    function_map = {
        "task.bleach": standard_bleacher,
        "task.worker": simple_worker,
        "task.stain": standard_stainer,
        "global.observability.observer": standard_observer,
    }

    runner = EventDrivenRunner(graph, function_map, CodeRegistry())

    # Assert Runner has generated a Run ID
    assert runner.run_id is not None
~~~~~

#### Acts 4: 修复 Unit Test 中的 Runner 初始化

`test_reactor.py` 中的 `test_event_driven_ping_pong` 同样需要更新。

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
from cascade.vm.harness import EventDrivenRunner
from cascade.spec.physical.triad import ObservabilityNode
from cascade.std.triad.observer import standard_observer


# Dummy function for testing
def noop(inputs, node, resources):
~~~~~
~~~~~python.new
from cascade.vm.harness import EventDrivenRunner
from cascade.spec.physical.triad import ObservabilityNode
from cascade.std.triad.observer import standard_observer
from cascade.vm.registry import CodeRegistry


# Dummy function for testing
def noop(inputs, node, resources):
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
    }

    # 2. Use Runner, injecting the backend factory
    runner = EventDrivenRunner(graph, func_map, reactor_factory=reactor_backend_factory)
    runner.inject_input("D1", 10)

    # 3. Start & Wait
~~~~~
~~~~~python.new
    }

    # 2. Use Runner, injecting the backend factory
    runner = EventDrivenRunner(
        graph, func_map, CodeRegistry(), reactor_factory=reactor_backend_factory
    )
    runner.inject_input("D1", 10)

    # 3. Start & Wait
~~~~~

### 下一步建议

执行测试以验证：
1.  `test_context_injection.py` 和 `test_reactor.py` 是否通过。
2.  `Reactor` 是否正确处理了 `ingress_queue` 中的 Token。

如果通过，可以考虑将此变更提交。
