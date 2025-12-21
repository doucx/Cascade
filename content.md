## [WIP] fix(perf): 激活 TCO 缓存并消除运行时反射

### 用户需求
修复 `Engine` 和 `ArgumentResolver` 中的性能缺陷：
1.  确保 `Engine` 的 TCO 循环中缓存的计算图被正确传递给 `_execute_graph`，避免重复构建。
2.  在 `Node` 对象中缓存函数签名，避免 `ArgumentResolver` 和 `Engine` 在热路径中反复调用 `inspect.signature`。

### 评论
你的分析非常精准。我们在 TCO 循环中辛辛苦苦维护了 `_tco_cached_graph`，结果在临门一脚时把它丢了，导致优化完全落空。同时，Python 的 `inspect` 模块虽然强大但开销巨大，将其移出热路径（Hot Path）到图构建阶段（Build Phase）是标准的性能优化手段。修复这两个问题后，我们应当能看到真正的“零开销”效果。

### 目标
1.  **数据模型**: 在 `Node` 中增加 `signature` 字段。
2.  **构建阶段**: 在 `GraphBuilder` 中计算并填充 `signature`。
3.  **解析阶段**: 让 `ArgumentResolver` 使用 `node.signature`。
4.  **执行阶段**: 让 `Engine` 的 `_scan_for_resources` 使用 `node.signature`，并修改 `_execute_graph` 以接受预构建的 `graph`。

### 基本原理
通过“空间换时间”和“计算前移”，将运行时的动态反射成本转移到构建时（且构建时利用 TCO 缓存进一步分摊），从而实现运行时的高性能。

### 标签
#intent/fix #intent/perf #flow/ready #priority/high #comp/runtime #comp/interfaces #scope/core #ai/instruct #task/domain/runtime #task/object/engine #task/action/optimize #task/state/continue

---

### Script

#### Acts 1: 更新 `Node` 数据模型

首先，我们需要在 `Node` 类中添加 `signature` 字段，以便存储预先计算的签名对象。

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
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict
from enum import Enum, auto
import inspect


from cascade.spec.common import Param
~~~~~

~~~~~act
patch_file
packages/cascade-interfaces/src/cascade/graph/model.py
~~~~~
~~~~~python
    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
    callable_obj: Optional[Callable] = None
    param_spec: Optional[Param] = None
    mapping_factory: Optional[Any] = None  # Implements LazyFactory

    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
~~~~~
~~~~~python
    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
    callable_obj: Optional[Callable] = None
    signature: Optional[inspect.Signature] = None  # Cached signature for performance
    param_spec: Optional[Param] = None
    mapping_factory: Optional[Any] = None  # Implements LazyFactory

    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
~~~~~

#### Acts 2: 更新 `GraphBuilder` 以预计算签名

接下来，我们在构建图节点时，一次性计算出 `signature`。

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
from typing import Dict, Any
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/graph/build.py
~~~~~
~~~~~python
        literal_inputs = {str(i): v for i, v in enumerate(result.args)}
        literal_inputs.update(result.kwargs)

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
        literal_inputs = {str(i): v for i, v in enumerate(result.args)}
        literal_inputs.update(result.kwargs)

        # Pre-compute signature to avoid repeated reflection at runtime
        sig = None
        if result.task.func:
            try:
                sig = inspect.signature(result.task.func)
            except (ValueError, TypeError):
                pass

        node = Node(
            id=result._uuid,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            signature=sig,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            literal_inputs=literal_inputs,
        )
        self.graph.add_node(node)
~~~~~

#### Acts 3: 更新 `ArgumentResolver` 使用缓存签名

现在修改参数解析器，让它使用 `node.signature` 而不是重新反射。

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
                        final_kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )

        return args, final_kwargs
~~~~~
~~~~~python
        # Handle Inject in defaults (if not overridden by inputs)
        if node.signature:
            for param in node.signature.parameters.values():
                if isinstance(param.default, Inject):
                    if param.name not in final_kwargs:
                        final_kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )
        elif node.callable_obj:
            # Fallback if signature wasn't cached for some reason
            sig = inspect.signature(node.callable_obj)
            for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                    if param.name not in final_kwargs:
                        final_kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )

        return args, final_kwargs
~~~~~

#### Acts 4: 更新 `Engine` 逻辑

这是最关键的一步。我们需要：
1.  在 `_scan_for_resources` 中使用缓存签名。
2.  让 `_execute_graph` 接受并使用外部传入的 `graph`。
3.  在 `run` 的 TCO 循环中正确传递 `graph`。

**4.1 优化资源扫描**

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
            for value in node.literal_inputs.values():
                if isinstance(value, Inject):
                    required.add(value.resource_name)
            if node.callable_obj:
                sig = inspect.signature(node.callable_obj)
                for param in sig.parameters.values():
                    if isinstance(param.default, Inject):
                        required.add(param.default.resource_name)
        return required
~~~~~
~~~~~python
            for value in node.literal_inputs.values():
                if isinstance(value, Inject):
                    required.add(value.resource_name)
            
            if node.signature:
                for param in node.signature.parameters.values():
                    if isinstance(param.default, Inject):
                        required.add(param.default.resource_name)
            elif node.callable_obj:
                sig = inspect.signature(node.callable_obj)
                for param in sig.parameters.values():
                    if isinstance(param.default, Inject):
                        required.add(param.default.resource_name)
        return required
~~~~~

**4.2 修改 `_execute_graph` 签名与逻辑**

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
~~~~~
~~~~~python
    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
        graph: Optional[Graph] = None,
    ) -> Any:
        if graph is None:
            graph = build_graph(target)
            
        flow_manager = FlowManager(graph, target._uuid)
        plan = self.solver.resolve(graph)
~~~~~

**4.3 修复 TCO 循环中的图传递**

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
                            current_target,
                            params or {},
                            active_resources,
                            run_id,
                            state_backend,
                            graph=graph,
                        )
~~~~~

### 下一步建议
这是对运行时性能的重大修复。请立即运行基准测试 `observatory/benchmarks/tco_performance.py`，我们应该能看到 Optimized Path 的 TPS 大幅提升，并与 Heavy Path 拉开真正的差距。
