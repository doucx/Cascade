糟糕，TCO 快速通道的实现引入了一个回归错误。测试失败表明，在递归的最后一步，引擎无法找到最终结果，这通常指向状态管理或对象标识符在不同迭代之间出现了不一致。

你的分析是正确的：这是一个微妙的状态同步问题。

 错误分析

1.  **问题的根源**: 错误 `KeyError: "Target task '...' did not produce a result."` 发生在 `_execute_graph` 的末尾。这说明当执行计划（`plan`）完成后，引擎去查找目标节点的结果时，发现结果没有被存放在预期的节点 ID 下。

2.  **因果链**:
    *   **TCO 快速通道**：当我们进入快速通道时，我们会复用之前缓存的 `graph` 和 `plan`。这些对象包含了一组“规范化”的 `Node` 实例（例如，`node_A`）。
    *   **数据提取**: 为了获取新一轮迭代的参数（比如 `n-1`），我们依然调用了 `build_graph(current_target)`。由于 `ShallowHasher` 会将字面量参数纳入哈希计算，这次调用会生成一个**全新的** `Node` 实例（例如，`node_B`）和一张全新的 `instance_map`，这张图谱将 `current_target._uuid` 映射到 `node_B`。
    *   **不匹配**: 我们随后调用 `_execute_graph`，传入了**旧的计划**（包含 `node_A`）和**新的 `instance_map`**（将目标 `_uuid` 映射到 `node_B`）。
    *   **执行与存储**: 执行器按照旧计划运行，处理 `node_A`，并将最终结果存入 `state_backend[node_A.id]`。
    *   **检查失败**: 在 `_execute_graph` 的末尾，它使用新的 `instance_map` 来查找目标节点：`target_node = instance_map[current_target._uuid]`，这会得到 `node_B`。然后它检查 `state_backend.has_result(node_B.id)`，这个检查必然失败，因为结果被存储在了 `node_A.id` 下。

 解决方案

解决方案是在进入快速通道后，强制“校准”`instance_map`，使其将当前 `LazyResult` 实例的 UUID 映射到我们从缓存计划中取出的、正确的、规范化的 `Node` 实例。这样，后续的所有操作（尤其是最终的结果检查）都会使用正确的节点 ID。

我将生成一个计划来应用这个修复。

## [WIP] fix(engine): Correct node identity mismatch in TCO fast path

### 错误分析
TCO（尾调用优化）的快速通道逻辑存在一个缺陷。在快速通道中，我们正确地复用了缓存的 `ExecutionPlan`（其中包含规范化的 `Node` 对象）。然而，为了提取新一轮迭代的参数，我们调用 `build_graph()`，这会生成一张全新的、临时的图和一张新的 `instance_map`。

这导致了 `plan` 中的节点（规范化节点）与 `instance_map` 中的节点（临时节点）不匹配。当 `_execute_graph` 完成执行后，它使用 `instance_map` 来查找目标节点 ID 以获取结果，但由于结果是使用 `plan` 中的规范化节点 ID 存储的，查找必然失败，从而引发 `KeyError`。

### 用户需求
修复 TCO 快速通道中的 `KeyError`，确保深度递归和相互递归的测试用例能够通过。

### 评论
这个 Bug 揭示了在混合使用缓存结构和即时生成的数据时保持标识符一致性的重要性。通过在快速通道中“校准”`instance_map`，我们能以最小的代价弥合这种不一致，同时保留 `build_graph`作为数据提取器的便利性。这个修复对于保证 Cascade 长活 Agent 的稳定性和性能至关重要。

### 目标
1.  在 `GraphExecutionStrategy.execute` 的快速通道逻辑中，定位到 `instance_map` 不匹配的问题。
2.  从缓存的 `plan` 中提取出规范化的目标 `Node` 对象。
3.  用这个规范化的 `Node` 对象覆盖 `instance_map` 中由 `build_graph` 临时生成的映射。
4.  确保所有 TCO 相关的测试恢复并通过。

### 基本原理
我们将采用一个“外科手术式”的修复方法。在快速通道中，我们承认 `build_graph()` 会生成一个临时的、不正确的 `instance_map`。但在调用 `_execute_graph` 之前，我们介入并修正这个 `instance_map`。

我们假设对于一个简单的 TCO 任务，其执行计划 `plan` 的第一个阶段只包含一个节点，这个节点就是我们要执行的规范化目标节点。我们将这个节点提取出来，然后强制更新 `instance_map`，使当前 `LazyResult` 的 `_uuid` 指向这个正确的、规范化的节点。这样，当 `_execute_graph` 内部进行最终结果查找时，它将使用正确的节点 ID，从而成功找到结果。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/instruct #task/domain/runtime #task/object/tco-optimization #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `strategies.py` 中的节点标识符不匹配问题

我们将修改 `GraphExecutionStrategy.execute` 方法，在 TCO 快速通道中添加校准 `instance_map` 的逻辑。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
                if is_fast_path:
                    # FAST PATH: Reuse plan, rebuild graph quickly to get data
                    graph, plan = self._task_templates[current_target.task]
                    # Re-run build_graph. This is efficient due to NodeRegistry caching the
                    # graph structure. We discard the returned graph but keep the new data_tuple
                    # and instance_map, effectively using it as a data extractor.
                    _, data_tuple, instance_map = build_graph(current_target)
                else:
                    # STANDARD PATH: Build graph and resolve plan for the first time
                    graph, data_tuple, instance_map = build_graph(current_target)
                    plan = self.solver.resolve(graph)

                    # Cache the template for future TCO loops
                    if isinstance(current_target, LazyResult) and self._is_simple_task(
                        current_target
                    ):
                        self._task_templates[current_target.task] = (graph, plan)
~~~~~
~~~~~python
                if is_fast_path:
                    # FAST PATH: Reuse plan, rebuild graph quickly to get data
                    graph, plan = self._task_templates[current_target.task]
                    _, data_tuple, instance_map = build_graph(current_target)

                    # BUGFIX: The instance_map from the new build_graph will contain a new,
                    # ephemeral node ID for the current_target. However, the execution plan
                    # uses the canonical node ID from the cached graph. We must align them.
                    # For a simple TCO task, the canonical target is the first (and only)
                    # node in the first stage of the plan.
                    if plan and plan[0]:
                        canonical_target_node = plan[0][0]
                        instance_map[current_target._uuid] = canonical_target_node
                else:
                    # STANDARD PATH: Build graph and resolve plan for the first time
                    graph, data_tuple, instance_map = build_graph(current_target)
                    plan = self.solver.resolve(graph)

                    # Cache the template for future TCO loops
                    if isinstance(current_target, LazyResult) and self._is_simple_task(
                        current_target
                    ):
                        self._task_templates[current_target.task] = (graph, plan)
~~~~~
