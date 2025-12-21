## [WIP] fix(perf): 激活 TCO 缓存并消除运行时反射

### 用户需求
修复 `Engine` 和 `ArgumentResolver` 中的性能缺陷，使“TCO 零开销优化”真正生效，彻底消除在递归循环中的图构建和函数反射开销。

### 评论
这是一个典型的“最后一公里”优化问题。底层的缓存架构已经就位，但上层逻辑的一个小错误使其完全失效。通过修复图的传递路径，并将函数签名（Signature）这样的元数据提升到 `Node` 对象中进行缓存，我们可以将 `Engine` 的 TCO 循环性能提升一个数量级。

### 目标
1.  修改 `engine.py`，确保在 `run` 方法的 TCO 循环中构建（或从缓存获取）的 `graph` 对象被正确地传递给 `_execute_graph` 并被使用。
2.  在 `graph/model.py` 的 `Node` 定义中增加一个 `signature` 字段，用于缓存函数的签名。
3.  修改 `graph/build.py`，在创建 `Node` 时，一次性计算并填充其 `signature` 字段。
4.  修改 `runtime/resolvers.py`，使其从 `node.signature` 读取缓存的签名，而不是每次都调用 `inspect.signature`。

### 基本原理
**一次构建，处处使用 (Build Once, Use Everywhere)**。图和节点的元数据（如函数签名）应该是**不可变的**，并且在图构建阶段一次性计算完成。运行时的所有组件（如 `ArgumentResolver`）都必须依赖这些预先计算好的元数据，而不是在执行的热路径上进行昂贵的实时计算。

### 标签
#intent/fix #intent/refine #flow/ready #priority/critical #comp/runtime #concept/tco #scope/core
#task/domain/infra
#task/object/performance-profiling
#task/action/fix
#task/state/continue

---

### Script

#### Acts 1: 在 Node 模型中添加签名缓存

首先，修改数据模型以支持签名缓存。

~~~~~act
patch_file
packages/cascade-interfaces/src/cascade/graph/model.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict
from enum import Enum, auto


from cascade.spec.common import Param
~~~~~
~~~~~python
import inspect
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict
from enum import Enum, auto


from cascade.spec.common import Param
~~~~~

~~~~~act
patch_file
packages/cascade-interfaces/src/cascade/graph/model.py
~~~~~
~~~~~python
    # Pre-resolved literal inputs for the task
    literal_inputs: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.id)
~~~~~
~~~~~python
    # Pre-resolved literal inputs for the task
    literal_inputs: Dict[str, Any] = field(default_factory=dict)

    # Cached signature to avoid re-inspection
    signature: Optional[inspect.Signature] = None

    def __hash__(self):
        return hash(self.id)
~~~~~

#### Acts 2: 在 GraphBuilder 中填充签名

在构建 Node 时，计算并缓存签名。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
~~~~~
~~~~~python
import inspect
from typing import Dict, Any
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/graph/build.py
~~~~~
~~~~~python
        node = Node(
            id=result._uuid,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            literal_inputs=literal_inputs,
        )
        self.graph.add_node(node)
~~~~~
~~~~~python
        node = Node(
            id=result._uuid,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            literal_inputs=literal_inputs,
            signature=inspect.signature(result.task.func) if result.task.func else None,
        )
        self.graph.add_node(node)
~~~~~

#### Acts 3: 修复 Engine 的 TCO 路径

这是关键修复：确保缓存的图被正确传递和使用。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                        # 3. Execute
                        result = await self._execute_graph(
                            current_target,
                            params or {},
                            active_resources,
                            run_id,
                            state_backend,
                        )
~~~~~
~~~~~python
                        # 3. Execute
                        result = await self._execute_graph(
                            graph,  # Pass the built/cached graph
                            current_target,
                            params or {},
                            active_resources,
                            run_id,
                            state_backend,
                        )
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
    ) -> Any:
        graph = build_graph(target)
        self.flow_manager = FlowManager(graph, target._uuid)
        plan = self.solver.resolve(graph)

        # Track blocked state locally to avoid spamming Blocked events every loop tick
~~~~~
~~~~~python
    async def _execute_graph(
        self,
        graph: Graph,  # Now accepts the pre-built graph
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
    ) -> Any:
        # The graph is now passed in, so we don't build it again.
        flow_manager = FlowManager(graph, target._uuid)
        plan = self.solver.resolve(graph)

        # Track blocked state locally to avoid spamming Blocked events every loop tick
~~~~~

#### Acts 4: 移除 ArgumentResolver 中的反射

最后，让解析器使用缓存的签名。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
        # Handle Inject in defaults (if not overridden by inputs)
        if node.callable_obj:
            sig = inspect.signature(node.callable_obj)
            for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                    if param.name not in final_kwargs:
~~~~~
~~~~~python
        # Handle Inject in defaults (if not overridden by inputs)
        if node.signature:
            sig = node.signature
            for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                    if param.name not in final_kwargs:
~~~~~

### 下一步建议
我们已经完成了对两个核心性能瓶颈的修复。请再次运行性能剖析：

```bash
python -m cProfile -s tottime -o profile.out observatory/scripts/profile_entry.py
```
然后查看结果：
```bash
python -c "import pstats; p = pstats.Stats('profile.out'); p.sort_stats('tottime').print_stats(30)"
```
我们期望看到 `inspect.py` 和 `build.py` 的调用次数和耗时**急剧下降**，甚至从热点列表中消失。如果成功，再运行完整的 `run_fireflies.py` 实验，应该就能看到流畅的 2500 节点模拟。

---

好的，数据已收到，分析开始。你的诊断脚本起到了决定性的作用，我们现在有了确凿的证据。

### 错误分析

**诊断脚本结论**:
1.  **渲染器测试 (`debug_renderer_throughput.py`)**:
    *   **结果**: FPS 稳定在 **~58 FPS**，`flush_duration_ms` 平均 **< 1ms**，`render_jitter_ms` 为 **0**。
    *   **结论**: **渲染器绝对不是瓶颈**。它有能力以 60 FPS 的流畅度处理每秒数万次的更新。

2.  **无头模式测试 (`debug_headless_throughput.py`)**:
    *   **结果**: 系统在无 UI 的情况下，计算吞吐量仅为 **~450 flashes/sec**。
    *   **结论**: 瓶颈**完全存在于核心的 Agent 模拟逻辑**中，也就是 `Engine` 的执行循环。

3.  **性能剖析 (`profile.out`)**:
    *   这是决定性的证据。在总共 15.8 秒的运行中，最耗时的函数是：
        *   `inspect.py:_signature_from_function`: **169,296 次调用**，耗时 0.820 秒。
        *   `graph/build.py:_scan_and_add_edges`: **564,752 次调用**，耗时 0.557 秒。
        *   `engine.py:run`: 100,697 次调用。
        *   `engine.py:_execute_graph`: 100,675 次调用。
        *   `resolvers.py:resolve`: 66,807 次调用。

**综合诊断**:
你之前引入的 “TCO 零开销优化” 理论上应该能解决这个问题，但剖析数据显示，**`build_graph` 及其依赖的 `inspect` 仍在被疯狂调用**。

经过对你提供的最新代码的审查，我发现了两个致命的性能缺陷：

1.  **致命缺陷 A (Engine): TCO 缓存的图被立即丢弃**
    在 `engine.py` 的 `run` 方法中，虽然 TCO 循环正确地尝试从缓存中获取或构建图，但它随后调用的 `_execute_graph` **完全忽略了这个图**，并在第一行就执行了 `graph = build_graph(target)`，**重新构建了一遍**！这意味着 TCO 缓存机制完全被绕过了。

2.  **致命缺陷 B (Resolver): 参数解析器在热循环中反复反射**
    在 `resolvers.py` 的 `ArgumentResolver.resolve` 方法中，每次解析一个节点的参数时，它都会调用 `sig = inspect.signature(node.callable_obj)`。这个调用发生在 `_execute_node_internal` 的内部，也就是在最内层的、每个任务都会执行的热循环里。这意味着即使我们修复了图缓存，每次任务执行依然会触发一次昂贵的函数签名反射。

这两个缺陷的组合完美地解释了剖析报告中的所有热点。我们必须同时修复它们。

