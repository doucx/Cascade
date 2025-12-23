遵循 `d2-skill-quipu-decide-write-patch` 流程：

简要回答：
找到问题了。

1.  **根本原因 (The Smoking Gun)**: 在 `GraphBuilder.build` 中，我错误地将 `self.graph.add_node(node)` 放在了 `if created_new:` 块内。这意味着，如果一个节点是从 `NodeRegistry` 中复用的（例如 TCO 循环中的静态依赖链），它就不会被添加到当前正在构建的 `Graph` 对象中。结果就是，`Solver` 面对的是一个只有边没有点（或只有部分点）的图，导致依赖项（`noop` 节点）没有被包含在执行计划中，最终在执行消费者节点时抛出 `DependencyMissingError`。
2.  **测试失败**: `test_tco_cache.py` 失败是因为遗漏了 `@pytest.mark.asyncio` 装饰器。

修复方案：
1.  修改 `packages/cascade-graph/src/cascade/graph/build.py`，确保无论节点是否是新创建的，都将其添加到当前的 `graph` 中。
2.  修改 `tests/engine/runtime/test_tco_cache.py`，添加缺失的装饰器。

## [WIP] fix(core): 修复 GraphBuilder 在节点复用时丢失节点的 Bug

### 错误分析
-   **现象**: TCO 性能测试中的 `heavy_complex_countdown` 失败，报 `DependencyMissingError`。
-   **根因**: `GraphBuilder` 仅将 `NodeRegistry` 中**新创建**的节点添加到当前 `Graph` 实例中。复用的节点（如递归中的静态依赖链）被遗漏，导致 `ExecutionPlan` 不完整，依赖项未执行。
-   **测试问题**: 新增的回归测试因缺少 asyncio 标记而未能运行。

### 用户需求
修复核心 Bug 以恢复 TCO 循环中的依赖项执行，并修复回归测试的配置。

### 评论
这是一个经典的“缓存失效”类 Bug。我们在引入“结构复用”时，混淆了“全局唯一性（Registry）”和“当前上下文完整性（Graph）”的概念。对于每个新的 `Graph` 构建过程，无论节点是否是全局“旧”的，对于这个 `Graph` 来说它都是“必需”的。

### 目标
1.  将 `self.graph.add_node(node)` 移出 `if created_new:` 块。
2.  为 `test_tco_cache.py` 添加 `@pytest.mark.asyncio`。

### 基本原理
确保 `GraphBuilder` 构建的 `Graph` 对象包含所有遍历到的节点，从而保证 `Solver` 能生成完整的执行计划。

### 标签
#intent/fix #flow/ready #priority/critical #comp/graph #comp/tests #scope/core #ai/instruct #task/domain/architecture #task/object/graph-builder #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 修复 `GraphBuilder` 逻辑

强制将所有访问到的节点添加到当前图中。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        node, created_new = self.registry.get_or_create(structural_hash, node_factory)
        self._visited_instances[result._uuid] = node

        if created_new:
            self.graph.add_node(node)
            if result.task.func:
                if not getattr(result.task, "_tco_analysis_done", False):
~~~~~
~~~~~python
        node, created_new = self.registry.get_or_create(structural_hash, node_factory)
        self._visited_instances[result._uuid] = node

        # Always add the node to the current graph, even if it was reused from the registry.
        self.graph.add_node(node)

        if created_new:
            if result.task.func:
                if not getattr(result.task, "_tco_analysis_done", False):
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        node, created_new = self.registry.get_or_create(structural_hash, node_factory)
        self._visited_instances[result._uuid] = node

        if created_new:
            self.graph.add_node(node)

        # 4. Add data edges
        self._scan_and_add_edges(node, result.mapping_kwargs)
~~~~~
~~~~~python
        node, created_new = self.registry.get_or_create(structural_hash, node_factory)
        self._visited_instances[result._uuid] = node

        # Always add the node to the current graph
        self.graph.add_node(node)

        # 4. Add data edges
        self._scan_and_add_edges(node, result.mapping_kwargs)
~~~~~

#### Acts 2: 修复测试用例装饰器

~~~~~act
patch_file
tests/engine/runtime/test_tco_cache.py
~~~~~
~~~~~python
import asyncio
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


@cs.task
def noop():
    """A simple dependency task."""
    return "ok"
~~~~~
~~~~~python
import asyncio
import pytest
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


@cs.task
def noop():
    """A simple dependency task."""
    return "ok"
~~~~~
~~~~~act
patch_file
tests/engine/runtime/test_tco_cache.py
~~~~~
~~~~~python
    return recursive_with_deps(n - 1, _dep=noop())


async def test_jit_cache_handles_tco_with_dependencies():
    """
    Validates that the GraphExecutionStrategy's JIT cache correctly handles
    TCO loops where each iteration has internal dependencies.
~~~~~
~~~~~python
    return recursive_with_deps(n - 1, _dep=noop())


@pytest.mark.asyncio
async def test_jit_cache_handles_tco_with_dependencies():
    """
    Validates that the GraphExecutionStrategy's JIT cache correctly handles
    TCO loops where each iteration has internal dependencies.
~~~~~

### 下一步建议
这次修复应该是决定性的。
1.  运行 `pytest tests/engine/runtime/test_tco_cache.py` 确认回归测试通过。
2.  运行完整的 `pytest` 确保没有其他副作用。
3.  运行 `python observatory/benchmarks/tco_performance.py`。这一次，我们应该能看到所有基准测试都通过，并且 `heavy_complex_countdown` 的性能应该有所提升（尽管由于我们确认了它是 cache miss，提升幅度取决于 `NodeRegistry` 减少了多少对象分配开销）。
4.  根据基准测试结果，评估是否需要进一步优化（例如，是否真的需要解决 root node cache miss 的问题，或者目前的 Node 复用已经足够好）。
