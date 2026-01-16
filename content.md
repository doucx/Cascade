好的，我明白了。上一轮的重构暴露了两个地方没有正确适配新的 `Engine` 构造函数：

1.  **`test_vm_e2e.py`**: 这个测试文件有其自己的、局部的 `engine` fixture，它直接调用了 `Engine()`，现在缺少了必需的 `constraint_manager` 和 `wakeup_event` 参数。
2.  **`cascade.app`**: 在 `CascadeApp` 的 `__init__` 方法中，虽然我创建了 `ConstraintManager` 和 `wakeup_event`，但我忘记了将它们传递给 `Engine` 的构造函数。这导致了 `test_file_existence_cache.py` 中通过 `cs.run()` 调用的失败。

我将一次性修复这两个问题。

## [WIP] fix: Adapt Engine consumers to new DI requirements

### 错误分析

在将 `Engine` 重构为需要显式注入 `constraint_manager` 和 `wakeup_event` 后，`packages/cascade-runtime/tests/integration/test_vm_e2e.py` 中的本地 `engine` fixture 以及 `packages/cascade-application/src/cascade/app/__init__.py` 中的 `CascadeApp` 类都未能提供这些必需的参数，导致了 `TypeError`。

### 用户需求

修复所有因 `Engine` 构造函数变更而导致的 `TypeError`，确保 VM 测试和 `cascade.app` 都能正确实例化 `Engine`。

### 评论

这是依赖注入重构后的典型清理工作。通过将 `engine_factory` fixture 应用于 `test_vm_e2e.py`，我们统一了测试中 `Engine` 的创建方式，提高了代码的复用性和一致性。同时，修正 `CascadeApp` 中的 `Engine` 实例化调用，确保了应用层正确地将所有必需的服务注入到核心运行时中，完成了架构分层。

### 目标

1.  修改 `test_vm_e2e.py` 中的 `engine` fixture，使其使用根 `conftest.py` 中定义的 `engine_factory` 来创建 `Engine` 实例，并确保注入 `VMExecutionStrategy`。
2.  修改 `cascade.app.__init__.py` 中 `CascadeApp` 的构造逻辑，将创建的 `constraint_manager` 和 `wakeup_event` 正确传递给 `Engine` 的构造函数。

### 基本原理

对于 `test_vm_e2e.py`，我们将利用已有的 `engine_factory` fixture。我们会在测试文件中创建一个 `VMExecutionStrategy` 实例，并将其作为 `strategy` 参数传递给 `engine_factory`。工厂将负责提供所有其他必需的依赖项（如 `constraint_manager`），从而以一种干净、解耦的方式构建出用于 VM 测试的 `Engine`。

对于 `cascade.app`，这是一个直接的修复。我们只需在 `self.engine = Engine(...)` 的调用中，添加 `constraint_manager=self.constraint_manager` 和 `wakeup_event=self.wakeup_event`（或者直接传递在方法内部创建的局部变量）即可。

### 标签

#intent/fix #flow/ready #priority/critical #comp/runtime #comp/tests #scope/core #dx #ai/instruct #task/domain/testing #task/object/dependency-injection #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_vm_e2e.py` 的 Engine 实例化

我将修改此文件中的 `engine` fixture，以正确使用 `engine_factory`。

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_vm_e2e.py
~~~~~
~~~~~python.old
@pytest.fixture
def engine(executor, bus, strategy):
    # Solver is not used by VMStrategy but required by Engine interface
    solver = MockSolver(plan=[])

    return Engine(
        solver=solver,
        executor=executor,
        bus=bus,
        strategy=strategy,
        object_store=InMemoryObjectStore(),
    )
~~~~~
~~~~~python.new
@pytest.fixture
def engine(engine_factory, executor, bus, strategy):
    # Solver is not used by VMStrategy but required by Engine interface
    solver = MockSolver(plan=[])

    return engine_factory(
        solver=solver,
        executor=executor,
        bus=bus,
        strategy=strategy,
        object_store=InMemoryObjectStore(),
    )
~~~~~

#### Acts 2: 修复 `CascadeApp` 的 Engine 实例化

现在，我将修复 `cascade.app` 中的 `Engine` 调用，确保所有必需的参数都被传递。

~~~~~act
patch_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python.old
        # 6. Create Engine
        self.engine = Engine(
            solver=self.solver,
            executor=self.executor,
            bus=self.event_bus,
            strategy=strategy,
            resource_manager=self.resource_manager,
            system_resources=self.system_resources,
            connector=self.connector,
            state_backend_factory=self.sb_factory,
        )
~~~~~
~~~~~python.new
        # 6. Create Engine
        self.engine = Engine(
            solver=self.solver,
            executor=self.executor,
            bus=self.event_bus,
            strategy=strategy,
            constraint_manager=constraint_manager,
            wakeup_event=wakeup_event,
            resource_manager=self.resource_manager,
            system_resources=self.system_resources,
            connector=self.connector,
            state_backend_factory=self.sb_factory,
        )
~~~~~

### 下一步建议

我们已经修复了所有已知的 `Engine` 实例化错误。现在，我将再次运行测试套件。这次，`test_vm_e2e.py` 和 `test_file_existence_cache.py` 都应该能成功通过。如果所有测试都通过，则表明我们的依赖注入重构已经完成并稳定下来，下一步可以进行提交。
