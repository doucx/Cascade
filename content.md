好的，我们正式开始执行路线图中的第四步。

本次的核心任务是重构 `GraphExecutionStrategy` 以实现真正的零开销尾递归优化（TCO），这是发挥新架构全部威力的关键一步。我们将启用并完善 TCO “快速通道”逻辑，让引擎能够识别并缓存可复用的执行计划，从而跳过绝大多数重复计算。

我将生成一个计划来完成这项工作。

## [WIP] refactor(engine): Implement TCO fast path in GraphExecutionStrategy

### 用户需求
根据重构路线图，完成第四步，即重构 `GraphExecutionStrategy` 中的 TCO 逻辑，使其能够缓存和复用执行计划，实现对 TCO 循环的零开销优化。

### 评论
这是一个至关重要的性能优化，是本次架构重构的“回报”所在。通过实现真正的 TCO 快速通道，我们将兑现 Cascade 的核心承诺之一：让递归的、Agent 风格的任务能够以接近原生循环的性能无限运行。这一改进将直接利用我们在前几步中构建的“模板-实例分离”和节点规范化（`NodeRegistry`）的基础设施。

### 目标
1.  修改 `GraphExecutionStrategy.execute` 的主循环，以正确识别 TCO 循环候选者。
2.  当一个 TCO 候选任务被识别，并且其 `(GraphTemplate, ExecutionPlan)` 已被缓存时，进入“快速通道”。
3.  在快速通道中，**跳过**昂贵的 `solver.resolve()` 步骤，直接复用缓存的 `ExecutionPlan`。
4.  在快速通道中，仍然调用 `build_graph()`。这是一种高效的做法，因为 `NodeRegistry` 会确保图的“骨架”部分因缓存而快速构建，同时此调用能正确地从新的 `LazyResult` 实例中提取出新的运行时数据（“血肉”`data_tuple`）。
5.  使用缓存的计划和新的数据继续执行，从而完成一次零开销的 TCO 迭代。

### 基本原理
在新的架构下，TCO 循环中每一轮迭代的“图模板”和“执行计划”都是完全相同的，变化的仅仅是传入的运行时数据（`data_tuple`）。因此，最大的性能开销——求解器解析图拓扑以生成执行计划（`solver.resolve()`）——是完全可以避免的。

我们将通过 `_task_templates` 字典缓存每个 TCO 候选任务的 `(Graph, ExecutionPlan)`。在后续迭代中，如果识别到同一个任务，我们就直接从缓存中取出计划。同时，我们依然调用 `build_graph()`，但其目的已经从“构建图”转变为“提取数据”。得益于 `NodeRegistry` 的存在，`build_graph` 在处理已见过的结构时会非常快，因为它只需进行字典查找，而无需创建新对象。这种“复用计划，提取数据”的模式，便是实现零开销 TCO 的核心。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #concept/state #scope/core #ai/instruct #task/domain/runtime #task/object/tco-optimization #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 启用并实现 TCO 快速通道

我们将修改 `strategies.py` 文件，重写 `GraphExecutionStrategy.execute` 方法中的 TCO 检查和执行路径逻辑。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
                graph = None
                plan = None
                data_tuple = () # The Flesh
                is_fast_path = False

                # --- 1. ZERO-OVERHEAD FAST PATH CHECK ---
                # Check if we are in a recognized TCO loop (A -> B -> ... -> A)
                
                if isinstance(current_target, LazyResult) and self._is_simple_task(current_target):
                    task_obj = current_target.task
                    cycle_id = getattr(task_obj, "_tco_cycle_id", None)
                    
                    if (cycle_id and cycle_id == last_tco_cycle_id) or (task_obj == last_executed_task):
                        if task_obj in self._task_templates:
                            is_fast_path = True
                            graph, plan = self._task_templates[task_obj]
                            # For fast path, we still need to extract data!
                            # Since we skipped build_graph, we need a lightweight data extractor.
                            # BUT, for V3 step 1, we can just call build_graph and throw away the graph 
                            # if we want to be lazy, OR just disable fast path for now until we build a pure DataExtractor.
                            # Disable fast path for this commit to ensure correctness first.
                            is_fast_path = False 
                
                if not is_fast_path:
                    # --- 2. STANDARD PATH ---
                    # Always build fresh for now to handle data extraction
                    graph, data_tuple, instance_map = build_graph(current_target)
                    plan = self.solver.resolve(graph)
                    
                    # Store in template cache for future optimization (even if we don't fully use it yet)
                    if isinstance(current_target, LazyResult) and self._is_simple_task(current_target):
                        self._task_templates[current_target.task] = (graph, plan)
~~~~~
~~~~~python
                graph, plan, data_tuple, instance_map = None, None, (), None

                is_fast_path = False
                if isinstance(current_target, LazyResult) and self._is_simple_task(
                    current_target
                ):
                    task_obj = current_target.task
                    cycle_id = getattr(task_obj, "_tco_cycle_id", None)

                    is_tco_candidate = (
                        cycle_id and cycle_id == last_tco_cycle_id
                    ) or (task_obj == last_executed_task)

                    if is_tco_candidate and task_obj in self._task_templates:
                        is_fast_path = True

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

### 下一步建议

我们已经完成了核心的 TCO 逻辑重构。下一步是进入路线图的 **第五步：[COMMIT 5] 清理与收尾**。

我建议我们首先全面审查代码，删除所有与旧数据模型相关的、被注释掉的或不再使用的代码。然后，我们可以创建一个 `[COMMIT]` 计划，将这次重构作为一个原子性的、完整的提交记录下来。
