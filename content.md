我们已经完成了编译器强化 (`IRGenerator`) 和运行时适配器 (`IRToRuntimeAdapter`) 的准备工作。现在的关键步骤是修改核心执行策略，将流量从旧的 `cascade-graph` 构建器切换到新的编译器链路。

我将生成一个计划来执行这一“心脏移植手术”。

## [WIP] refactor(runtime): 将执行策略迁移至编译器前端

### 用户需求
实施 "Operation Graph-Strangler" 的第三阶段（流量切换）。修改 `GraphExecutionStrategy`，使其不再依赖 `cascade.graph.build.build_graph`，而是使用 `IRGenerator` 生成 IR，再通过 `IRToRuntimeAdapter` 转换为运行时图模型。

### 评论
这是一个高风险、高回报的核心重构。它验证了我们之前的编译器工作是否真的能够替代旧的构建逻辑。为了降低风险，我们在代码中保留了明确的注释，指明这是 Cascade 3.1 的新链路。

### 目标
1.  修改 `packages/cascade-runtime/src/cascade/runtime/legacy/strategies/graph.py`。
2.  移除对 `cascade.graph.build` 的引用。
3.  引入 `cascade.compiler.frontend.generator.IRGenerator` 和 `cascade.runtime.graph.adapter.IRToRuntimeAdapter`。
4.  更新主执行循环和子图运行器 (`sub_graph_runner`) 以使用新链路。

### 基本原理
通过将图构建逻辑收敛到 `cascade-compiler`，我们消除了逻辑重复，确立了单向数据流（DSL -> IR -> Runtime），并为未来更高级的静态分析和优化打下了基础。Runtime 不再需要知道如何“解析” DSL，它只需要知道如何执行由 Compiler 生成的标准模型。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #scope/core #ai/instruct #task/domain/core #task/object/graph-execution-strategy #task/action/migrate-to-compiler #task/state/begin

---

### Script

#### Acts 1: 更新 GraphExecutionStrategy 依赖与逻辑

我们将替换导入语句，并更新 `execute` 方法和内部的 `sub_graph_runner` 函数，使其通过 Compiler Frontend + Adapter 链路来构建执行图。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/graph.py
~~~~~
~~~~~python.old
from cascade.graph.model import Graph, Node, EdgeType
from cascade.graph.build import build_graph
from cascade.graph.registry import NodeRegistry
from cascade.reflection import BlueprintHasher
~~~~~
~~~~~python.new
from cascade.graph.model import Graph, Node, EdgeType
from cascade.compiler.frontend.generator import IRGenerator
from cascade.runtime.graph.adapter import IRToRuntimeAdapter
from cascade.graph.registry import NodeRegistry
from cascade.reflection import BlueprintHasher
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/graph.py
~~~~~
~~~~~python.old
                if current_target._uuid in local_context_cache:
                    (
                        graph,
                        instance_map,
                        plan,
                        executable_registry,
                    ) = local_context_cache[current_target._uuid]
                else:
                    graph, instance_map, executable_registry = build_graph(
                        current_target, registry=self._node_registry
                    )

                    if current_target._uuid not in instance_map:
                        raise RuntimeError(
~~~~~
~~~~~python.new
                if current_target._uuid in local_context_cache:
                    (
                        graph,
                        instance_map,
                        plan,
                        executable_registry,
                    ) = local_context_cache[current_target._uuid]
                else:
                    # Cascade 3.1: Use Compiler Frontend + Adapter instead of direct GraphBuilder
                    gen_result = IRGenerator().generate(current_target)
                    adapter = IRToRuntimeAdapter(registry=self._node_registry)
                    graph, instance_map, executable_registry = adapter.adapt(gen_result)

                    if current_target._uuid not in instance_map:
                        raise RuntimeError(
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/graph.py
~~~~~
~~~~~python.old
                if executable_this_pass:

                    async def sub_graph_runner(target, sub_params, parent_state):
                        (
                            sub_graph,
                            sub_instance_map,
                            sub_executable_registry,
                        ) = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        result_obj = await self._execute_graph(
~~~~~
~~~~~python.new
                if executable_this_pass:

                    async def sub_graph_runner(target, sub_params, parent_state):
                        # Cascade 3.1: Use Compiler Frontend + Adapter
                        gen_result = IRGenerator().generate(target)
                        adapter = IRToRuntimeAdapter()
                        (
                            sub_graph,
                            sub_instance_map,
                            sub_executable_registry,
                        ) = adapter.adapt(gen_result)

                        sub_plan = self.solver.resolve(sub_graph)
                        result_obj = await self._execute_graph(
~~~~~

### 下一步建议

代码修改完成后，你需要执行全量测试来验证此次“心脏移植”是否成功。
请运行：
`uv run pytest packages/cascade-runtime/tests`

如果测试全部通过，我们就可以进入阶段五：将 `cascade-graph` 中的剩余资产（对象模型）搬迁到 `cascade-runtime`，并最终删除旧包。
