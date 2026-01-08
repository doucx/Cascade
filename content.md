发现 `DependencyMissingError` 根源：`IRGenerator` 忽略了 `ResourceConstraint` 中的 `LazyResult` 依赖遍历，导致上游任务未被生成；且 `IRToRuntimeAdapter` 未建立 `CONSTRAINT` 类型边，导致调度器无法保证执行顺序。

## [WIP] fix: 修复动态资源约束的依赖生成与边构建逻辑

### 错误分析

**`DependencyMissingError` 在 `test_dynamic_resource_constraint` 中触发。**

1.  **Compiler 侧 (IRGenerator)**:
    *   **现象**: `calculate_cpu_needs` 任务未被生成。
    *   **原因**: `IRGenerator._visit_lazy_result` 和 `_visit_mapped_result` 方法仅遍历了 `args`, `kwargs`, `dependencies` 和 `condition`，**完全忽略了 `_constraints` 属性**。
    *   **后果**: 当一个 `LazyResult` 仅作为约束条件出现时（如 `.with_constraints(cpu=needs)`），它永远不会被 `_visit` 调用，因此对应的 `NodeIR` 永远不会被创建。Runtime 的 `InstanceMap` 中缺失该节点，导致 `ConstraintResolver` 抛出 `DependencyMissingError`。
    
2.  **Runtime 侧 (IRToRuntimeAdapter)**:
    *   **现象**: 即使节点存在（假设被修复），调度顺序也可能错误。
    *   **原因**: `IRToRuntimeAdapter._create_edges` 未处理 `NodeIR.constraints`。
    *   **后果**: 动态约束暗示了数据依赖。如果没有 `EdgeType.CONSTRAINT` 边，`NativeSolver`（拓扑排序）无法感知依赖关系，可能导致下游任务在上游任务之前调度（或并行调度），从而导致运行时获取不到约束值。

### 用户需求

修复动态资源约束（Dynamic Resource Constraints）功能，使其能正确声明、生成并执行依赖任务。

### 评论

这是一个典型的“隐式依赖”问题。在 DSL 中，`.with_constraints(cpu=x)` 看起来像配置，但在物理层，它是一个硬性的数据依赖边。Compiler 和 Runtime 必须显式地将其建模为图结构的一部分。

### 目标

1.  修改 `IRGenerator` 以递归遍历 `_constraints` 中的 `LazyResult`。
2.  修改 `IRToRuntimeAdapter` 以解析 `NodeIR.constraints` 并创建 `EdgeType.CONSTRAINT` 边。
3.  通过 `test_dynamic_resource_constraint` 测试。

### 基本原理

*   **全图遍历**: 任何持有 `LazyResult` 的字段（包括约束）都是图遍历的入口。
*   **显式拓扑**: 所有的执行顺序依赖（包括为了计算资源需求而产生的依赖）都必须在 Runtime Graph 中以 Edge 形式存在。

### 标签

#intent/fix #flow/ready #priority/high #comp/compiler #comp/runtime #concept/dependency #scope/core #ai/instruct #task/domain/scheduler #task/object/constraints #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 IRGenerator 的遍历逻辑

我们需要在 `_collect_deps_map`（用于哈希计算上下文）和 `_visit_lazy_result`/`_visit_mapped_result`（用于节点生成）中增加对 `_constraints` 的遍历。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
        if lr._condition:
            collect_deps(lr._condition)
        for dep in lr._dependencies:
            collect_deps(dep)

        # Collect Jump targets
~~~~~
~~~~~python.new
        if lr._condition:
            collect_deps(lr._condition)
        if lr._constraints:
            for val in lr._constraints.requirements.values():
                collect_deps(val)
        for dep in lr._dependencies:
            collect_deps(dep)

        # Collect Jump targets
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
        condition_id = None
        if lr._condition:
            condition_id = self._visit(lr._condition)

        dependency_ids = []
        for dep in lr._dependencies:
            dependency_ids.append(self._visit(dep))

        flow_control = None
~~~~~
~~~~~python.new
        condition_id = None
        if lr._condition:
            condition_id = self._visit(lr._condition)
        
        # Visit dynamic constraints to ensure they are generated
        if lr._constraints:
            for val in lr._constraints.requirements.values():
                self._visit(val)

        dependency_ids = []
        for dep in lr._dependencies:
            dependency_ids.append(self._visit(dep))

        flow_control = None
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
        condition_id = None
        if lr._condition:
            condition_id = self._visit(lr._condition)

        dependency_ids = []
        for dep in lr._dependencies:
            dependency_ids.append(self._visit(dep))

        task_def = self.analyzer.analyze(lr.factory)
~~~~~
~~~~~python.new
        condition_id = None
        if lr._condition:
            condition_id = self._visit(lr._condition)

        if lr._constraints:
            for val in lr._constraints.requirements.values():
                self._visit(val)

        dependency_ids = []
        for dep in lr._dependencies:
            dependency_ids.append(self._visit(dep))

        task_def = self.analyzer.analyze(lr.factory)
~~~~~

#### Acts 2: 修复 IRToRuntimeAdapter 的边构建逻辑

我们需要在 `_create_edges` 中增加对 `node_ir.constraints` 的处理，为动态约束创建类型为 `CONSTRAINT` 的边。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/graph/adapter.py
~~~~~
~~~~~python.old
        # 4. Jump / Flow Control
        if node_ir.flow_control:
            self._reconstruct_jump_edges(node_ir.flow_control, target_node)

    def _reconstruct_router_edges(
~~~~~
~~~~~python.new
        # 4. Jump / Flow Control
        if node_ir.flow_control:
            self._reconstruct_jump_edges(node_ir.flow_control, target_node)

        # 5. Constraint Edges
        if node_ir.constraints:
            from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult

            for key, val in node_ir.constraints.items():
                if isinstance(val, (LazyResult, MappedLazyResult)):
                    # Note: val is the LazyResult object because IRGenerator copied the dict.
                    # We need to find its logical ID or use UUID to lookup in maps.
                    # IRGenerator output guarantees nodes are generated.
                    # Since Adapter has logic to build maps, we use logical_map for UUIDs.
                    if val._uuid in self.logical_map:
                        source_node = self.logical_map[val._uuid]
                        self.graph.add_edge(
                            Edge(
                                source=source_node,
                                target=target_node,
                                arg_name=key,
                                edge_type=EdgeType.CONSTRAINT,
                            )
                        )

    def _reconstruct_router_edges(
~~~~~

### 下一步建议

再次运行 E2E 集成测试：
`pytest tests/e2e/integration/test_resource_scheduling.py`
