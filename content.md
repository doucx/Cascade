简要回答
好的，我将修复 `Engine` 中处理 `Param` 类型 Selector 的 ID 映射问题，并修正测试用例中的错误用法。

## [WIP] fix(runtime): 修复 Router 剪枝逻辑对 Param 的支持及测试错误

### 错误分析
1.  **Param ID 映射错误**: `Engine` 在构建 `selector_map` 时，盲目访问 `selector._uuid`。但当 Selector 是 `Param` 类型时，它没有 `_uuid`，其节点 ID 应该是 `param.name`。这导致了 `AttributeError`。
2.  **测试用例构建错误**: `test_router_prunes_cascade` 尝试直接运行 `Router` 对象 (`engine.run(router)`)。`Engine` 只能运行 `LazyResult` 或 `Param`，不能直接运行连接结构。

### 用户需求
无新需求，修复上一轮迭代引入的 Bug。

### 评论
必须确保 `Engine` 能够稳健地处理不同类型的节点标识符，这是动态图执行的基础。

### 目标
1.  在 `Engine` 中正确处理 `Param` 类型的 Selector ID。
2.  修正 `test_router_prunes_cascade`，将 `Router` 包装在一个 Identity 任务中。
3.  （尝试解决 Test 1 失败）在 `GraphBuilder` 中再次确认控制依赖的添加逻辑，确保 `Selector` 确实在 `Route` 之前执行。

### 基本原理
通过 `isinstance(selector, Param)` 检查来区分 ID 获取方式。
通过包装任务使图构建合法化。

### 标签
#intent/fix #flow/ready #priority/high
#comp/runtime #comp/tests
#scope/core
#task/domain/core #task/object/router #task/action/bug-fix
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 修复 `Engine` 中的 Selector ID 获取逻辑

我们需要导入 `Param` 并根据类型获取 ID。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
~~~~~
~~~~~python
from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.spec.common import Param
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
        # Map: selector_node_id -> List[Router]
        selector_map = defaultdict(list)
        for edge in graph.edges:
            if edge.router:
                selector_map[edge.router.selector._uuid].append(edge.router)

        # Inject params first (usually params are in the first stage or handled implicitly)
~~~~~
~~~~~python
        # Map: selector_node_id -> List[Router]
        selector_map = defaultdict(list)
        for edge in graph.edges:
            if edge.router:
                selector = edge.router.selector
                selector_id = selector.name if isinstance(selector, Param) else selector._uuid
                selector_map[selector_id].append(edge.router)

        # Inject params first (usually params are in the first stage or handled implicitly)
~~~~~

#### Acts 2: 修正测试用例 `test_router_pruning.py`

将 `engine.run(router)` 替换为 `engine.run(identity(router))`。

~~~~~act
patch_file
tests/integration/test_router_pruning.py
~~~~~
~~~~~python
    router = cs.Router(
        selector=selector(),
        routes={
            "a": branch_a(),
            "b": chain_b
        }
    )

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    await engine.run(router)

    skipped = spy.events_of_type(TaskSkipped)
~~~~~
~~~~~python
    router = cs.Router(
        selector=selector(),
        routes={
            "a": branch_a(),
            "b": chain_b
        }
    )

    @cs.task
    def identity(x):
        return x

    target = identity(router)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    await engine.run(target)

    skipped = spy.events_of_type(TaskSkipped)
~~~~~

### 下一步建议
如果这次修复后 Test 1 依然失败，那么问题可能出在 `NativeSolver` 或 `Engine` 的 Stage 处理逻辑上，可能需要深入 `NativeSolver` 检查它是否忽略了某种类型的边。
