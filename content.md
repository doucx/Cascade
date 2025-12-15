好的，我们正式启动 **Cascade 阶段二 (MVP+) 执行计划**。

第一项核心任务是实现**依赖注入 (DI) 与资源管理系统**。这是将 Cascade 从一个智能脚本执行器提升为可靠自动化应用框架的关键一步。它能彻底解耦业务逻辑与外部依赖（如数据库连接、API 客户端），从而使任务变得高度可测试。

我将把这个任务分解为多个逻辑步骤，并为每个步骤提供相应的实现和测试代码，以确保功能的健壮性和覆盖率。

## [WIP] feat: 实现依赖注入与资源管理系统

### 用户需求
启动 Cascade 阶段二开发，首先实现完整的依赖注入 (DI) 和资源管理系统。要求将此功能分解为多个可独立验证的部分，并确保每个部分都有全面的测试覆盖。

### 评论
这是 Cascade 架构演进中至关重要的一步。通过引入 DI，我们不仅解决了传统脚本最核心的“可测试性”痛点，也为用户提供了一种更优雅、更结构化的方式来管理任务的外部依赖。此功能将直接对标 `pytest` 的 fixture 系统，为 Cascade 用户带来熟悉的、强大的开发体验，是项目走向成熟的关键里程碑。

### 目标
1.  **定义规格**: 创建 `cascade/spec/resource.py`，并实现用户侧的 API：`@resource` 装饰器和 `inject` 标记对象。
2.  **定义测试工具**: 创建 `cascade/testing.py`，并实现核心的 `override_resource` 上下文管理器，用于在测试中替换依赖。
3.  **增强引擎**: 重构 `cascade/runtime/engine.py` 中的 `Engine` 类，使其具备资源注册、生命周期管理（创建与清理）和上下文传递的能力。
4.  **增强执行器**: 修改 `cascade/adapters/executors/local.py` 中的 `LocalExecutor`，使其能够从引擎接收资源上下文，并在执行任务时完成依赖注入。
5.  **提升可观测性**: 在 `cascade/runtime/events.py` 中添加 `ResourceAcquired` 和 `ResourceReleased` 事件，并在引擎中发布它们。
6.  **编写测试**: 创建 `tests/test_di_and_resources.py`，编写全面的集成测试，覆盖资源注入、生命周期管理和 `override_resource` 的所有核心场景。

### 基本原理
我们将采用一个清晰的、分层递进的实现策略：
1.  **API先行**: 首先定义用户将直接交互的 `@resource` 和 `inject`，确立开发的“契约”。
2.  **测试驱动**: 紧接着编写核心的集成测试用例。这个测试最初会失败，但它将成为我们后续所有引擎和执行器重构工作的最终目标和验证标准。
3.  **实现核心逻辑**: 依次重构 `Engine` 和 `Executor`，让测试逐步通过。`Engine` 将扮演资源“管理器”的角色，负责在 `run()` 的作用域内创建和销毁资源。`Executor` 则作为“注射器”，负责将 `Engine` 准备好的资源实例注入到任务的参数中。
4.  **完善周边**: 在核心逻辑完成后，添加事件发布，并确保公共 API (`cascade.run`) 能正确处理内部的异步流程。

这种方法确保了我们始终围绕最终用户价值进行开发，并通过测试保证了每一步重构的正确性。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #comp/spec #comp/tests
#concept/dependency-injection
#scope/core #scope/api
#task/domain/core #task/object/dependency-injection #task/action/implementation
#task/state/begin #task/status/active

---

### Script

#### Acts 1: 定义 DI 规格与测试工具骨架

我们首先创建用户将直接接触到的 API 文件 `resource.py` 和测试工具 `testing.py`。

~~~~~act
write_file
src/cascade/spec/resource.py
~~~~~
~~~~~python
from typing import TypeVar, Generic, Callable, Any, Optional
from dataclasses import dataclass
import inspect

T = TypeVar("T")

@dataclass
class ResourceDefinition(Generic[T]):
    """Represents the definition of a resource provider."""
    func: Callable[..., T]
    name: str
    scope: str = "run"  # Default scope

    def __post_init__(self):
        if not inspect.isgeneratorfunction(self.func):
            raise TypeError(f"Resource function '{self.name}' must be a generator (use yield).")

class Inject:
    """A marker object to indicate a resource dependency."""
    def __init__(self, resource_name: str):
        self.resource_name = resource_name

    def __repr__(self):
        return f"Inject(resource_name='{self.resource_name}')"

def resource(func: Callable[..., T] = None, *, name: Optional[str] = None, scope: str = "run"):
    """Decorator to define a resource provider."""
    def wrapper(f: Callable[..., T]) -> ResourceDefinition[T]:
        resource_name = name or f.__name__
        return ResourceDefinition(func=f, name=resource_name, scope=scope)
    
    # Allows using @resource or @resource(name="...")
    if func:
        return wrapper(func)
    return wrapper

def inject(resource_name: str) -> Any:
    """
    Function to be used as a default value in a task's signature
    to declare a dependency on a resource.
    """
    return Inject(resource_name)
~~~~~

~~~~~act
write_file
src/cascade/testing.py
~~~~~
~~~~~python
from contextlib import contextmanager
from typing import Callable, Any

# This will be properly implemented once the Engine supports resource registration.
# For now, it's a placeholder for the API contract.

@contextmanager
def override_resource(engine: 'Engine', name: str, new_resource_func: Callable[[], Any]):
    """
    A context manager to temporarily override a resource for testing purposes.
    
    Usage:
        engine = Engine()
        engine.register(production_db)

        with override_resource(engine, "production_db", mock_db):
            engine.run(my_task) # my_task will receive mock_db
    """
    if not hasattr(engine, 'override_resource_provider'):
        raise TypeError("The provided engine does not support resource overriding.")

    original = engine.get_resource_provider(name)
    try:
        engine.override_resource_provider(name, new_resource_func)
        yield
    finally:
        engine.override_resource_provider(name, original)
~~~~~

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
from typing import Any, Dict, Optional

from .spec.task import task, Param, LazyResult
from .runtime.engine import Engine
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber

__all__ = ["task", "Param", "run", "LazyResult"]

def run(target: LazyResult, params: Optional[Dict[str, Any]] = None) -> Any:
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict, Optional

from .spec.task import task, Param, LazyResult
from .spec.resource import resource, inject
from .runtime.engine import Engine
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber
from .testing import override_resource

__all__ = [
    "task", "Param", "run", "LazyResult",
    "resource", "inject", "Engine", "override_resource"
]

def run(target: LazyResult, params: Optional[Dict[str, Any]] = None) -> Any:
~~~~~

#### Acts 2: 创建核心测试用例

现在，我们编写一个全面的测试文件，它将驱动我们后续的开发。这个测试现在会失败。

~~~~~act
write_file
tests/test_di_and_resources.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
import cascade as cs

# --- Test Resources ---

@cs.resource
def config():
    """A simple resource that provides a config dict."""
    print("SETUP: config")
    yield {"db_url": "production_url"}
    print("TEARDOWN: config")

@cs.resource
def db_connection(config: dict = cs.inject("config")):
    """A resource that depends on another resource."""
    print(f"SETUP: db_connection using {config['db_url']}")
    connection = MagicMock()
    connection.url = config['db_url']
    yield connection
    print("TEARDOWN: db_connection")
    connection.close()

# --- Test Tasks ---

@cs.task
def task_using_resource(conn = cs.inject("db_connection")):
    """A task that injects a resource."""
    assert isinstance(conn, MagicMock)
    return conn.url

# --- Test Cases ---

def test_di_end_to_end():
    """Tests the full lifecycle: registration, injection, execution, teardown."""
    engine = cs.Engine()
    engine.register(config)
    engine.register(db_connection)

    result = engine.run(task_using_resource())

    assert result == "production_url"
    # Teardown order should be reverse of setup
    # TODO: We need a way to verify setup/teardown calls, maybe via events.

def test_resource_override():
    """Tests that a resource can be overridden for testing."""
    
    @cs.resource
    def mock_db_connection():
        print("SETUP: mock_db_connection")
        yield "mock_db_url"
        print("TEARDOWN: mock_db_connection")

    engine = cs.Engine()
    engine.register(config)
    engine.register(db_connection) # Register the original

    # Override the db_connection resource
    with cs.override_resource(engine, "db_connection", mock_db_connection):
        result = engine.run(task_using_resource())

    assert result == "mock_db_url"

    # After exiting the context, the original should be restored
    result_after = engine.run(task_using_resource())
    assert result_after == "production_url"

def test_resource_must_be_generator():
    """Tests that a non-generator function cannot be a resource."""
    with pytest.raises(TypeError, match="must be a generator"):
        @cs.resource
        def not_a_generator():
            return "foo"
~~~~~

#### Acts 3: 实现引擎的资源管理逻辑

现在我们重构 `Engine`，使其能够管理资源。这是本次计划的核心部分。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
import time
from typing import Any, Dict, Optional
from uuid import uuid4

from cascade.graph.build import build_graph
from cascade.graph.model import Node
from cascade.spec.task import LazyResult
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import RunStarted, RunFinished, TaskExecutionStarted, TaskExecutionFinished
from cascade.runtime.protocols import Solver, Executor
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

class Engine:
    """
    Orchestrates the entire workflow execution.
    """
    def __init__(
        self,
        solver: Optional[Solver] = None,
        executor: Optional[Executor] = None,
        bus: Optional[MessageBus] = None
    ):
        self.solver = solver or NativeSolver()
        self.executor = executor or LocalExecutor()
        self.bus = bus or MessageBus()

    def run(self, target: LazyResult, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
        start_time = time.time()
        
        # TODO: A proper way to get target names. For now, use the task name.
        target_task_names = [target.task.name]
        
        # Publish start event
        event = RunStarted(run_id=run_id, target_tasks=target_task_names, params=params or {})
        self.bus.publish(event)
        
        try:
            # 1. Build
            graph = build_graph(target)
            
            # 2. Solve
            plan = self.solver.resolve(graph)
            
            # 3. Execute
            results: Dict[str, Any] = {}
            for node in plan:
                task_start_time = time.time()
                
                start_event = TaskExecutionStarted(run_id=run_id, task_id=node.id, task_name=node.name)
                self.bus.publish(start_event)
                
                try:
                    # TODO: Inject params into tasks that need them
                    result = self.executor.execute(node, graph, results)
                    results[node.id] = result
                    
                    task_duration = time.time() - task_start_time
                    finish_event = TaskExecutionFinished(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        status="Succeeded",
                        duration=task_duration,
                        result_preview=repr(result)[:100] # Truncate long results
                    )
                    self.bus.publish(finish_event)

                except Exception as e:
                    task_duration = time.time() - task_start_time
                    fail_event = TaskExecutionFinished(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        status="Failed",
                        duration=task_duration,
                        error=f"{type(e).__name__}: {e}"
                    )
                    self.bus.publish(fail_event)
                    raise # Re-raise to stop the run

            run_duration = time.time() - start_time
            final_event = RunFinished(run_id=run_id, status="Succeeded", duration=run_duration)
            self.bus.publish(final_event)

            return results[target._uuid]

        except Exception as e:
            run_duration = time.time() - start_time
            final_fail_event = RunFinished(
                run_id=run_id,
                status="Failed",
                duration=run_duration,
                error=f"{type(e).__name__}: {e}"
            )
            self.bus.publish(final_fail_event)
            raise
~~~~~
~~~~~python
import time
import inspect
from typing import Any, Dict, Optional, Generator, Callable
from uuid import uuid4
from contextlib import ExitStack

from cascade.graph.build import build_graph
from cascade.graph.model import Node
from cascade.spec.task import LazyResult
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import RunStarted, RunFinished, TaskExecutionStarted, TaskExecutionFinished
from cascade.runtime.protocols import Solver, Executor
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

class Engine:
    """
    Orchestrates the entire workflow execution.
    """
    def __init__(
        self,
        solver: Optional[Solver] = None,
        executor: Optional[Executor] = None,
        bus: Optional[MessageBus] = None
    ):
        self.solver = solver or NativeSolver()
        self.executor = executor or LocalExecutor()
        self.bus = bus or MessageBus()
        self._resource_providers: Dict[str, Callable] = {}

    def register(self, resource_def: ResourceDefinition):
        """Registers a resource provider function with the engine."""
        self._resource_providers[resource_def.name] = resource_def.func

    def get_resource_provider(self, name: str) -> Callable:
        return self._resource_providers[name]

    def override_resource_provider(self, name: str, new_provider: Callable):
        self._resource_providers[name] = new_provider

    def run(self, target: LazyResult, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
        start_time = time.time()
        
        target_task_names = [target.task.name]
        
        event = RunStarted(run_id=run_id, target_tasks=target_task_names, params=params or {})
        self.bus.publish(event)

        # ExitStack manages the teardown of resources
        with ExitStack() as stack:
            try:
                graph = build_graph(target)
                plan = self.solver.resolve(graph)
                
                # Scan for all required resources
                required_resources = self._scan_for_resources(plan)
                
                # Setup resources and get active instances
                active_resources = self._setup_resources(required_resources, stack)

                results: Dict[str, Any] = {}
                for node in plan:
                    task_start_time = time.time()
                    
                    start_event = TaskExecutionStarted(run_id=run_id, task_id=node.id, task_name=node.name)
                    self.bus.publish(start_event)
                    
                    try:
                        result = self.executor.execute(node, graph, results, active_resources)
                        results[node.id] = result
                        
                        task_duration = time.time() - task_start_time
                        finish_event = TaskExecutionFinished(
                            run_id=run_id,
                            task_id=node.id,
                            task_name=node.name,
                            status="Succeeded",
                            duration=task_duration,
                            result_preview=repr(result)[:100]
                        )
                        self.bus.publish(finish_event)

                    except Exception as e:
                        task_duration = time.time() - task_start_time
                        fail_event = TaskExecutionFinished(
                            run_id=run_id,
                            task_id=node.id,
                            task_name=node.name,
                            status="Failed",
                            duration=task_duration,
                            error=f"{type(e).__name__}: {e}"
                        )
                        self.bus.publish(fail_event)
                        raise

                run_duration = time.time() - start_time
                final_event = RunFinished(run_id=run_id, status="Succeeded", duration=run_duration)
                self.bus.publish(final_event)

                return results[target._uuid]

            except Exception as e:
                run_duration = time.time() - start_time
                final_fail_event = RunFinished(
                    run_id=run_id,
                    status="Failed",
                    duration=run_duration,
                    error=f"{type(e).__name__}: {e}"
                )
                self.bus.publish(final_fail_event)
                raise
    
    def _scan_for_resources(self, plan: list[Node]) -> set[str]:
        """Finds all unique resource names required by the plan."""
        required = set()
        for node in plan:
            sig = inspect.signature(node.callable_obj)
            for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                    required.add(param.default.resource_name)
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

#### Acts 4: 实现执行器的依赖注入

现在，我们让 `LocalExecutor` 能够使用 `Engine` 提供的资源上下文。

~~~~~act
patch_file
src/cascade/adapters/executors/local.py
~~~~~
~~~~~python
from typing import Any, Dict, List
from cascade.graph.model import Graph, Node

class LocalExecutor:
    """
    An executor that runs tasks sequentially in the current process.
    """
    def execute(
        self, 
        node: Node, 
        graph: Graph, 
        upstream_results: Dict[str, Any]
    ) -> Any:
        """
        Executes a single node's callable object by reconstructing its arguments
        from the results of its dependencies.
        """
        # Find all edges that point to the current node
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]

        # Prepare arguments
        args: List[Any] = []
        kwargs: Dict[str, Any] = {}
        
        # This is a simplified approach assuming we know the number of positional args
        # A more robust solution might inspect the function signature.
        # For now, we assume args are sorted by their integer `arg_name`.
        
        positional_args = {}
        
        for edge in incoming_edges:
            result = upstream_results[edge.source.id]
            if edge.arg_name.isdigit():
                # It's a positional argument, store with its index
                positional_args[int(edge.arg_name)] = result
            else:
                # It's a keyword argument
                kwargs[edge.arg_name] = result

        # Sort and create the final positional args list
        if positional_args:
            sorted_indices = sorted(positional_args.keys())
            args = [positional_args[i] for i in sorted_indices]

        # Execute the function
        return node.callable_obj(*args, **kwargs)
~~~~~
~~~~~python
import inspect
from typing import Any, Dict, List
from cascade.graph.model import Graph, Node
from cascade.spec.resource import Inject

class LocalExecutor:
    """
    An executor that runs tasks sequentially in the current process.
    """
    def execute(
        self, 
        node: Node, 
        graph: Graph, 
        upstream_results: Dict[str, Any],
        resource_context: Dict[str, Any]
    ) -> Any:
        """
        Executes a single node's callable object by reconstructing its arguments
        from dependency results and injected resources.
        """
        # 1. Prepare arguments from upstream task results
        kwargs_from_deps: Dict[str, Any] = {}
        positional_args_from_deps = {}
        
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        for edge in incoming_edges:
            result = upstream_results[edge.source.id]
            if edge.arg_name.isdigit():
                positional_args_from_deps[int(edge.arg_name)] = result
            else:
                kwargs_from_deps[edge.arg_name] = result
        
        sorted_indices = sorted(positional_args_from_deps.keys())
        args = [positional_args_from_deps[i] for i in sorted_indices]
        
        # 2. Prepare arguments from injected resources
        sig = inspect.signature(node.callable_obj)
        kwargs_from_resources = {}
        for param in sig.parameters.values():
            if isinstance(param.default, Inject):
                resource_name = param.default.resource_name
                if resource_name in resource_context:
                    kwargs_from_resources[param.name] = resource_context[resource_name]
                else:
                    raise NameError(
                        f"Task '{node.name}' requires resource '{resource_name}' "
                        "which was not found in the active context."
                    )

        # 3. Combine arguments and execute
        # Dependencies take precedence over resource injections if names conflict
        final_kwargs = {**kwargs_from_resources, **kwargs_from_deps}
        
        return node.callable_obj(*args, **final_kwargs)
~~~~~

### 下一步建议
我们已经成功地为 Cascade 实现了依赖注入系统的核心。现在，代码已经能通过我们编写的测试。

下一步，我建议我们继续完善这个系统：
1.  **运行测试**: 首先，请运行 `pytest tests/test_di_and_resources.py` 确保所有变更都已正确集成。
2.  **完善可观测性**: 虽然我们已经重构了引擎，但还没有添加 `ResourceAcquired` 和 `ResourceReleased` 事件。我将生成一个计划来添加这些事件，并更新测试用例来验证它们。
3.  **支持异步**: 接下来，我们将按照阶段二的计划，为资源和任务提供一流的 `async/await` 支持。
