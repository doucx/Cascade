## [WIP] fix(engine): Limit graph caching to single-node graphs

### 摘要头
`# [WIP] fix(engine): Limit graph caching to single-node graphs`

### 用户需求
1.  修复 `tco_performance.py` 中 `heavy_complex_countdown` 导致的 `DependencyMissingError`。
2.  该错误是由 `Engine` 中不完善的图缓存更新逻辑 (`_update_graph_literals`) 引起的，该逻辑目前无法正确处理多节点图的 UUID 更新。
3.  解决方案是限制图缓存机制仅对单节点图生效，对于复杂图强制重新构建。这也符合 `heavy_complex_countdown` 旨在测试图构建开销的初衷。

### 错误分析
`heavy_complex_countdown` 生成了一个包含 11 个节点的图。由于递归调用时结构哈希不变，`Engine` 命中了图缓存。然而，`_update_graph_literals` 仅简单地更新了最后一个节点的 UUID 和参数，导致图中其他依赖节点（`noop` 链）保留了旧的 UUID。当 `target` 节点试图查找其新参数（指向新 UUID 的依赖）时，Engine 却只产生了旧 UUID 的结果，导致依赖缺失。

### 评论
这是一个临时的权衡。完整的图同构更新非常复杂。限制缓存范围既修复了崩溃，又保证了基准测试的有效性（Heavy Path 确实应该很重）。

### 目标
修改 `Engine.run` 中的 TCO 循环逻辑，增加对图节点数量的检查。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/caching #scope/core #ai/instruct #task/domain/runtime #task/object/engine #task/action/bugfix #task/state/continue

---

### Script

#### Acts 1: 限制图缓存的使用

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                        if struct_hash in self._graph_cache:
                            # CACHE HIT: Reuse graph and plan
                            graph, plan = self._graph_cache[struct_hash]
                            # CRITICAL: Update literal values and UUIDs in the cached graph
                            self._update_graph_literals(graph, current_target, literals)
                        else:
                            # CACHE MISS: Build, solve, and cache
                            graph = build_graph(current_target)
                            plan = self.solver.resolve(graph)
                            self._graph_cache[struct_hash] = (graph, plan)
~~~~~
~~~~~python
                        if struct_hash in self._graph_cache:
                            # CACHE HIT: Reuse graph and plan
                            cached_graph, cached_plan = self._graph_cache[struct_hash]
                            
                            # LIMITATION: Current _update_graph_literals only supports single-node graphs correctly.
                            # For complex graphs, we must rebuild to ensure all UUIDs are correct.
                            if len(cached_graph.nodes) > 1:
                                graph = build_graph(current_target)
                                plan = self.solver.resolve(graph)
                            else:
                                graph = cached_graph
                                plan = cached_plan
                                self._update_graph_literals(graph, current_target, literals)
                        else:
                            # CACHE MISS: Build, solve, and cache
                            graph = build_graph(current_target)
                            plan = self.solver.resolve(graph)
                            self._graph_cache[struct_hash] = (graph, plan)
~~~~~

### 下一步建议
再次运行基准测试脚本。这次应该能跑通，并给出震撼的结果。
