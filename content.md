## [WIP] feat: 增强资源管理系统的可观测性

### 用户需求
为依赖注入系统添加可观测性。具体而言，需要在资源被获取（setup 完成）和释放（teardown 完成）时发布相应的事件，以便日志和监控系统能够感知资源的状态变化。

### 评论
当前资源管理是“静默”的。如果资源初始化缓慢或失败，或者清理逻辑未执行，用户很难感知。通过引入 `ResourceAcquired` 和 `ResourceReleased` 事件，我们将这种隐式的生命周期显式化，这对于调试复杂的资源依赖链至关重要。

### 目标
1.  **定义事件**: 在 `src/cascade/runtime/events.py` 中添加 `ResourceAcquired` 和 `ResourceReleased` 事件类。
2.  **发布事件**: 更新 `src/cascade/runtime/engine.py`，在资源 setup 成功后和 teardown 完成后发布上述事件。
3.  **验证**: 更新 `tests/test_di_and_resources.py`，添加测试逻辑以验证这些事件是否被正确触发。

### 基本原理
我们利用 Cascade 已有的 Message Bus 架构。`Engine` 在管理资源生命周期的关键节点（`next(gen)` 之后和 `StopIteration` 之后/异常时）构造并发布事件。这些事件将携带 `run_id` 和 `resource_name`，提供完整的上下文。

### 标签
#intent/build #flow/ready #priority/medium
#comp/runtime #comp/tests
#concept/observability #concept/dependency-injection
#scope/core
#task/domain/core #task/object/observability #task/action/implementation
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 定义资源生命周期事件

我们首先定义两个新的事件类型。

~~~~~act
patch_file
src/cascade/runtime/events.py
~~~~~
~~~~~python
@dataclass(frozen=True)
class TaskSkipped(TaskEvent):
    """Fired when a task is skipped due to caching or conditional logic."""
    reason: str = "Unknown" # "CacheHit", "ConditionFalse"
~~~~~
~~~~~python
@dataclass(frozen=True)
class TaskSkipped(TaskEvent):
    """Fired when a task is skipped due to caching or conditional logic."""
    reason: str = "Unknown" # "CacheHit", "ConditionFalse"

@dataclass(frozen=True)
class ResourceEvent(Event):
    """Base for events related to resources."""
    resource_name: str = ""

@dataclass(frozen=True)
class ResourceAcquired(ResourceEvent):
    """Fired when a resource is successfully initialized (setup complete)."""
    pass

@dataclass(frozen=True)
class ResourceReleased(ResourceEvent):
    """Fired when a resource is successfully torn down."""
    pass
~~~~~

#### Acts 2: 在 Engine 中发布事件

修改 `Engine`，在 `_setup_resources` 和 `_teardown_resource` 中发布事件。我们需要将 `run_id` 传递给这两个方法，以便事件包含正确的上下文。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import RunStarted, RunFinished, TaskExecutionStarted, TaskExecutionFinished
from cascade.runtime.protocols import Solver, Executor
from cascade.adapters.solvers.native import NativeSolver
~~~~~
~~~~~python
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
    RunStarted, RunFinished, TaskExecutionStarted, TaskExecutionFinished,
    ResourceAcquired, ResourceReleased
)
from cascade.runtime.protocols import Solver, Executor
from cascade.adapters.solvers.native import NativeSolver
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
                # Scan for all required resources
                required_resources = self._scan_for_resources(plan)
                
                # Setup resources and get active instances
                active_resources = self._setup_resources(required_resources, stack)

                results: Dict[str, Any] = {}
                for node in plan:
~~~~~
~~~~~python
                # Scan for all required resources
                required_resources = self._scan_for_resources(plan)
                
                # Setup resources and get active instances
                active_resources = self._setup_resources(required_resources, stack, run_id)

                results: Dict[str, Any] = {}
                for node in plan:
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
        return required

    def _setup_resources(self, required_names: set[str], stack: ExitStack) -> Dict[str, Any]:
        """
        Initializes all required resources and their dependencies recursively.
        Returns a dictionary of active resource instances.
        """
        active: Dict[str, Any] = {}
        
        def get_or_create(name: str):
            if name in active:
                return active[name]
            
            provider = self._resource_providers.get(name)
            if not provider:
                raise NameError(f"Resource '{name}' is required but not registered.")

            # Inspect provider's signature to find its dependencies
            sig = inspect.signature(provider)
            deps = {}
            for param_name, param in sig.parameters.items():
                if isinstance(param.default, Inject):
                    deps[param_name] = get_or_create(param.default.resource_name)
                # Here you could also inject `Param`s if needed
            
            # Create the resource generator
            gen = provider(**deps)
            
            # Enter the generator and get the yielded value
            instance = next(gen)
            active[name] = instance
            
            # Register the teardown logic
            stack.callback(self._teardown_resource, gen)
            
            return instance

        for name in required_names:
            get_or_create(name)
            
        return active

    def _teardown_resource(self, gen: Generator):
        """Helper to exhaust a resource generator for cleanup."""
        try:
            next(gen)
        except StopIteration:
            pass # This is expected
~~~~~
~~~~~python
        return required

    def _setup_resources(self, required_names: set[str], stack: ExitStack, run_id: str) -> Dict[str, Any]:
        """
        Initializes all required resources and their dependencies recursively.
        Returns a dictionary of active resource instances.
        """
        active: Dict[str, Any] = {}
        
        def get_or_create(name: str):
            if name in active:
                return active[name]
            
            provider = self._resource_providers.get(name)
            if not provider:
                raise NameError(f"Resource '{name}' is required but not registered.")

            # Inspect provider's signature to find its dependencies
            sig = inspect.signature(provider)
            deps = {}
            for param_name, param in sig.parameters.items():
                if isinstance(param.default, Inject):
                    deps[param_name] = get_or_create(param.default.resource_name)
                # Here you could also inject `Param`s if needed
            
            # Create the resource generator
            gen = provider(**deps)
            
            # Enter the generator and get the yielded value
            instance = next(gen)
            active[name] = instance
            self.bus.publish(ResourceAcquired(run_id=run_id, resource_name=name))
            
            # Register the teardown logic
            stack.callback(self._teardown_resource, gen, run_id, name)
            
            return instance

        for name in required_names:
            get_or_create(name)
            
        return active

    def _teardown_resource(self, gen: Generator, run_id: str, resource_name: str):
        """Helper to exhaust a resource generator for cleanup."""
        try:
            next(gen)
        except StopIteration:
            self.bus.publish(ResourceReleased(run_id=run_id, resource_name=resource_name))
~~~~~

#### Acts 3: 验证事件发布

更新测试文件，验证事件是否被正确触发。

~~~~~act
patch_file
tests/test_di_and_resources.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
import cascade as cs

# --- Test Resources ---
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
import cascade as cs
from cascade.runtime.events import ResourceAcquired, ResourceReleased, Event

# --- Test Resources ---
~~~~~

~~~~~act
patch_file
tests/test_di_and_resources.py
~~~~~
~~~~~python
    result = engine.run(task_using_resource())

    assert result == "production_url"
    # Teardown order should be reverse of setup
    # TODO: We need a way to verify setup/teardown calls, maybe via events.

def test_resource_override():
~~~~~
~~~~~python
    result = engine.run(task_using_resource())

    assert result == "production_url"

def test_resource_events():
    """Tests that resource lifecycle events are emitted."""
    events = []
    bus = cs.MessageBus()
    bus.subscribe(Event, events.append)

    engine = cs.Engine(bus=bus)
    engine.register(config)
    engine.register(db_connection)

    engine.run(task_using_resource())

    # Check for ResourceAcquired events
    acquired_names = [e.resource_name for e in events if isinstance(e, ResourceAcquired)]
    # 'config' must be acquired before 'db_connection' because db_connection depends on config
    assert "config" in acquired_names
    assert "db_connection" in acquired_names
    assert acquired_names.index("config") < acquired_names.index("db_connection")

    # Check for ResourceReleased events
    released_names = [e.resource_name for e in events if isinstance(e, ResourceReleased)]
    # Teardown is in reverse order (LIFO via ExitStack)
    assert "db_connection" in released_names
    assert "config" in released_names
    assert released_names.index("db_connection") < released_names.index("config")

def test_resource_override():
~~~~~

### 下一步建议
运行测试 `pytest tests/test_di_and_resources.py`，确认所有测试通过。

之后，我们将进行阶段二的下一个大任务：**实现一等公民的异步 (`async/await`) 支持**。这将使 `Cascade` 能够处理现代的 IO 密集型工作流。
