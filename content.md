简要回答：
已完成代码审查。发现 `cascade-graph` 和 `cascade-engine` 中存在违反 `d3-axiom-hash-naming` 的短命名变量（如 `structural_hash` 和 `blueprint_hash`）。我将生成一个修复计划，将这些变量重命名为符合 `[Source]_[Object]_[State]_hash` 规范的长命名形式。

## [WIP] refactor(core): 强制执行哈希长命名公理，消除概念性债务

### 用户需求
对代码库进行审查，并强制执行新引入的 `d3-axiom-hash-naming` 公理。将模糊的短命名哈希变量重命名为自文档化的长命名，以消除“概念性债务”并防止未来的逻辑错误。

### 评论
这是一个关键的防御性重构。虽然当前代码逻辑是正确的，但 `structural_hash` 和 `blueprint_hash` 这样的命名在未来引入基线对比（Baseline Comparison）或增量编译时会成为巨大的歧义源。通过现在执行此规范，我们为系统的长期可维护性奠定了基础。

### 目标
1.  在 `GraphBuilder` (`build.py`) 中，将局部变量 `structural_hash` 重命名为 `current_code_structure_hash`。
2.  在 `GraphExecutionStrategy` (`graph.py`) 中，将局部变量 `blueprint_hash` 重命名为 `current_graph_structure_hash`。

### 基本原理
根据 `d3-axiom-hash-naming`，哈希变量必须遵循 `[Source]_[Object]_[State]_hash` 的四段式结构。
-   `structural_hash` -> `current_code_structure_hash`: 来源于代码(LazyResult)，对象是结构，状态是当前。
-   `blueprint_hash` -> `current_graph_structure_hash`: 来源于图对象(Graph)，对象是结构，状态是当前。

### 标签
#intent/refine #flow/ready #priority/high #comp/core #comp/engine #concept/state #scope/dx #ai/instruct #task/domain/core #task/object/hash-naming #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重构 GraphBuilder 中的哈希命名

在 `cascade-graph` 包中，`GraphBuilder` 使用 `structural_hash` 来进行 Hash-Consing。我们将其重命名为 `current_code_structure_hash` 以明确其语义：这是从当前代码（LazyResult）实时计算出的结构哈希。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
        # 2. Compute structural hash using HashingService
        structural_hash = self.hashing_service.compute_structural_hash(
            result, dep_nodes
        )

        # 3. Hash-consing: Query registry FIRST before doing more work
        node = self.registry.get(structural_hash)

        if not node:
            # Extract bindings
~~~~~
~~~~~python.new
        # 2. Compute structural hash using HashingService
        current_code_structure_hash = self.hashing_service.compute_structural_hash(
            result, dep_nodes
        )

        # 3. Hash-consing: Query registry FIRST before doing more work
        node = self.registry.get(current_code_structure_hash)

        if not node:
            # Extract bindings
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
                has_complex_inputs=has_complex,
            )
            self.registry._registry[structural_hash] = node

        self._visited_instances[result._uuid] = node
~~~~~
~~~~~python.new
                has_complex_inputs=has_complex,
            )
            self.registry._registry[current_code_structure_hash] = node

        self._visited_instances[result._uuid] = node
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
        # 2. Compute structural hash using HashingService
        structural_hash = self.hashing_service.compute_structural_hash(
            result, dep_nodes
        )

        # 3. Hash-consing
        def node_factory():
~~~~~
~~~~~python.new
        # 2. Compute structural hash using HashingService
        current_code_structure_hash = self.hashing_service.compute_structural_hash(
            result, dep_nodes
        )

        # 3. Hash-consing
        def node_factory():
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
                input_bindings=input_bindings,
            )

        node, created_new = self.registry.get_or_create(structural_hash, node_factory)
        self._visited_instances[result._uuid] = node

        # Always add the node to the current graph
~~~~~
~~~~~python.new
                input_bindings=input_bindings,
            )

        node, created_new = self.registry.get_or_create(
            current_code_structure_hash, node_factory
        )
        self._visited_instances[result._uuid] = node

        # Always add the node to the current graph
~~~~~

#### Acts 2: 重构 GraphExecutionStrategy 中的哈希命名

在 `cascade-engine` 包中，`GraphExecutionStrategy` 使用 `blueprint_hash` 作为执行计划缓存的键。我们将其重命名为 `current_graph_structure_hash`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python.old
                    # 2.2 Resolve Plan (with caching based on blueprint hash)
                    blueprint_hash = self.blueprint_hasher.compute_hash(graph)
                    if blueprint_hash in self._template_plan_cache:
                        indexed_plan = self._template_plan_cache[blueprint_hash]
                        plan = self._rehydrate_plan(graph, indexed_plan)
                    else:
                        plan = self.solver.resolve(graph)
                        indexed_plan = self._index_plan(graph, plan)
                        self._template_plan_cache[blueprint_hash] = indexed_plan

                    # Update local cache
~~~~~
~~~~~python.new
                    # 2.2 Resolve Plan (with caching based on blueprint hash)
                    current_graph_structure_hash = self.blueprint_hasher.compute_hash(graph)
                    if current_graph_structure_hash in self._template_plan_cache:
                        indexed_plan = self._template_plan_cache[
                            current_graph_structure_hash
                        ]
                        plan = self._rehydrate_plan(graph, indexed_plan)
                    else:
                        plan = self.solver.resolve(graph)
                        indexed_plan = self._index_plan(graph, plan)
                        self._template_plan_cache[
                            current_graph_structure_hash
                        ] = indexed_plan

                    # Update local cache
~~~~~

### 下一步建议
当前重构仅解决了局部变量的命名问题。为了完全符合公理，我们未来应该考虑将 `Node.structural_id` 字段也进行重命名（例如改为 `code_structure_hash`），但这涉及 API 变更，应在更大的版本更新中进行。目前的修改已经消除了最危险的逻辑歧义。
