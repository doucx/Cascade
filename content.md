Your analysis is sharp. The previous fix resolved the scheduling livelock, but in doing so, it allowed the tests to proceed further and uncover a new, more fundamental issue: a kernel panic.

You are correct. The test timeouts are again a symptom, not the root cause.

The log output provides a clear diagnosis:
```
KeyError: "Resource 'system.egress_queue' not found."
```
This error occurs within the `standard_egress` kernel function, which is responsible for handling the final output of a graph. This function has a hard dependency on a system resource named `system.egress_queue` to publish its results.

The test harness used in these integration tests, `EventDrivenRunner`, was not updated to provide this required resource to the `PhysicsKernel`. Consequently, when an `egress` node tries to fire, the kernel panics, the `Reactor` correctly interprets this as a critical system error, and shuts down the machine. The test, however, is still waiting for `TaskExecutionFinished` events that will never be emitted due to the premature shutdown, leading to the timeout.

The goal is to align the `EventDrivenRunner` test harness with the requirements of the production runtime by ensuring it properly initializes and registers the `system.egress_queue`.

The `EventDrivenRunner` must simulate the complete system environment required by the `PhysicsKernel`. By adding the missing `egress_queue` and registering it with the `ResourceRegistry`, we satisfy the dependency of the `standard_egress` function, preventing the kernel panic and allowing the test workflows to run to completion as intended.

I will now generate the plan to implement this fix.

## [WIP] fix(vm): Register egress_queue in test harness to prevent kernel panic

### 用户需求

修复 `test_resource_contention` 和 `test_resource_sentry` 中的 `KeyError: "Resource 'system.egress_queue' not found."` 问题。该问题导致内核恐慌 (kernel panic) 和测试超时。

### 评论

这是一个典型的测试基础设施与生产代码不同步的问题。随着 `VMExecutionStrategy` 的引入，`egress` 节点的实现方式发生了变化，其依赖于一个标准的 `system.egress_queue` 来输出结果。`EventDrivenRunner` 这个测试工具没有相应地更新，导致在执行 `egress` 节点时因缺少资源而崩溃。修复方法是使测试工具的行为与生产环境的 `RuntimeHarness` 保持一致。

### 目标

修改 `EventDrivenRunner` 以创建并注册 `system.egress_queue`，从而解决内核恐慌问题并使相关集成测试能够通过。

### 基本原理

`standard_egress` 内核函数需要从 `ResourceRegistry` 中获取一个名为 `system.egress_queue` 的 `asyncio.Queue` 来放置图的最终结果。`EventDrivenRunner` 作为测试中的“主板”，负责组装所有必要的系统组件。通过在 `EventDrivenRunner` 的初始化过程中添加 `egress_queue` 的创建和注册逻辑，我们为 `standard_egress` 提供了其运行所必需的依赖，从而修复了整个执行路径。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #comp/runtime #concept/state #task/domain/testing #task/object/test-harness #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 在 `EventDrivenRunner` 中添加 `egress_queue`

我们将修改 `packages/cascade-vm/src/cascade/vm/harness.py` 文件，在 `EventDrivenRunner` 中添加 `egress_queue` 的初始化和注册逻辑。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
        # 1. Setup Queues for disconnected execution
        self.compute_queue: asyncio.Queue[ComputeRequest] = asyncio.Queue()
        self.chronos_queue: asyncio.Queue[DelayRequest] = asyncio.Queue()
        self.ingress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()

        # 2. Setup Services
        # In a real system, store would be a separate entity.
~~~~~
~~~~~python.new
        # 1. Setup Queues for disconnected execution
        self.compute_queue: asyncio.Queue[ComputeRequest] = asyncio.Queue()
        self.chronos_queue: asyncio.Queue[DelayRequest] = asyncio.Queue()
        self.ingress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()
        self.egress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()

        # 2. Setup Services
        # In a real system, store would be a separate entity.
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
        self.resource_registry.register("system.event_bus", self.event_bus)
        self.resource_registry.register("system.compute_queue", self.compute_queue)
        self.resource_registry.register("system.chronos_queue", self.chronos_queue)
        self.resource_registry.register("system.object_store", self.object_store)

        # 4. Setup Reactor
        # Construct the Physics Kernel
~~~~~
~~~~~python.new
        self.resource_registry.register("system.event_bus", self.event_bus)
        self.resource_registry.register("system.compute_queue", self.compute_queue)
        self.resource_registry.register("system.chronos_queue", self.chronos_queue)
        self.resource_registry.register("system.object_store", self.object_store)
        self.resource_registry.register("system.egress_queue", self.egress_queue)

        # 4. Setup Reactor
        # Construct the Physics Kernel
~~~~~

### 下一步建议

既然 `EventDrivenRunner` 的核心缺陷已经修复，现在可以重新运行测试套件。如果所有测试都通过，那么这个宏观任务（修复并发测试）就完成了，我们可以生成一个 `[COMMIT]` 计划来最终提交所有相关的修复。
