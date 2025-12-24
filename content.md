Of course. The test failed exactly as we predicted, but the failure reveals a deeper truth than just a rendering issue. My previous "fix" was flawed because I didn't trace the problem to its source.

Let's break it down.

测试失败的直接原因是 `visualize.py` 渲染了一个从 `C` 到 `C` 的自引用边，而不是我们期望的 `C` 到 `A` 的边。然而，这只是症状，不是病因。

根本原因在于 `cascade-graph/src/cascade/graph/build.py` 中的 `GraphBuilder`。当前，当它遇到 `cs.bind()` 创建的 `ITERATIVE_JUMP` 边时，它会创建一个**占位符**边，其 `target` 硬编码为 `source` 节点，如代码注释所示 (`target=node,  # Placeholder, engine uses jump_selector`)。这个占位符对于运行时引擎是足够的，因为它可以在执行时动态查询 `jump_selector`。但是，对于静态分析工具 `visualize` 来说，它看到的就是一个错误的、自引用的图。

因此，真正的修复方案必须双管齐下：
1.  **修正 `GraphBuilder`**: 让它构建一个能准确反映所有静态跳转路径的图。
2.  **修正 `visualize`**: 让它能通用地渲染这些正确的跳转边，并使用跳转键 (`"next"`, `"restart"`) 作为标签，这比硬编码的 `"jump"` 更具信息量。

我将生成一个计划来同时解决这两个问题，并更新我们的测试用例以反映这个更智能的标签。

## [WIP] feat: 通用化跳转边的图构建与可视化逻辑

### 用户需求
修正 `GraphBuilder` 和 `visualize`，使其能够正确构建和渲染任意 `ITERATIVE_JUMP` 边（包括多节点循环），从而让所有相关测试通过。

### 评论
这次修复将从根本上提升新架构的质量。通过让 `GraphBuilder` 创建一个拓扑上完全准确的图，我们不仅修复了 `visualize`，还为未来任何需要静态分析控制流的工具（如 Linter、优化器）打下了坚实的基础。这是从“运行时 Hack”到“架构性正确”的关键一步。

### 目标
1.  **`GraphBuilder`**: 修改 `_visit_lazy_result` 方法。当处理 `_jump_selector` 时，不再创建单个占位符边，而是遍历 `selector.routes` 中的每一条路由，为每个非 `None` 的目标创建一个独立的、`source` 和 `target` 均正确的 `ITERATIVE_JUMP` 边。将路由的键（如 `"restart"`）用作边的 `arg_name`。
2.  **`visualize.py`**: 修改 `ITERATIVE_JUMP` 的处理逻辑。不再硬编码自引用 (`source -> source`)，而是使用边对象上正确的 `source` 和 `target`。同时，使用 `edge.arg_name` 作为边的标签。
3.  **`test_visualize.py`**: 更新两个跳转测试用例的断言，使其检查正确的动态标签（`"next"` 和 `"restart"`），而不是之前硬编码的 `"jump"`。

### 基本原理
我们将把智能逻辑前移到 `GraphBuilder` 中。`GraphBuilder` 将成为静态拓扑的唯一真相来源，它会明确地在图中创建出 `C -> A` 这样的边。这样一来，`visualize` 就可以变回一个“哑”渲染器，它只需为 `ITERATIVE_JUMP` 类型的边应用特殊样式即可，无需理解复杂的跳转逻辑。这种职责分离使得两个组件都更加健壮和可维护。

### 标签
#intent/refine #flow/ready #priority/high #comp/graph #comp/sdk #scope/core #ai/instruct #task/domain/visualization #task/object/explicit-jumps #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正 `GraphBuilder` 以创建拓扑正确的跳转边

我们将修改 `build.py`，用一个循环替换掉创建占位符边的逻辑。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
                # Create the ITERATIVE_JUMP edge
                self.graph.add_edge(
                    Edge(
                        source=node,
                        target=node,  # Placeholder, engine uses jump_selector
                        arg_name="<jump>",
                        edge_type=EdgeType.ITERATIVE_JUMP,
                        jump_selector=selector,
                    )
                )
~~~~~
~~~~~python
                # Create a distinct ITERATIVE_JUMP edge for each potential jump target.
                # This makes the static graph correctly represent all potential control flows.
                for key, route_target_lr in selector.routes.items():
                    if route_target_lr is None:
                        continue  # Skip exit routes, as they don't form an edge

                    # We have already visited the target, so it's in the instance map
                    target_node = self._visited_instances[route_target_lr._uuid]

                    self.graph.add_edge(
                        Edge(
                            source=node,
                            target=target_node,
                            arg_name=key,  # Use the jump key as the edge label
                            edge_type=EdgeType.ITERATIVE_JUMP,
                            # We can still attach the selector for the engine's use
                            jump_selector=selector,
                        )
                    )
~~~~~

#### Acts 2: 通用化 `visualize.py` 的跳转边渲染逻辑

现在 `GraphBuilder` 提供了正确的边，我们来修正渲染器，让它使用这些信息。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/visualize.py
~~~~~
~~~~~python
        elif edge.edge_type == EdgeType.ITERATIVE_JUMP:
            # Special case for self-referencing jump edges
            style = ' [style=bold, color=blue, label="jump"]'
            dot_parts.append(
                f'  "{edge.source.structural_id}" -> "{edge.source.structural_id}"{style};'
            )
            # Continue to the next edge to avoid double-printing
            continue
~~~~~
~~~~~python
        elif edge.edge_type == EdgeType.ITERATIVE_JUMP:
            style = f' [style=bold, color=blue, label="{edge.arg_name}"]'
~~~~~

#### Acts 3: 更新测试用例以断言正确的动态标签

最后，我们更新两个测试用例，让它们检查新的、信息更丰富的标签。

~~~~~act
patch_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
    # Assert that a self-referencing, specially styled "jump" edge exists
    expected_edge = (
        f'"{node_id}" -> "{node_id}" [style=bold, color=blue, label="jump"]'
    )
    assert expected_edge in dot_string
~~~~~
~~~~~python
    # Assert that a self-referencing, specially styled "jump" edge exists
    expected_edge = (
        f'"{node_id}" -> "{node_id}" [style=bold, color=blue, label="next"]'
    )
    assert expected_edge in dot_string
~~~~~

~~~~~act
patch_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
    # 5. Assert that the styled jump edge from C to A exists
    expected_edge = (
        f'"{source_id}" -> "{target_id}" [style=bold, color=blue, label="jump"]'
    )
    assert expected_edge in dot_string
~~~~~
~~~~~python
    # 5. Assert that the styled jump edge from C to A exists
    expected_edge = (
        f'"{source_id}" -> "{target_id}" [style=bold, color=blue, label="restart"]'
    )
    assert expected_edge in dot_string
~~~~~

### 下一步建议
我们已经从根本上解决了图构建和可视化的问题。现在所有测试都应该通过，并且我们的可视化工具变得更加强大和准确。

这是一个逻辑上完整且重要的改进。我强烈建议我们现在创建一个 `[COMMIT]` 计划，将这三个文件的修改作为一个原子提交进行暂存和提交，以清晰地记录这次从“占位符”到“拓扑正确”的架构演进。
