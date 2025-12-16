简要回答
这是一个非常扎实且必要的架构升级。通过在核心层引入资源感知，`Cascade` 将从简单的任务执行器转变为能够处理异构负载的智能调度系统。我将生成一个计划，在不引入任何第三方依赖的情况下，实现包括 `ResourceManager`、图构建增强、执行层过滤和引擎集成的完整资源调度 MVP。

## [WIP] feat(core): 实现资源感知调度与配额管理 (MVP)

### 用户需求
实现一个零依赖的资源感知调度系统，使 `Engine` 能够在执行任务前检查、等待并获取任务声明所需的资源（例如 CPU, GPU, 内存）。同时，支持动态资源约束，即资源的需求量本身可以是一个上游任务的计算结果。

### 评论
这个计划触及了系统的多个核心组件。引入 `ResourceManager` 并将其集成到 `Engine` 的主循环中，将赋予 `Cascade` 处理并发和资源争用的能力。特别是通过特定的边类型处理动态资源约束，体现了 `Cascade` “万物皆为可计算值” 的一致性设计。

### 目标
1.  创建 `src/cascade/runtime/resource_manager.py`，实现基于 `asyncio.Condition` 的资源计数和等待逻辑。
2.  修改 `src/cascade/graph/build.py`，使其能够扫描任务的 `constraints`，并将动态约束值（`LazyResult`）作为隐式依赖加入图中。
3.  修改 `src/cascade/adapters/executors/local.py`，使其忽略约束依赖边，防止它们干扰正常的参数注入。
4.  修改 `src/cascade/runtime/engine.py`，在任务执行生命周期中集成资源的获取与释放，并解析动态约束。
5.  修改 `src/cascade/__init__.py` 的 `run` 函数，允许用户传入系统总资源容量。
6.  编写测试验证资源限制是否能正确地串行化任务执行。

### 基本原理
-   **ResourceManager**: 选择 `asyncio.Condition` 而非 `Semaphore` 是因为资源请求是多维度的（如 `{gpu:1, mem:4}`），标准信号量无法处理这种原子性的多资源请求。
-   **GraphBuilder 增强**: 为了保证拓扑排序正确，动态计算的资源需求量必须被视为“上游依赖”。通过添加特殊前缀的边，我们既利用了现有的求解器，又能在执行时通过名称过滤将其与普通数据参数区分开。
-   **Engine 集成**: 将资源获取放在 `_execute_node_with_policies` 中最靠近执行点的位置，能够最大限度地减少资源占用时间。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/runtime #scope/core #task/domain/runtime #task/object/resource-manager #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建资源管理器 (ResourceManager)

实现一个线程安全的、基于异步条件变量的资源管理器。它维护当前的资源使用量，并提供阻塞式的 `acquire` 和非阻塞的 `release` 方法。

~~~~~act
write_file
src/cascade/runtime/resource_manager.py
~~~~~
~~~~~python
import asyncio
from typing import Dict, Union, Optional

class ResourceManager:
    """
    Manages system resources and ensures task concurrency respects resource constraints.
    Uses asyncio.Condition to coordinate resource acquisition.
    """

    def __init__(self, capacity: Optional[Dict[str, Union[int, float]]] = None):
        # Total capacity of the system (e.g., {"gpu": 2, "memory_gb": 16})
        # If a resource is not in capacity dict, it is assumed to be infinite.
        self._capacity: Dict[str, float] = {}
        if capacity:
            self._capacity = {k: float(v) for k, v in capacity.items()}
        
        # Current usage
        self._usage: Dict[str, float] = {k: 0.0 for k in self._capacity}
        
        # Condition variable for waiting tasks
        self._condition = asyncio.Condition()

    def set_capacity(self, capacity: Dict[str, Union[int, float]]):
        """Updates system capacity configuration."""
        self._capacity = {k: float(v) for k, v in capacity.items()}
        # Initialize usage for new keys if needed
        for k in self._capacity:
            if k not in self._usage:
                self._usage[k] = 0.0

    async def acquire(self, requirements: Dict[str, Union[int, float]]):
        """
        Atomically acquires the requested resources. 
        Waits until all resources are available.
        """
        if not requirements:
            return

        async with self._condition:
            # Check if request is impossible to satisfy even when empty
            self._validate_feasibility(requirements)

            while not self._can_acquire(requirements):
                await self._condition.wait()
            
            # Commit acquisition
            for res, amount in requirements.items():
                if res in self._capacity:
                    self._usage[res] += float(amount)

    async def release(self, requirements: Dict[str, Union[int, float]]):
        """
        Releases the resources and notifies waiting tasks.
        """
        if not requirements:
            return

        async with self._condition:
            for res, amount in requirements.items():
                if res in self._capacity:
                    self._usage[res] -= float(amount)
                    # Prevent floating point drift below zero
                    if self._usage[res] < 0:
                        self._usage[res] = 0.0
            
            # Notify all waiting tasks to re-check their conditions
            self._condition.notify_all()

    def _can_acquire(self, requirements: Dict[str, Union[int, float]]) -> bool:
        """Internal check to see if resources are currently available."""
        for res, amount in requirements.items():
            if res not in self._capacity:
                continue # Unmanaged resources are always available
            
            if self._usage[res] + float(amount) > self._capacity[res]:
                return False
        return True

    def _validate_feasibility(self, requirements: Dict[str, Union[int, float]]):
        """Checks if the requirement exceeds total system capacity."""
        for res, amount in requirements.items():
            if res in self._capacity:
                if float(amount) > self._capacity[res]:
                    raise ValueError(
                        f"Resource requirement '{res}={amount}' exceeds total system capacity ({self._capacity[res]})."
                    )
~~~~~

#### Acts 2: 增强图构建逻辑 (GraphBuilder)

修改 `GraphBuilder`，使其在处理 `LazyResult` 节点时，也会扫描其 attached 的 `_constraints`。如果约束值本身是一个 `LazyResult`（动态约束），则建立一条特殊的隐式依赖边。

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~python
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        self._process_dependencies(node, result.args, is_kwargs=False)
        self._process_dependencies(node, result.kwargs, is_kwargs=True)

        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(source=source_node, target=node, arg_name="_condition")
            self.graph.add_edge(edge)

        return node
~~~~~
~~~~~python
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        self._process_dependencies(node, result.args, is_kwargs=False)
        self._process_dependencies(node, result.kwargs, is_kwargs=True)

        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(source=source_node, target=node, arg_name="_condition")
            self.graph.add_edge(edge)

        # Process dynamic constraints
        if result._constraints and not result._constraints.is_empty():
            from cascade.spec.task import LazyResult, MappedLazyResult
            for res_name, req_value in result._constraints.requirements.items():
                if isinstance(req_value, (LazyResult, MappedLazyResult)):
                    source_node = self._visit(req_value)
                    # Use a special prefix for constraint edges so executors can ignore them
                    edge = Edge(
                        source=source_node, 
                        target=node, 
                        arg_name=f"_constraint:{res_name}"
                    )
                    self.graph.add_edge(edge)

        return node
~~~~~

#### Acts 3: 修改执行器以忽略约束边 (LocalExecutor)

修改 `LocalExecutor`，在收集任务参数时，显式过滤掉那些用于资源约束计算的边（以 `_constraint:` 开机），防止它们被误当作函数参数注入。

~~~~~act
patch_file
src/cascade/adapters/executors/local.py
~~~~~
~~~~~python
            # Skip implicit dependencies (used for routing/ordering only)
            if edge.arg_name == "_implicit_dependency":
                continue

            result = upstream_results[edge.source.id]
~~~~~
~~~~~python
            # Skip implicit dependencies (used for routing/ordering only)
            if edge.arg_name == "_implicit_dependency":
                continue

            # Skip dynamic constraint dependencies (handled by Engine resource manager)
            if edge.arg_name.startswith("_constraint:"):
                continue

            result = upstream_results[edge.source.id]
~~~~~

#### Acts 4: 集成资源管理到 Engine

这是核心变更。
1.  在 `Engine` 初始化时接受 `system_resources`。
2.  实现 `_resolve_constraints` 方法，用于解析动态约束值。
3.  在 `_execute_node_with_policies` 中，在任务运行前调用 `acquire`，在 `finally` 中调用 `release`。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


class Engine:
~~~~~
~~~~~python
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.resource_manager import ResourceManager
from cascade.spec.task import LazyResult, MappedLazyResult


class Engine:
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
        self,
        solver: Optional[Solver] = None,
        executor: Optional[Executor] = None,
        bus: Optional[MessageBus] = None,
    ):
        self.solver = solver or NativeSolver()
        self.executor = executor or LocalExecutor()
        self.bus = bus or MessageBus()
        self._resource_providers: Dict[str, Callable] = {}
~~~~~
~~~~~python
        self,
        solver: Optional[Solver] = None,
        executor: Optional[Executor] = None,
        bus: Optional[MessageBus] = None,
        system_resources: Optional[Dict[str, Any]] = None,
    ):
        self.solver = solver or NativeSolver()
        self.executor = executor or LocalExecutor()
        self.bus = bus or MessageBus()
        self.resource_manager = ResourceManager(capacity=system_resources)
        self._resource_providers: Dict[str, Callable] = {}
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def _execute_node_with_policies(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> Any:
        task_start_time = time.time()

        # 0. Check Cache
        if node.cache_policy:
~~~~~
~~~~~python
    async def _execute_node_with_policies(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> Any:
        # Resolve resource requirements
        requirements = self._resolve_constraints(node, graph, upstream_results)
        
        # Acquire resources (this may block)
        await self.resource_manager.acquire(requirements)
        
        try:
            return await self._execute_node_internal(
                node, graph, upstream_results, active_resources, run_id, requirements
            )
        finally:
            # Always release resources
            await self.resource_manager.release(requirements)

    def _resolve_constraints(
        self, node: Node, graph: Graph, upstream_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolves dynamic constraints to concrete values."""
        if not node.constraints or node.constraints.is_empty():
            return {}

        resolved = {}
        for res, amount in node.constraints.requirements.items():
            if isinstance(amount, (LazyResult, MappedLazyResult)):
                # Find the upstream source for this dynamic constraint using the special edge prefix
                # We can also lookup by ID since we know it's a LazyResult, but edge lookup is safer graph-wise.
                # Actually, simply using the result of the LazyResult._uuid is enough because
                # the graph builder ensures it's in upstream_results.
                if amount._uuid in upstream_results:
                    resolved[res] = upstream_results[amount._uuid]
                else:
                    # Depending on skip logic, this might be missing. 
                    # If upstream was skipped, we probably shouldn't be here, 
                    # or we should fail because we can't determine resource usage.
                    raise RuntimeError(
                        f"Could not resolve dynamic resource constraint '{res}' for task '{node.name}'. "
                        "Upstream dependency result missing."
                    )
            else:
                resolved[res] = amount
        return resolved

    async def _execute_node_internal(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        requirements: Dict[str, Any], # Passed for logging if needed
    ) -> Any:
        task_start_time = time.time()

        # 0. Check Cache
        if node.cache_policy:
~~~~~

#### Acts 5: 更新公共 API (run)

更新顶层 `run` 函数，暴露 `system_resources` 参数，使用户能够配置系统容量。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
def run(target: LazyResult, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.

    This is the primary entry point for users. It sets up a default
    engine with a human-readable logger.
    """
    bus = MessageBus()
    # Attach the default logger
    HumanReadableLogSubscriber(bus)

    engine = Engine(bus=bus)

    return asyncio.run(engine.run(target, params=params))
~~~~~
~~~~~python
def run(
    target: LazyResult, 
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.

    Args:
        target: The workflow target.
        params: Runtime parameters.
        system_resources: A dictionary defining total system capacity 
                          (e.g. {"gpu": 1, "threads": 4}).
    """
    bus = MessageBus()
    # Attach the default logger
    HumanReadableLogSubscriber(bus)

    engine = Engine(bus=bus, system_resources=system_resources)

    return asyncio.run(engine.run(target, params=params))
~~~~~

#### Acts 6: 创建资源调度集成测试

编写一个测试，通过设置有限的资源（并发度为1），验证两个本应并行的任务是否被强制串行执行。

~~~~~act
write_file
tests/integration/test_resource_scheduling.py
~~~~~
~~~~~python
import pytest
import asyncio
import time
import cascade as cs

@pytest.mark.asyncio
async def test_resource_concurrency_limit():
    """
    Test that system capacity limits task concurrency.
    We set up a system with 'slots=1', and try to run 2 tasks in parallel that each require 'slots=1'.
    They should execute sequentially, doubling the total time.
    """
    
    @cs.task
    async def slow_task(name: str):
        # Simulate work
        await asyncio.sleep(0.1)
        return time.time()

    # Define two parallel tasks
    t1 = slow_task("t1").with_constraints(slots=1)
    t2 = slow_task("t2").with_constraints(slots=1)
    
    # Run them (we need a way to run both, creating a list)
    @cs.task
    def gather(a, b):
        return a, b

    workflow = gather(t1, t2)

    start_time = time.time()
    
    # Run with limited capacity: only 1 slot available
    # Because both tasks need 1 slot, they must run one after another.
    result = cs.run(workflow, system_resources={"slots": 1})
    
    duration = time.time() - start_time
    t1_end, t2_end = result
    
    # In parallel, it would take ~0.1s. In serial, ~0.2s.
    # Allow some buffer for overhead.
    assert duration >= 0.2
    
    # One must finish before the other, roughly.
    assert abs(t1_end - t2_end) >= 0.1

@pytest.mark.asyncio
async def test_dynamic_resource_constraint():
    """
    Test that a task can request resources based on an upstream calculation.
    """
    
    @cs.task
    def calculate_cpu_needs():
        return 2

    @cs.task
    def cpu_heavy_task():
        return "Done"

    # CPU needs are determined dynamically
    needs = calculate_cpu_needs()
    
    # The task requests 'cpu' equal to the result of 'needs' (2)
    job = cpu_heavy_task().with_constraints(cpu=needs)

    # We set system capacity to 4.
    # This test mainly verifies the graph building and resolution logic works without error.
    result = cs.run(job, system_resources={"cpu": 4})
    
    assert result == "Done"

@pytest.mark.asyncio
async def test_insufficient_resources_deadlock():
    """
    Test that requesting more resources than available raises an error immediately
    (feasibility check), rather than hanging indefinitely.
    """
    
    @cs.task
    def massive_job():
        return "Should not run"
        
    job = massive_job().with_constraints(memory_gb=64)
    
    # System only has 16GB
    with pytest.raises(ValueError, match="exceeds total system capacity"):
        cs.run(job, system_resources={"memory_gb": 16})
~~~~~
