## [WIP] feat(vm): Activate Sync Kernel execution and fix test harness

### 用户需求
1.  **激活同步内核**: 修改 `Reactor`，使其能够识别同步函数（`def`）并直接在当前线程执行，绕过 `executor.submit` 线程池。这是实现高性能 TCO（尾调用优化）和微秒级延迟的关键。
2.  **修复集成测试**: 更新 `test_resource_backpressure.py`，为其注入 `InMemoryObjectStore`。由于 `const_probe` 现在依赖存储后端来持久化标量值，缺少此配置会导致测试失败。

### 评论
这是 Ref-Based 架构转型的关键一步。通过允许 Reactor 直接执行同步代码，我们将 `PhysicsKernel` 的概念真正落地，消除了不必要的上下文切换开销。同时，修复测试保证了我们在这一激进变更中的稳定性。

### 目标
1.  修改 `packages/cascade-vm/src/cascade/vm/reactor.py` 中的 `_execute_task` 方法，添加对同步函数的直接调用分支。
2.  修改 `packages/cascade-runtime/tests/integration/test_resource_backpressure.py`，手动构建并注入 `ResourceRegistry` 和 `InMemoryObjectStore`。

### 基本原理
*   **Zero-Overhead Execution**: 标准库 ICs（如 Allocator, Bleacher）现在是极其轻量的纯内存操作。将它们放入线程池（`executor.submit`）不仅没有必要，反而因为线程调度和 Future 管理引入了毫秒级的延迟。直接调用可以将开销降低到微秒级。
*   **Dependency Injection in Tests**: 随着 `Probe` 组件开始真正与 `ObjectStore` 交互（为了生成 Ref），所有使用 Probe 的测试都必须提供一个有效的存储后端。

### 标签
#intent/refine #flow/ready #priority/critical #comp/vm #comp/tests #concept/reactor #concept/ref-architecture #scope/core #ai/instruct #task/domain/core #task/object/reactor #task/action/sync-activation #task/state/continue

---

### Script

#### Acts 1: 激活 Reactor 的同步执行路径

修改 `_execute_task`，如果 `func` 不是协程函数，则直接调用它。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
    async def _execute_task(
        self, node: PhysicsFuncNode, input_data: Dict[str, Token]
    ) -> None:
        try:
            # 1. Execution
            func = self.function_map.get(node.id)
            if not func:
                raise ValueError(f"No function mapped for node {node.id}")

            # The new standard signature for all physical functions is (inputs, node, resources)
            if inspect.iscoroutinefunction(func):
                result_tokens = await func(input_data, node, self.resource_registry)
            else:
                result_tokens = await self.executor.submit(
                    func, (input_data, node, self.resource_registry)
                )

            if not isinstance(result_tokens, dict):
~~~~~
~~~~~python.new
    async def _execute_task(
        self, node: PhysicsFuncNode, input_data: Dict[str, Token]
    ) -> None:
        try:
            # 1. Execution
            func = self.function_map.get(node.id)
            if not func:
                raise ValueError(f"No function mapped for node {node.id}")

            # The new standard signature for all physical functions is (inputs, node, resources)
            if inspect.iscoroutinefunction(func):
                result_tokens = await func(input_data, node, self.resource_registry)
            else:
                # Sync Kernel Activation: Direct Execution
                # For high-performance ICs (Allocator, Bleacher, etc.), we execute
                # directly on the reactor thread to avoid executor overhead.
                result_tokens = func(input_data, node, self.resource_registry)

            if not isinstance(result_tokens, dict):
~~~~~

#### Acts 2: 修复 Backpressure 测试的环境注入

为手动构建的 Reactor 注入 `system.object_store`。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor

# Import new ICs
from cascade.std.triad.bleacher import standard_bleacher
~~~~~
~~~~~python.new
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor
from cascade.vm.resource_registry import ResourceRegistry
from cascade.runtime.storage import InMemoryObjectStore

# Import new ICs
from cascade.std.triad.bleacher import standard_bleacher
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    # 5. Initialize Reactor
    reactor = Reactor(physical_graph, memory, executor, func_map)

    # 6. Prime the reactor.
    reactor.prime()
~~~~~
~~~~~python.new
    # 5. Initialize Reactor
    # Probe needs an object store to materialize scalar values into Refs
    registry = ResourceRegistry()
    store = InMemoryObjectStore()
    registry.register("system.object_store", store)
    
    reactor = Reactor(physical_graph, memory, executor, func_map, resource_registry=registry)

    # 6. Prime the reactor.
    reactor.prime()
~~~~~

### 下一步建议

我们已经完成了底层设施的改造：标准库已同步化，Reactor 已支持同步调用，且关键测试已修复环境问题。

现在的关键是验证这一切是否按预期工作。
1.  **运行测试**: 执行 `test_resource_contention.py` 和 `test_resource_backpressure.py`。
2.  **扩展验证**: 考虑增加一个针对 `PhysicsKernel` 行为的单元测试，确保同步函数确实是在主线程执行的（可以通过检查线程 ID）。
3.  **清理**: 如果 `discrete_allocator` 等测试通过，我们可以考虑移除 `cascade-std` 中残留的任何旧版异步代码。
