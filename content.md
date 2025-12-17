简要回答
好的，我将开始执行路线图的第一部分，使 `.map()` 返回的 `MappedLazyResult` 支持策略链式调用（如 `with_retry`）。这涉及到从 Spec 定义到运行时图构建，再到执行引擎的完整链路更新。

## [WIP] feat(core): 支持对 .map() 结果应用策略配置

### 用户需求
用户希望能够直接对批量任务操作 `.map(...)` 的结果应用 `with_retry`、`with_cache` 和 `with_constraints` 等策略配置，并期望这些策略能自动传播到生成的每一个子任务中。

### 评论
当前 `MappedLazyResult` 缺乏这些策略字段和方法，导致无法为批量任务统一配置行为。这是一个关键的开发者体验 (DX) 缺失。实现此功能需要确保策略数据能从 Spec (`MappedLazyResult`) 流转到 Graph (`Node`)，最终在 Runtime (`Engine`) 展开子任务时被应用。

### 目标
1.  **Spec 层**: 在 `MappedLazyResult` 中添加策略字段，并在 `Task` 模块中为其绑定链式配置方法。
2.  **Graph 层**: 更新 `GraphBuilder`，使其在构建 `map` 类型节点时，能从 `MappedLazyResult` 提取并存储策略信息。
3.  **Runtime 层**: 更新 `Engine` 的 `_execute_map_node` 方法，在动态生成子任务时，将父节点的策略复制给子任务。
4.  **Testing**: 添加集成测试验证重试和约束策略在 `.map()` 场景下的有效性。

### 基本原理
通过鸭子类型 (Duck Typing) 复用现有的策略配置方法（`_with_retry` 等），并利用 `GraphBuilder` 将这些配置持久化到 `Node` 对象中。Engine 在执行 map 节点时，充当了一个“动态图生成器”，它负责将父节点的配置模板实例化到每一个动态生成的子节点上，从而实现策略的透明传播。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/runtime #concept/state #scope/api #ai/instruct #task/domain/core #task/object/map-policies #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 更新 `MappedLazyResult` 定义
在 `lazy_types.py` 中为 `MappedLazyResult` 添加缺失的策略字段。

~~~~~act
patch_file
src/cascade/spec/lazy_types.py
~~~~~
~~~~~python
    factory: Any  # Should be LazyFactory
    mapping_kwargs: Dict[str, Any]
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _condition: Optional[LazyResult] = None

    def __hash__(self):
        return hash(self._uuid)
~~~~~
~~~~~python
    factory: Any  # Should be LazyFactory
    mapping_kwargs: Dict[str, Any]
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _condition: Optional[LazyResult] = None
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[Any] = None  # CachePolicy
    _constraints: Optional[Any] = None  # ResourceConstraint

    def __hash__(self):
        return hash(self._uuid)
~~~~~

#### Acts 2: 为 `MappedLazyResult` 绑定配置方法
在 `task.py` 中，将 `with_retry`、`with_cache` 和 `with_constraints` 方法绑定到 `MappedLazyResult` 类上。

~~~~~act
patch_file
src/cascade/spec/task.py
~~~~~
~~~~~python
LazyResult.with_constraints = _with_constraints


def _mapped_run_if(self: MappedLazyResult, condition: LazyResult) -> MappedLazyResult:
    self._condition = condition
    return self


MappedLazyResult.run_if = _mapped_run_if
~~~~~
~~~~~python
LazyResult.with_constraints = _with_constraints


# --- MappedLazyResult Mixins ---

def _mapped_run_if(self: MappedLazyResult, condition: LazyResult) -> MappedLazyResult:
    self._condition = condition
    return self


MappedLazyResult.run_if = _mapped_run_if
MappedLazyResult.with_retry = _with_retry
MappedLazyResult.with_cache = _with_cache
MappedLazyResult.with_constraints = _with_constraints
~~~~~

#### Acts 3: 更新 `GraphBuilder` 以传递策略
修改 `build.py`，确保在从 `MappedLazyResult` 构建 `Node` 时，将策略信息复制到节点对象中。

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~python
        node = Node(
            id=result._uuid,
            name=f"map({getattr(result.factory, 'name', 'factory')})",
            node_type="map",
            mapping_factory=result.factory,
        )
        self.graph.add_node(node)
~~~~~
~~~~~python
        node = Node(
            id=result._uuid,
            name=f"map({getattr(result.factory, 'name', 'factory')})",
            node_type="map",
            mapping_factory=result.factory,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
        )
        self.graph.add_node(node)
~~~~~

#### Acts 4: 更新 `Engine` 以传播策略
修改 `engine.py` 中的 `_execute_map_node`，在生成子任务时应用父节点的策略。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
        sub_targets = []
        for i in range(first_len):
            item_kwargs = {k: v[i] for k, v in kwargs.items()}
            # Factory creates a LazyResult
            sub_target = factory(**item_kwargs)
            sub_targets.append(sub_target)

        coros = [
            self._execute_graph(target, params, active_resources, run_id)
            for target in sub_targets
        ]
~~~~~
~~~~~python
        sub_targets = []
        for i in range(first_len):
            item_kwargs = {k: v[i] for k, v in kwargs.items()}
            # Factory creates a LazyResult
            sub_target = factory(**item_kwargs)
            
            # Propagate policies from the map node to the sub-task
            if node.retry_policy:
                sub_target._retry_policy = node.retry_policy
            if node.cache_policy:
                sub_target._cache_policy = node.cache_policy
            if node.constraints:
                sub_target._constraints = node.constraints

            sub_targets.append(sub_target)

        coros = [
            self._execute_graph(target, params, active_resources, run_id)
            for target in sub_targets
        ]
~~~~~

#### Acts 5: 添加测试用例
创建 `tests/runtime/test_map_policies.py`，验证重试和约束策略在 `map` 操作中的行为。

~~~~~act
write_file
tests/runtime/test_map_policies.py
~~~~~
~~~~~python
import pytest
import asyncio
import time
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import TaskRetrying, Event
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver

class SpySubscriber:
    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        return [e for e in self.events if isinstance(e, event_type)]

@pytest.mark.asyncio
async def test_map_with_retry_policy():
    """
    Test that .with_retry() applied to .map() is propagated to sub-tasks.
    """
    call_counts = {}

    @cs.task
    def flaky_process(x):
        count = call_counts.get(x, 0)
        call_counts[x] = count + 1
        
        # Fail on first attempt for each item
        if count == 0:
            raise ValueError(f"Fail {x}")
        return x

    # Map over 3 items, expecting each to fail once then succeed
    # Total calls should be 6 (3 initial + 3 retries)
    inputs = [1, 2, 3]
    mapped = flaky_process.map(x=inputs).with_retry(max_attempts=2, delay=0.01)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    # Use a dummy gather task to run everything
    @cs.task
    def gather(results):
        return results

    # We can't directly run mapped result in v1.3 because it returns a list,
    # and Engine.run expects a single LazyResult.
    # But wait, Engine.run builds a graph. If we pass a MappedLazyResult,
    # GraphBuilder handles it (node_type="map").
    # However, Engine.run returns the result of the target node.
    # For a map node, _execute_map_node returns a list of results.
    # So we CAN run mapped result directly.
    
    results = await engine.run(mapped)
    
    assert sorted(results) == [1, 2, 3]
    
    # Check retries occurred
    retries = spy.events_of_type(TaskRetrying)
    assert len(retries) == 3
    
    # Check call counts
    assert sum(call_counts.values()) == 6
    assert all(c == 2 for c in call_counts.values())

@pytest.mark.asyncio
async def test_map_with_constraints_policy():
    """
    Test that .with_constraints() applied to .map() limits concurrency of sub-tasks.
    """
    @cs.task
    async def slow_task(x):
        await asyncio.sleep(0.05)
        return time.time()

    # 4 tasks, but system has only 2 slots.
    # Should take at least 2 rounds (~0.1s total), instead of 1 round (~0.05s).
    inputs = [1, 2, 3, 4]
    mapped = slow_task.map(x=inputs).with_constraints(slots=1)

    engine = Engine(
        solver=NativeSolver(), 
        executor=LocalExecutor(), 
        bus=MessageBus(),
        system_resources={"slots": 2} # Allow 2 concurrent tasks
    )

    start_time = time.time()
    results = await engine.run(mapped)
    duration = time.time() - start_time
    
    assert len(results) == 4
    
    # Ideally:
    # T=0: Task 1, 2 start
    # T=0.05: Task 1, 2 finish; Task 3, 4 start
    # T=0.10: Task 3, 4 finish
    # Total ~0.10s.
    # If parallel (unconstrained): ~0.05s.
    
    # We assert it took clearly longer than a single pass
    assert duration >= 0.09
~~~~~

### 下一步建议
实现完策略传播后，下一步我们将处理路线图的 **步骤 2：在图中实现“隐式收集 (`_gather_`)”节点**。这将解决把 `.map()` 的结果传给下游任务时类型不匹配的问题。
