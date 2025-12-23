好的，我分析了最后两个失败的测试。

 错误分析

**根本原因**：在引入节点复用（interning）重构后，图中的节点 ID 不再是 `LazyResult._uuid`（一个临时的实例 ID），而是 `Node.id`（一个基于其内容的稳定结构化哈希）。然而，`test_visualize.py` 中的测试用例仍然错误地断言 DOT 文件中包含的是旧的 `_uuid`。

`cs.visualize()` 的新实现是正确的，因为它现在使用了稳定的、可预测的结构化哈希作为节点标识符。失败的根源在于**测试用例本身已经过时**，它们需要被更新以反映这一新的、更健壮的架构。

**解决方案**：
我将修改这两个失败的测试，使其不再依赖不稳定的 `_uuid`。取而代之，它们将：
1.  首先调用 `build_graph` 来获取从 `_uuid` 到其对应 `Node` 对象的 `instance_map`。
2.  使用这个映射来查找每个 `LazyResult` 实例对应的、具有稳定 `Node.id` 的 `Node` 对象。
3.  更新断言，以验证 DOT 字符串中包含的是这些正确的、稳定的 `Node.id`。

这个修复将使测试与新的架构保持一致，并验证 `visualize` 工具的正确行为。

## [WIP] fix(tests): Update visualize tests to use stable node IDs

### 错误分析
`test_visualize.py` 中的测试用例在节点复用（interning）重构后未能更新。它们仍然错误地断言 `cs.visualize()` 生成的 DOT 字符串中的节点 ID 是临时的 `LazyResult._uuid`，而新实现正确地使用了稳定的 `Node.id`（结构化哈希）。这导致了断言失败。

### 用户需求
修复 `test_visualize.py` 中的两个失败测试，使其适应使用 `Node.id` 而非 `_uuid` 的新架构。

### 评论
这是一个典型的“测试需要跟随实现演进”的案例。`visualize` 工具的行为是正确的，因为它现在暴露了更稳定、更有意义的节点标识符。修复测试用例不仅能使测试通过，还能使其本身变得更加健壮，因为它将验证 `visualize` 是否正确地使用了规范化的节点 ID。

### 目标
1.  修改 `test_visualize_diamond_graph` 和 `test_visualize_special_edge_types`。
2.  在测试中调用 `build_graph` 以获取 `instance_map`。
3.  使用 `instance_map` 查找 `LazyResult` 对应的 `Node` 对象及其稳定的 `id`。
4.  更新 `assert` 语句以使用正确的 `Node.id`。
5.  使所有测试通过。

### 基本原理
我们将重构测试逻辑，使其首先通过 `build_graph(target)` 获取 `graph`, `data_tuple`, 和 `instance_map`。然后，对于测试中定义的每个 `LazyResult` 实例（如 `r_a`, `r_b`），我们将使用 `instance_map[r_a._uuid]` 来获取其对应的、唯一的 `Node` 对象。最后，我们将使用 `node.id` 来构造预期的 DOT 字符串片段，从而使断言与 `visualize` 函数的实际输出保持一致。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #comp/sdk #scope/core #ai/instruct #task/domain/testing #task/object/test-failures #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复可视化测试用例

我们将一次性修复 `tests/sdk/tools/test_visualize.py` 中的两个失败测试，使其使用正确的节点 ID 进行断言。

~~~~~act
patch_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    dot_string = cs.visualize(r_d)

    # Basic structural checks
    assert dot_string.startswith("digraph CascadeWorkflow {")
    assert dot_string.endswith("}")
    assert 'rankdir="TB"' in dot_string

    # Check node definitions with new default styles
    # style="rounded,filled", fillcolor=white, fontcolor=black
    assert (
        f'"{r_a._uuid}" [label="t_a\\n(task)", shape=box, style="rounded,filled", fillcolor=white, fontcolor=black];'
        in dot_string
    )
    assert (
        f'"{r_b._uuid}" [label="t_b\\n(task)", shape=box, style="rounded,filled", fillcolor=white, fontcolor=black];'
        in dot_string
    )

    # Check data edge definitions
    assert f'"{r_a._uuid}" -> "{r_b._uuid}" [label="0"];' in dot_string
    assert f'"{r_c._uuid}" -> "{r_d._uuid}" [label="z"];' in dot_string
~~~~~
~~~~~python
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    # Pre-build to get the instance map for stable IDs
    from cascade.graph.build import build_graph
    _, _, instance_map = build_graph(r_d)
    
    node_a = instance_map[r_a._uuid]
    node_b = instance_map[r_b._uuid]
    node_c = instance_map[r_c._uuid]
    node_d = instance_map[r_d._uuid]

    dot_string = cs.visualize(r_d)

    # Basic structural checks
    assert dot_string.startswith("digraph CascadeWorkflow {")
    assert dot_string.endswith("}")
    assert 'rankdir="TB"' in dot_string

    # Check node definitions with new default styles
    # style="rounded,filled", fillcolor=white, fontcolor=black
    assert (
        f'"{node_a.id}" [label="t_a\\n(task)", shape=box, style="rounded,filled", fillcolor=white, fontcolor=black];'
        in dot_string
    )
    assert (
        f'"{node_b.id}" [label="t_b\\n(task)", shape=box, style="rounded,filled", fillcolor=white, fontcolor=black];'
        in dot_string
    )

    # Check data edge definitions
    assert f'"{node_a.id}" -> "{node_b.id}" [label="0"];' in dot_string
    assert f'"{node_c.id}" -> "{node_d.id}" [label="z"];' in dot_string
~~~~~
~~~~~act
patch_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
    target = (
        t_main(data_in=data_source).run_if(cond).with_constraints(cpu=constraint_val)
    )

    dot_string = cs.visualize(target)

    # 1. Assert Data Edge (standard style)
    assert f'"{data_source._uuid}" -> "{target._uuid}" [label="data_in"];' in dot_string

    # 2. Assert Condition Edge (dashed, gray)
    expected_cond_edge = (
        f'"{cond._uuid}" -> "{target._uuid}" [style=dashed, color=gray, label="run_if"]'
    )
    assert expected_cond_edge in dot_string

    # 3. Assert Constraint Edge (dotted, purple)
    expected_constraint_edge = f'"{constraint_val._uuid}" -> "{target._uuid}" [style=dotted, color=purple, label="constraint: cpu"]'
    assert expected_constraint_edge in dot_string
~~~~~
~~~~~python
    target = (
        t_main(data_in=data_source).run_if(cond).with_constraints(cpu=constraint_val)
    )

    from cascade.graph.build import build_graph
    _, _, instance_map = build_graph(target)

    node_ds = instance_map[data_source._uuid]
    node_target = instance_map[target._uuid]
    node_cond = instance_map[cond._uuid]
    node_constraint = instance_map[constraint_val._uuid]

    dot_string = cs.visualize(target)

    # 1. Assert Data Edge (standard style)
    assert f'"{node_ds.id}" -> "{node_target.id}" [label="data_in"];' in dot_string

    # 2. Assert Condition Edge (dashed, gray)
    expected_cond_edge = (
        f'"{node_cond.id}" -> "{node_target.id}" [style=dashed, color=gray, label="run_if"]'
    )
    assert expected_cond_edge in dot_string

    # 3. Assert Constraint Edge (dotted, purple)
    expected_constraint_edge = f'"{node_constraint.id}" -> "{node_target.id}" [style=dotted, color=purple, label="constraint: cpu"]'
    assert expected_constraint_edge in dot_string
~~~~~

### 下一步建议
我们已经修复了最后两个失败的测试。现在，整个测试套件应该能够完全通过了。

这标志着**“第二阶段：构建器演进 - 2.1 节点复用”** 的所有核心实现和相关的 bug 修复工作都已完成。代码库现在处于一个稳定的状态。

我建议我们正式结束这一阶段，并准备开始路线图的下一个主要任务：**“2.2 分离的数据提取流程”**。
